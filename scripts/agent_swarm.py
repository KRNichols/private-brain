#!/usr/bin/env python3
"""
Shared-topology multi-agent SWEEP — no queue babysitter.

One prompt → N agent slices → all agents read/write the SAME filesystem RAG-DAG
at the same time. Position and state live in the graph (nodes/edges/audit),
not in 32 separate memories. Conflicts resolve via atomic JSON writes + locks
inside the graph, not a central "who goes first" controller.

Inspired by graph-engineering patterns:
  - real edges only (no fake sequential "and then")
  - fan-out independent work
  - layered fan-in (batch summaries → consolidate)
  - silent-failure guard (expected vs completed count)

CLI:
  python agent_swarm.py sweep --prompt "kafka resilience" --agents 32
  python agent_swarm.py sweep --prompt "..." --agents 16 --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from audit_lib import audit
from brain_lib import (
    STATE_DIR,
    ensure_tree,
    load_all_nodes,
    query,
    read_json,
    utc_now,
    write_json,
)
from ingest_bus import ingest_edge, ingest_node
from vector_manager import search_vectors

# Agent roles that can take a slice of the shared graph
AGENT_ROLES = (
    "retriever",
    "tagger",
    "linker",
    "rater",
    "gap_finder",
    "vector_probe",
    "source_scout",
    "tier_guard",
)


def _tokens(prompt: str, n: int) -> list[str]:
    toks = [t for t in re.split(r"[^\w]+", prompt.lower()) if len(t) > 2]
    # dedupe preserve order
    seen = set()
    out = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        out = ["status", "graph", "knowledge"]
    # pad/cycle to n slices
    if len(out) < n:
        out = (out * ((n // len(out)) + 1))[:n]
    return out[:n]


def _slice_prompt(prompt: str, agent_i: int, n: int, token: str, role: str) -> dict[str, Any]:
    """Single prompt assigns every agent its slice — no manual pre-split by human."""
    return {
        "agent_index": agent_i,
        "agent_id": f"swarm-{agent_i:02d}-{role}",
        "role": role,
        "token": token,
        "slice": f"[{agent_i + 1}/{n}] role={role} focus=`{token}` on shared graph",
        "mission": (
            f"On the shared topological graph, execute role={role} for token=`{token}`. "
            f"User intent: {prompt[:200]}. Read graph state, write findings back as nodes/edges. "
            f"Do not wait for other agents — conflicts resolve in the graph."
        ),
    }


def agent_worker(spec: dict[str, Any], rid: str) -> dict[str, Any]:
    """
    One agent slice. All workers share the same .brain graph.
    Writes are atomic; audit chain is flock-serialized.
    """
    t0 = time.perf_counter()
    aid = spec["agent_id"]
    role = spec["role"]
    token = spec["token"]
    os.environ["PRIVATE_BRAIN_AGENT_ID"] = aid
    os.environ["PRIVATE_BRAIN_ROLE"] = role
    os.environ["PRIVATE_BRAIN_RUN_ID"] = rid

    audit("swarm_agent", agent_id=aid, role=role, run_id=rid, result="start", detail=spec["slice"])
    findings: list[dict] = []
    writes = 0
    errors: list[str] = []

    try:
        # --- shared graph READ (everyone can read at once) ---
        if role in ("retriever", "source_scout", "vector_probe", "gap_finder"):
            hits = query(token, limit=8)
            try:
                vhits = search_vectors(token, limit=5)
            except Exception:
                vhits = []
            for h in hits[:6]:
                findings.append(
                    {
                        "id": h.get("id"),
                        "title": h.get("title"),
                        "tier": h.get("tier"),
                        "source": h.get("source"),
                        "via": "lexical",
                    }
                )
            for v in vhits[:4]:
                findings.append(
                    {
                        "id": v.get("id"),
                        "score": v.get("score"),
                        "via": "vector",
                    }
                )

        if role == "tagger":
            # stamp catalog nodes related to token (per-hit soft-fail under concurrent graph writers)
            hits = query(token, limit=5)
            for h in hits[:3]:
                try:
                    nid = f"swarm:tag:{aid}:{h.get('id', '')[:40]}"
                    ingest_node(
                        nid,
                        type="SwarmTag",
                        source="brain",
                        title=f"tag:{token} → {h.get('title')}",
                        tier="T3",
                        tags=["swarm", "tag", token, role],
                        parent_id=h.get("id"),
                        content=f"Agent {aid} tagged node {h.get('id')} for `{token}`",
                        props={"target": h.get("id"), "token": token, "agent": aid},
                        agent_id=aid,
                        role=role,
                    )
                    if h.get("id"):
                        try:
                            ingest_edge(h["id"], "SWARM_TAGGED", nid, agent_id=aid)
                        except Exception as e:
                            errors.append(f"tag_edge:{str(e)[:80]}")
                    writes += 1
                    findings.append({"tagged": h.get("id"), "node": nid})
                except Exception as e:
                    errors.append(f"tag:{str(e)[:80]}")

        if role == "linker":
            hits = query(token, limit=6)
            ids = [h.get("id") for h in hits if h.get("id")]
            for i in range(len(ids) - 1):
                ingest_edge(ids[i], "SWARM_RELATED", ids[i + 1], agent_id=aid)
                writes += 1
            findings.append({"linked_pairs": max(0, len(ids) - 1), "ids": ids[:6]})

        if role == "rater":
            hits = query(token, limit=8)
            gold = sum(1 for h in hits if (h.get("tier") or "") in ("T0", "T1"))
            slag = sum(1 for h in hits if (h.get("tier") or "") == "T3")
            findings.append({"hits": len(hits), "goldish": gold, "t3": slag, "token": token})
            nid = f"swarm:rate:{aid}:{token}"
            ingest_node(
                nid,
                type="SwarmRate",
                source="metrics",
                title=f"swarm rate `{token}` gold={gold} t3={slag}",
                tier="T2",
                tags=["swarm", "rate", token],
                content=json.dumps({"hits": len(hits), "goldish": gold, "t3": slag}),
                props={"token": token, "agent": aid},
                agent_id=aid,
                role=role,
            )
            writes += 1

        if role == "tier_guard":
            hits = query(token, limit=10)
            only_t3 = hits and all((h.get("tier") or "T3") == "T3" for h in hits)
            findings.append({"token": token, "only_t3": only_t3, "n": len(hits)})
            if only_t3:
                nid = f"swarm:gap:tier:{aid}:{token}"
                ingest_node(
                    nid,
                    type="KnowledgeGap",
                    source="brain",
                    title=f"gap: only T3 for `{token}`",
                    tier="T2",
                    tags=["swarm", "gap", token],
                    content=f"Agent {aid} found no T0-T2 for token `{token}`",
                    agent_id=aid,
                    role=role,
                )
                writes += 1

        if role == "gap_finder":
            hits = query(token, limit=3)
            if len(hits) < 2:
                nid = f"swarm:gap:thin:{aid}:{token}"
                ingest_node(
                    nid,
                    type="KnowledgeGap",
                    source="brain",
                    title=f"thin coverage `{token}`",
                    tier="T2",
                    tags=["swarm", "gap", "thin", token],
                    content=f"Agent {aid}: hit_count={len(hits)} for `{token}` under user intent",
                    agent_id=aid,
                    role=role,
                )
                writes += 1
                findings.append({"gap": True, "hits": len(hits)})
            else:
                findings.append({"gap": False, "hits": len(hits)})

        if role == "vector_probe":
            try:
                vhits = search_vectors(token, limit=6)
            except Exception as e:
                vhits = []
                errors.append(str(e)[:80])
            findings.append({"vector_hits": len(vhits), "top": (vhits[0] if vhits else None)})

        if role == "source_scout":
            nodes = load_all_nodes()
            by_src: dict[str, int] = {}
            for n in nodes:
                blob = f"{n.get('id','')} {n.get('title','')}".lower()
                if token in blob:
                    s = n.get("source") or "?"
                    by_src[s] = by_src.get(s, 0) + 1
            findings.append({"token": token, "by_source": by_src})
            nid = f"swarm:scout:{aid}:{token}"
            ingest_node(
                nid,
                type="SwarmScout",
                source="brain",
                title=f"scout `{token}` sources={by_src}",
                tier="T3",
                tags=["swarm", "scout", token],
                content=json.dumps(by_src),
                props={"token": token, "by_source": by_src, "agent": aid},
                agent_id=aid,
                role=role,
            )
            writes += 1

        # always leave a breadcrumb on the shared graph
        crumb = f"swarm:crumb:{rid}:{aid}"
        ingest_node(
            crumb,
            type="SwarmCrumb",
            source="brain",
            title=spec["slice"],
            tier="T3",
            tags=["swarm", "crumb", role, token],
            content=json.dumps({"findings": findings[:12], "mission": spec["mission"][:400]}, ensure_ascii=False)[:8000],
            props={
                "agent_id": aid,
                "role": role,
                "token": token,
                "run_id": rid,
                "writes": writes,
                "finding_count": len(findings),
            },
            agent_id=aid,
            role=role,
        )
        writes += 1
        ok = True
    except Exception as e:
        ok = False
        errors.append(str(e)[:200])
        audit("swarm_agent", agent_id=aid, role=role, run_id=rid, result="fail", detail=str(e)[:160])

    elapsed = int((time.perf_counter() - t0) * 1000)
    if ok:
        audit(
            "swarm_agent",
            agent_id=aid,
            role=role,
            run_id=rid,
            result="ok",
            detail=f"writes={writes} findings={len(findings)} ms={elapsed}",
        )
    return {
        "agent_id": aid,
        "role": role,
        "token": token,
        "ok": ok,
        "writes": writes,
        "findings": findings[:20],
        "errors": errors,
        "elapsed_ms": elapsed,
    }


def decompose(prompt: str, n_agents: int) -> list[dict[str, Any]]:
    """Orchestrator only draws the graph: N slices, no work itself."""
    # Cap 256 — money unconstrained; safety ceiling for process size
    n_agents = max(1, min(256, int(n_agents)))
    toks = _tokens(prompt, n_agents)
    specs = []
    for i in range(n_agents):
        role = AGENT_ROLES[i % len(AGENT_ROLES)]
        specs.append(_slice_prompt(prompt, i, n_agents, toks[i], role))
    return specs


def sweep(
    prompt: str,
    n_agents: int = 32,
    *,
    max_workers: int | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Fan-out N agents onto the shared topological graph simultaneously.
    Fan-in checks expected vs completed (silent failure guard).
    Layered consolidate: per-role batch → global summary node.
    """
    ensure_tree()
    rid = run_id or f"swarm-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    os.environ["PRIVATE_BRAIN_RUN_ID"] = rid
    n_agents = max(1, min(256, int(n_agents or 1)))
    specs = decompose(prompt, n_agents)
    # High concurrency on shared graph; flock on audit/writes keeps integrity
    workers = max(1, int(max_workers or min(n_agents, 64)))
    t0 = time.perf_counter()

    audit(
        "swarm_start",
        agent_id=f"orchestrator-{rid}",
        role="orchestrator",
        run_id=rid,
        result="start",
        detail=f"agents={n_agents} workers={workers}",
        props={"prompt_len": len(prompt), "n_agents": n_agents},
    )

    # --- FAN OUT: all agents at once on shared graph (no queue) ---
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(agent_worker, spec, rid): spec["agent_id"] for spec in specs}
        for fut in as_completed(futs):
            aid = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                results.append(
                    {
                        "agent_id": aid,
                        "ok": False,
                        "error": str(e)[:200],
                        "writes": 0,
                        "findings": [],
                        "errors": [str(e)[:200]],
                        "elapsed_ms": 0,
                    }
                )

    # --- SILENT FAILURE GUARD ---
    expected = len(specs)
    completed = len(results)
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = completed - ok_count
    missing = expected - completed
    gaps = []
    if missing:
        gaps.append(f"missing_results={missing}")
    if fail_count:
        gaps.append(f"failed_agents={fail_count}")

    # --- LAYERED FAN-IN: by role then global ---
    by_role: dict[str, list] = {}
    for r in results:
        by_role.setdefault(r.get("role") or "?", []).append(r)

    role_summaries = {}
    for role, items in by_role.items():
        role_summaries[role] = {
            "n": len(items),
            "ok": sum(1 for i in items if i.get("ok")),
            "writes": sum(int(i.get("writes") or 0) for i in items),
            "tokens": list({i.get("token") for i in items if i.get("token")})[:12],
        }

    total_writes = sum(int(r.get("writes") or 0) for r in results)
    wall_ms = int((time.perf_counter() - t0) * 1000)

    # consolidate node on shared graph
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:10]
    summary_id = f"swarm:summary:{rid}"
    summary_body = {
        "prompt": prompt[:500],
        "n_agents": n_agents,
        "expected": expected,
        "completed": completed,
        "ok": ok_count,
        "failed": fail_count,
        "missing": missing,
        "total_writes": total_writes,
        "wall_ms": wall_ms,
        "by_role": role_summaries,
        "gaps": gaps,
        "graph_engineering": True,
        "shared_topology": True,
        "no_queue": True,
    }
    ingest_node(
        summary_id,
        type="SwarmSummary",
        source="brain",
        title=f"swarm×{n_agents} ok={ok_count}/{expected} writes={total_writes} {wall_ms}ms",
        tier="T1",
        tags=["swarm", "summary", "graph-engineering"],
        content=json.dumps(summary_body, indent=2, ensure_ascii=False)[:20000],
        props={**summary_body, "prompt_hash": digest},
        agent_id=f"orchestrator-{rid}",
        role="orchestrator",
    )

    # link crumbs to summary (sample)
    for r in results[:n_agents]:
        crumb = f"swarm:crumb:{rid}:{r.get('agent_id')}"
        try:
            ingest_edge(summary_id, "HAS_AGENT", crumb, agent_id=f"orchestrator-{rid}")
        except Exception:
            pass

    out = {
        "ok": missing == 0 and fail_count == 0,
        "partial": fail_count > 0 or missing > 0,
        "run_id": rid,
        "prompt": prompt,
        "n_agents": n_agents,
        "workers": workers,
        "expected": expected,
        "completed": completed,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "missing": missing,
        "total_writes": total_writes,
        "wall_ms": wall_ms,
        "by_role": role_summaries,
        "gaps": gaps,
        "summary_node_id": summary_id,
        "agents": [
            {
                "agent_id": r.get("agent_id"),
                "role": r.get("role"),
                "token": r.get("token"),
                "ok": r.get("ok"),
                "writes": r.get("writes"),
                "elapsed_ms": r.get("elapsed_ms"),
                "finding_count": len(r.get("findings") or []),
            }
            for r in sorted(results, key=lambda x: x.get("agent_id") or "")
        ],
        "shared_topology": True,
        "no_queue": True,
        "note": "All agents read/wrote one shared filesystem graph; no per-agent queue.",
    }
    write_json(STATE_DIR / "last_swarm.json", {**out, "ts": utc_now()})
    audit(
        "swarm_complete",
        agent_id=f"orchestrator-{rid}",
        role="orchestrator",
        run_id=rid,
        result="ok" if out["ok"] else "partial",
        detail=f"ok={ok_count}/{expected} writes={total_writes} ms={wall_ms}",
        props={"summary": summary_id, "gaps": gaps},
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Shared-topology multi-agent swarm")
    ap.add_argument("cmd", choices=["sweep", "decompose", "status"])
    ap.add_argument("--prompt", default="status of private brain knowledge graph")
    ap.add_argument("--agents", type=int, default=32)
    ap.add_argument("--workers", type=int, default=0, help="thread pool size (0=min(agents,32))")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ensure_tree()
    if args.cmd == "decompose":
        specs = decompose(args.prompt, args.agents)
        print(json.dumps(specs, indent=2))
        return 0
    if args.cmd == "status":
        p = STATE_DIR / "last_swarm.json"
        print(json.dumps(read_json(p) if p.exists() else {"ok": False, "error": "no last_swarm"}, indent=2, default=str))
        return 0

    workers = args.workers or None
    out = sweep(args.prompt, args.agents, max_workers=workers)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") or out.get("partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
