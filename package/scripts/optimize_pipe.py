#!/usr/bin/env python3
"""
Optimizing pipe — continuous improvement stage of the RAG-DAG.

Goals: less relearning, better recall, healthier graph, lower waste.

Passes (in order, skip if green):
  1. graph_hygiene     — empty/corrupt JSON, orphan edges, snapshot rebuild
  2. knowledge_promote — re-rate, flag SLAG, boost linked GOLD neighbors
  3. vector_tune       — reindex if coverage < 90% of nodes
  4. session_harvest   — smart_discover incremental (new conversations)
  5. cost_trim         — tighten crawl cooldowns if budget hot
  6. recall_benchmark  — run probe queries; measure hit quality
  7. report            — write metrics:snapshot optimize + audit

CLI:
  python optimize_pipe.py run
  python optimize_pipe.py run --aggressive
  python optimize_pipe.py status
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from audit_lib import audit, verify_chain
from brain_lib import (
    EDGE_DIR,
    NODE_DIR,
    STATE_DIR,
    build_snapshot,
    ensure_tree,
    load_all_nodes,
    node_path,
    read_json,
    status,
    utc_now,
    write_json,
)
from orchestrate import load_cost_state, save_cost_state


def pass_graph_hygiene() -> dict[str, Any]:
    ensure_tree()
    fixed = {"bad_nodes": 0, "bad_edges": 0, "orphans_noted": 0}
    node_ids = set()
    for p in NODE_DIR.glob("*.json"):
        try:
            n = read_json(p)
            if not n or not n.get("id"):
                p.unlink(missing_ok=True)
                fixed["bad_nodes"] += 1
                continue
            node_ids.add(n["id"])
        except Exception:
            try:
                p.unlink()
            except Exception:
                pass
            fixed["bad_nodes"] += 1
    for p in EDGE_DIR.glob("*.json"):
        try:
            e = read_json(p)
            if not e or not e.get("src") or not e.get("dst"):
                p.unlink(missing_ok=True)
                fixed["bad_edges"] += 1
                continue
            if e["src"] not in node_ids or e["dst"] not in node_ids:
                # keep edge but note orphan — may resolve after partial ingest
                fixed["orphans_noted"] += 1
        except Exception:
            try:
                p.unlink()
            except Exception:
                pass
            fixed["bad_edges"] += 1
    # hygiene mutates files outside write_node — drop process caches
    try:
        from brain_lib import invalidate_graph_cache
        invalidate_graph_cache()
    except Exception:
        pass
    snap = build_snapshot(force=True).get("stats")
    return {"ok": True, "fixed": fixed, "snapshot": snap}


def pass_knowledge_promote() -> dict[str, Any]:
    from knowledge_rater import rate_all

    rated = rate_all(persist=True)
    nodes = load_all_nodes()
    # tag chronically thin SLAG for review
    slag = 0
    gold = 0
    for n in nodes:
        band = n.get("knowledge_band")
        if band == "SLAG":
            slag += 1
            tags = list(n.get("tags") or [])
            if "needs-enrichment" not in tags:
                tags.append("needs-enrichment")
                try:
                    obj = read_json(node_path(n["id"]))
                    obj["tags"] = tags
                    write_json(node_path(n["id"]), obj)
                except Exception:
                    pass
        elif band == "GOLD":
            gold += 1
    return {
        "ok": True,
        "rated": rated.get("rated"),
        "bands": rated.get("bands"),
        "avg": rated.get("avg"),
        "slag_tagged": slag,
        "gold": gold,
    }


def pass_vector_tune(aggressive: bool = False) -> dict[str, Any]:
    from vector_manager import reindex_all
    from vector_manager import status as vs

    st = status()
    v = vs()
    nodes = int(st.get("node_count") or 0)
    vecs = int(v.get("vectors") or 0)
    coverage = (vecs / nodes) if nodes else 1.0
    if aggressive or coverage < 0.9:
        r = reindex_all()
        return {"ok": True, "reindexed": True, "result": r, "coverage_before": round(coverage, 3)}
    return {"ok": True, "reindexed": False, "coverage": round(coverage, 3), "vectors": vecs}


def pass_session_harvest(max_files: int = 80) -> dict[str, Any]:
    try:
        from smart_discover import run_discover_ingest

        d = run_discover_ingest(max_files=max_files, force=False, agent_id="optimize-pipe")
        return {
            "ok": True,
            "discovered": d.get("discovered"),
            "ingested": d.get("ingested"),
            "skipped": d.get("skipped"),
            "by_kind": d.get("by_kind"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def pass_cost_trim() -> dict[str, Any]:
    s = load_cost_state()
    window = int(s.get("window_calls") or 0)
    cap = int(s.get("max_api_calls_per_hour") or 500)
    changed = False
    actions = []
    if window > cap * 0.7:
        # tighten crawl cooldown
        old = int(s.get("min_crawl_interval_sec") or 300)
        s["min_crawl_interval_sec"] = min(3600, max(old, 600))
        changed = True
        actions.append(f"raised min_crawl_interval_sec to {s['min_crawl_interval_sec']}")
    if window > cap * 0.9:
        s["max_api_calls_per_hour"] = max(100, int(cap * 0.9))
        changed = True
        actions.append(f"soft-capped max_api_calls_per_hour to {s['max_api_calls_per_hour']}")
    if changed:
        save_cost_state(s)
    return {"ok": True, "changed": changed, "actions": actions, "state": s}


def pass_recall_benchmark(probes: list[str] | None = None) -> dict[str, Any]:
    """Measure whether we can recall without relearning (local retrieve only)."""
    from brain_lib import query
    from vector_manager import search_vectors

    probes = probes or [
        "kafka",
        "controller",
        "wiki",
        "session",
        "resilience",
    ]
    results = []
    hits_total = 0
    for p in probes:
        lex = query(p, limit=5)
        try:
            vec = search_vectors(p, limit=5)
        except Exception:
            vec = []
        hits_total += len(lex)
        results.append(
            {
                "probe": p,
                "lexical_hits": len(lex),
                "vector_hits": len(vec),
                "top": [h.get("id") for h in lex[:2]],
            }
        )
    score = hits_total / max(1, len(probes))
    return {
        "ok": score >= 1.0,
        "avg_lexical_hits": round(score, 2),
        "probes": results,
        "no_relearn_ready": score >= 1.0,
    }


def run_optimize(aggressive: bool = False) -> dict[str, Any]:
    ensure_tree()
    rid = os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"optimize-{utc_now()}"
    audit("optimize_start", agent_id="optimize-pipe", role="optimizer", run_id=rid, result="start")

    passes: dict[str, Any] = {}
    passes["graph_hygiene"] = pass_graph_hygiene()
    passes["session_harvest"] = pass_session_harvest(max_files=500 if aggressive else 200)
    passes["knowledge_promote"] = pass_knowledge_promote()
    passes["vector_tune"] = pass_vector_tune(aggressive=aggressive)
    passes["cost_trim"] = pass_cost_trim()
    passes["recall_benchmark"] = pass_recall_benchmark()

    chain = verify_chain()
    st = status()
    out = {
        "stage": "optimize",
        "ok": all(p.get("ok", True) for p in passes.values() if isinstance(p, dict)),
        "run_id": rid,
        "passes": passes,
        "brain": {"nodes": st.get("node_count"), "edges": st.get("edge_count"), "by_source": st.get("by_source")},
        "chain_ok": chain.get("ok"),
        "no_relearn_ready": (passes.get("recall_benchmark") or {}).get("no_relearn_ready"),
        "ts": utc_now(),
    }

    # catalog snapshot into brain
    try:
        from ingest_bus import ingest_node

        nid = f"metrics:snapshot:optimize:{utc_now().replace(':','').replace('-','')[:15]}"
        ingest_node(
            nid,
            type="MetricsSnapshot",
            source="metrics",
            title="Optimize pipe snapshot",
            tier="T1",
            tags=["metrics", "optimize", "pipeline"],
            labels=["optimizer"],
            content=json.dumps(out, indent=2, default=str)[:40000],
            props={"kind": "optimize"},
            agent_id="optimize-pipe",
            role="optimizer",
        )
        out["snapshot_node_id"] = nid
    except Exception as e:
        out["snapshot_error"] = str(e)[:160]

    write_json(STATE_DIR / "optimize_last.json", out)
    audit(
        "optimize_complete",
        agent_id="optimize-pipe",
        role="optimizer",
        run_id=rid,
        result="ok" if out["ok"] else "partial",
        detail=f"no_relearn={out.get('no_relearn_ready')} nodes={st.get('node_count')}",
        props={"passes": list(passes.keys())},
    )
    return out


def status_opt() -> dict[str, Any]:
    p = STATE_DIR / "optimize_last.json"
    if p.exists():
        return read_json(p)
    return {"ok": False, "detail": "never ran"}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "status"])
    ap.add_argument("--aggressive", action="store_true")
    args = ap.parse_args()
    if args.cmd == "status":
        print(json.dumps(status_opt(), indent=2, default=str))
        return 0
    out = run_optimize(aggressive=args.aggressive)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
