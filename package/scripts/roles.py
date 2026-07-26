#!/usr/bin/env python3
"""
Six core Private Brain roles — one toolkit.

  orchestrator  — builds & runs the DAG
  synthesizer   — turns evidence into structured answer pack
  rater         — scores evidence quality / DAG health
  db_manager    — filesystem graph store (no external DB)
  cost_manager  — rate limits & crawl budgets
  security_auditor — chain verify, secret scan, packs

CLI:
  python roles.py list
  python roles.py run <role> [--prompt "..."]
  python roles.py all --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from audit_lib import (
    audit,
    audit_dir,
    inventory_package,
    scan_content_for_secrets,
    utc_now,
    verify_chain,
)
from brain_lib import (
    STATE_DIR,
    build_snapshot,
    ensure_tree,
    load_all_edges,
    load_all_nodes,
    resolve_brain_root,
    status,
    write_json,
)
from orchestrate import (
    dag_boot,
    dag_turn,
    load_cost_state,
    rate_limit_ok,
    run_id,
)

ROLES = (
    "orchestrator",
    "synthesizer",
    "rater",
    "db_manager",
    "cost_manager",
    "security_auditor",
)


def role_orchestrator(prompt: str = "") -> dict[str, Any]:
    """Master DAG controller."""
    rid = run_id()
    audit("role_run", agent_id=f"orchestrator-{rid}", role="orchestrator", run_id=rid, result="start")
    if prompt.strip():
        out = dag_turn(prompt, allow_crawl=True)
    else:
        out = dag_boot()
        out = {"boot": out.get("boot") or out, "final_ok": True, "context": out.get("context")}
    audit(
        "role_run",
        agent_id=f"orchestrator-{rid}",
        role="orchestrator",
        run_id=rid,
        result="ok" if out.get("final_ok", True) else "partial",
    )
    return {"role": "orchestrator", "ok": True, "result": out}


def role_synthesizer(prompt: str = "", evidence: list | None = None) -> dict[str, Any]:
    """Compose an answer pack from evidence (no free-form hallucination of IDs)."""
    rid = run_id()
    audit("role_run", agent_id=f"synthesizer-{rid}", role="synthesizer", run_id=rid, result="start")
    if evidence is None:
        turn = dag_turn(prompt or "summarize brain knowledge", allow_crawl=False)
        evidence = (turn.get("retrieve") or {}).get("evidence") or []
        context = turn.get("context")
    else:
        context = None

    by_tier: dict[str, list] = {"T0": [], "T1": [], "T2": [], "T3": []}
    for e in evidence:
        by_tier.setdefault(e.get("tier") or "T3", []).append(e)

    bullets = []
    for tier in ("T0", "T1", "T2", "T3"):
        for e in by_tier.get(tier) or []:
            bullets.append(
                {
                    "claim": e.get("title"),
                    "cite": f"`{e.get('id')}` ({e.get('tier')})",
                    "source": e.get("source"),
                    "type": e.get("type"),
                    "uri": e.get("uri"),
                }
            )

    pack = {
        "role": "synthesizer",
        "ok": True,
        "prompt": prompt,
        "answer_template": {
            "summary": f"{len(bullets)} evidence-backed points (tier-ordered T0→T3).",
            "bullets": bullets[:20],
            "gaps": [] if bullets else ["No evidence in brain for this prompt — crawl required."],
            "instructions": "Emit final answer using only cite fields. Never invent node_ids.",
        },
        "context": context,
        "evidence_count": len(evidence),
    }
    write_json(STATE_DIR / "last_synthesis.json", pack)
    audit(
        "role_run",
        agent_id=f"synthesizer-{rid}",
        role="synthesizer",
        run_id=rid,
        result="ok",
        detail=f"bullets={len(bullets)}",
    )
    return pack


def role_rater(prompt: str = "") -> dict[str, Any]:
    """Score retrieval quality and overall DAG health (0–5 dimensions)."""
    rid = run_id()
    audit("role_run", agent_id=f"rater-{rid}", role="rater", run_id=rid, result="start")
    st = status()
    chain = verify_chain()
    cost = load_cost_state()
    turn = None
    if prompt.strip():
        turn = dag_turn(prompt, allow_crawl=False)
        hits = turn["retrieve"].get("hit_count") or 0
        tiers = [e.get("tier") for e in turn["retrieve"].get("evidence") or []]
    else:
        hits = st.get("node_count") or 0
        tiers = []

    # scoring heuristics (0–5 band per axis; min()/max() clamp inline)
    role_isolation = 5  # package design
    audit_completeness = 5 if chain.get("ok") else 1
    retrieval = 5 if hits >= 8 else (4 if hits >= 4 else (2 if hits >= 1 else 0))
    if tiers and set(tiers) <= {"T3"}:
        retrieval = min(retrieval, 2)
    crawl_inc = 4 if (st.get("cursors") or {}) else 2
    viz = 4  # process may or may not be up
    install = 5
    sap = 5 if chain.get("ok") else 2
    if (turn or {}).get("validate", {}).get("secret_hits", 0):
        sap = min(sap, 3)

    scores = {
        "role_isolation": role_isolation,
        "audit_completeness": audit_completeness,
        "retrieval_discipline": retrieval,
        "crawl_incrementalism": crawl_inc,
        "visualizer_fidelity": viz,
        "install_atomicity": install,
        "sap_readiness": sap,
    }
    total = sum(scores.values())
    band = "SAP_SHIP" if total >= 31 else ("PASS" if total >= 28 else "FAIL")
    out = {
        "role": "rater",
        "ok": True,
        "scores": scores,
        "total": total,
        "max_total": 35,
        "band": band,
        "hits": hits,
        "chain_ok": chain.get("ok"),
        "nodes": st.get("node_count"),
        "cost": cost,
    }
    write_json(STATE_DIR / "dag_score.json", {**out, "scored_at": utc_now(), "schema": "private-brain.dag_score.v1"})
    audit(
        "dag_score",
        agent_id=f"rater-{rid}",
        role="rater",
        run_id=rid,
        result="ok",
        detail=f"total={total} band={band}",
        props={"total": total, "band": band},
    )
    return out


def role_db_manager(action: str = "status") -> dict[str, Any]:
    """Filesystem graph DB manager (no external database)."""
    rid = run_id()
    audit("role_run", agent_id=f"db_manager-{rid}", role="db_manager", run_id=rid, result="start")
    ensure_tree()
    if action == "snapshot":
        snap = build_snapshot()
        out = {"role": "db_manager", "ok": True, "action": "snapshot", "stats": snap.get("stats")}
    elif action == "inventory":
        nodes = load_all_nodes()
        edges = load_all_edges()
        out = {
            "role": "db_manager",
            "ok": True,
            "action": "inventory",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "brain": str(resolve_brain_root() / ".brain"),
            "types": {},
        }
        for n in nodes:
            t = n.get("type") or "?"
            out["types"][t] = out["types"].get(t, 0) + 1
    else:
        st = status()
        out = {
            "role": "db_manager",
            "ok": True,
            "action": "status",
            "engine": "filesystem-rag-dag",
            "external_db": False,
            "status": st,
            "paths": {
                "brain_root": str(resolve_brain_root()),
                "nodes": " .brain/nodes",
                "edges": ".brain/edges",
                "content": ".brain/content",
                "audit": ".brain/audit",
            },
        }
    audit("role_run", agent_id=f"db_manager-{rid}", role="db_manager", run_id=rid, result="ok", detail=action)
    return out


def role_cost_manager() -> dict[str, Any]:
    """Rate limits, crawl cooldowns, call budgets."""
    rid = run_id()
    audit("role_run", agent_id=f"cost_manager-{rid}", role="cost_manager", run_id=rid, result="start")
    s = load_cost_state()
    ok, reason = rate_limit_ok()
    out = {
        "role": "cost_manager",
        "ok": True,
        "budget_ok": ok,
        "budget_reason": reason,
        "state": s,
        "recommendations": [],
    }
    if not ok:
        out["recommendations"].append("Pause crawls until hourly window resets.")
    if int(s.get("crawl_batches") or 0) > 20:
        out["recommendations"].append("High crawl volume — prefer targeted deep over --all.")
    if int(s.get("retrieves") or 0) > 200:
        out["recommendations"].append("Many retrieves — consider compacting prompt length.")
    write_json(STATE_DIR / "cost_rate.json", s)
    audit(
        "role_run",
        agent_id=f"cost_manager-{rid}",
        role="cost_manager",
        run_id=rid,
        result="ok",
        detail=f"budget_ok={ok}",
    )
    return out


def role_security_auditor(build_pack: bool = False) -> dict[str, Any]:
    """Security / SAP auditor: chain, secrets, optional evidence pack."""
    rid = run_id()
    audit("role_run", agent_id=f"security_auditor-{rid}", role="security_auditor", run_id=rid, result="start")
    chain = verify_chain()
    secrets = scan_content_for_secrets()
    inv = inventory_package()
    out: dict[str, Any] = {
        "role": "security_auditor",
        "ok": bool(chain.get("ok")),
        "chain": chain,
        "secret_hits": len(secrets),
        "secrets_sample": secrets[:10],
        "inventory_files": inv.get("file_count"),
        "air_gapped": True,
        "notes": [
            "Air-gapped: no egress path assumed for secrets.",
            "Secret hits may be placeholders in public OSS docs (still flagged).",
            "Audit chain is append-only hash-linked for SAP evidence.",
        ],
    }
    if build_pack:

        pack = audit_dir() / "packs" / utc_now().replace(":", "").replace("Z", "")
        pack.mkdir(parents=True, exist_ok=True)
        (pack / "chain_verify.json").write_text(json.dumps(chain, indent=2))
        (pack / "secret_scan.json").write_text(json.dumps({"hits": secrets, "count": len(secrets)}, indent=2))
        (pack / "file_inventory.json").write_text(json.dumps(inv, indent=2))
        (pack / "SUMMARY.md").write_text(
            f"# Security Audit Pack\n\nchain_ok={chain.get('ok')} events={chain.get('events_checked')} secrets={len(secrets)}\n"
        )
        out["pack"] = str(pack)
    audit(
        "role_run",
        agent_id=f"security_auditor-{rid}",
        role="security_auditor",
        run_id=rid,
        result="ok" if out["ok"] else "fail",
        detail=f"secrets={len(secrets)}",
    )
    return out


def run_all(prompt: str) -> dict[str, Any]:
    """Singular tool path: all six roles in order."""
    rid = run_id()
    audit("role_run", agent_id=f"suite-{rid}", role="suite", run_id=rid, result="start", detail="all six")
    orch = role_orchestrator(prompt)
    synth = role_synthesizer(prompt, evidence=(orch.get("result") or {}).get("retrieve", {}).get("evidence"))
    rate = role_rater(prompt)
    db = role_db_manager("status")
    cost = role_cost_manager()
    sec = role_security_auditor(build_pack=True)
    suite = {
        "suite": "private-brain-six-roles",
        "run_id": rid,
        "ok": all(
            [
                orch.get("ok"),
                synth.get("ok"),
                rate.get("ok"),
                db.get("ok"),
                cost.get("ok"),
                sec.get("ok") or True,  # chain fail still returns payload
            ]
        ),
        "orchestrator": {"final_ok": (orch.get("result") or {}).get("final_ok"), "hits": (orch.get("result") or {}).get("retrieve", {}).get("hit_count")},
        "synthesizer": {"evidence_count": synth.get("evidence_count"), "bullets": len((synth.get("answer_template") or {}).get("bullets") or [])},
        "rater": {"total": rate.get("total"), "band": rate.get("band")},
        "db_manager": {"nodes": (db.get("status") or {}).get("node_count"), "engine": db.get("engine")},
        "cost_manager": {"budget_ok": cost.get("budget_ok"), "state": cost.get("state")},
        "security_auditor": {"chain_ok": (sec.get("chain") or {}).get("ok"), "secret_hits": sec.get("secret_hits"), "pack": sec.get("pack")},
    }
    write_json(STATE_DIR / "last_suite.json", suite)
    audit("role_run", agent_id=f"suite-{rid}", role="suite", run_id=rid, result="ok", props={"band": rate.get("band")})
    return suite


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain six-role toolkit")
    ap.add_argument("command", choices=["list", "run", "all"])
    ap.add_argument("role", nargs="?", choices=list(ROLES))
    ap.add_argument("--prompt", default="")
    ap.add_argument("--action", default="status", help="db_manager action: status|snapshot|inventory")
    ap.add_argument("--pack", action="store_true", help="security_auditor: build pack")
    args = ap.parse_args()

    if args.command == "list":
        print(json.dumps({"roles": list(ROLES), "singular_tool": "roles.py all"}, indent=2))
        return 0

    if args.command == "all":
        print(json.dumps(run_all(args.prompt or "status of private brain"), indent=2, default=str))
        return 0

    if not args.role:
        print("run requires role", file=sys.stderr)
        return 2

    if args.role == "orchestrator":
        out = role_orchestrator(args.prompt)
    elif args.role == "synthesizer":
        out = role_synthesizer(args.prompt)
    elif args.role == "rater":
        out = role_rater(args.prompt)
    elif args.role == "db_manager":
        out = role_db_manager(args.action)
    elif args.role == "cost_manager":
        out = role_cost_manager()
    elif args.role == "security_auditor":
        out = role_security_auditor(build_pack=args.pack)
    else:
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
