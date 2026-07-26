#!/usr/bin/env python3
"""
Watcher agent runtime (headless).

Polls brain + audit for unlogged mutations and secret-like content.
Writes findings + heartbeats. Air-gapped.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from audit_lib import audit, audit_dir, scan_content_for_secrets, verify_chain
from brain_lib import (
    EDGE_DIR,
    NODE_DIR,
    ensure_tree,
    resolve_brain_root,
    utc_now,
    write_json,
)


def findings_path() -> Path:
    return audit_dir() / "watcher-findings.jsonl"


def status_path() -> Path:
    return resolve_brain_root() / ".brain" / "state" / "watcher_status.json"


def append_finding(finding: dict) -> None:
    p = findings_path()
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(finding, ensure_ascii=False) + "\n")


def snapshot_graph_mtimes() -> dict[str, float]:
    ensure_tree()
    out: dict[str, float] = {}
    for d, prefix in ((NODE_DIR, "node"), (EDGE_DIR, "edge")):
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            out[f"{prefix}:{fp.name}"] = fp.stat().st_mtime
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--agent-id", default="watcher-1")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    ensure_tree()
    audit(
        "agent_start",
        agent_id=args.agent_id,
        role="watcher",
        run_id=args.run_id,
        detail="watcher_loop start",
    )
    prev = snapshot_graph_mtimes()
    prev_audit_size = 0
    apath = audit_dir()
    for fp in apath.glob("events-*.jsonl"):
        prev_audit_size += fp.stat().st_size

    open_findings = 0
    while True:
        now = utc_now()
        cur = snapshot_graph_mtimes()
        changed = [k for k, m in cur.items() if k not in prev or prev[k] != m]
        new_nodes = [k for k in changed if k.startswith("node:")]
        new_edges = [k for k in changed if k.startswith("edge:")]

        audit_size = 0
        for fp in apath.glob("events-*.jsonl"):
            audit_size += fp.stat().st_size
        audit_grew = audit_size > prev_audit_size

        # Heuristic: graph changed but audit did not grow → medium/high finding
        if (new_nodes or new_edges) and not audit_grew:
            finding = {
                "ts": now,
                "severity": "high",
                "code": "unlogged_mutation_suspected",
                "nodes_changed": len(new_nodes),
                "edges_changed": len(new_edges),
                "sample": (new_nodes + new_edges)[:10],
            }
            append_finding(finding)
            open_findings += 1
            audit(
                "watcher_finding",
                agent_id=args.agent_id,
                role="watcher",
                run_id=args.run_id,
                result="flag",
                detail=finding["code"],
                props=finding,
            )

        secrets = scan_content_for_secrets()
        if secrets:
            finding = {
                "ts": now,
                "severity": "high",
                "code": "secret_pattern_in_content",
                "count": len(secrets),
                "sample": secrets[:5],
            }
            append_finding(finding)
            open_findings += 1
            audit(
                "watcher_finding",
                agent_id=args.agent_id,
                role="watcher",
                run_id=args.run_id,
                result="flag",
                detail="secret_pattern_in_content",
                props={"count": len(secrets)},
            )

        chain = verify_chain()
        if not chain.get("ok"):
            finding = {
                "ts": now,
                "severity": "critical",
                "code": "audit_chain_break",
                "errors": chain.get("errors", [])[:5],
            }
            append_finding(finding)
            open_findings += 1
            audit(
                "watcher_finding",
                agent_id=args.agent_id,
                role="watcher",
                run_id=args.run_id,
                result="flag",
                detail="audit_chain_break",
                props={"errors": finding["errors"]},
            )

        write_json(
            status_path(),
            {
                "last_ok": now,
                "agent_id": args.agent_id,
                "open_findings_session": open_findings,
                "graph_objects": len(cur),
                "chain_ok": chain.get("ok"),
                "secret_hits": len(secrets),
            },
        )
        audit(
            "watcher_heartbeat",
            agent_id=args.agent_id,
            role="watcher",
            run_id=args.run_id,
            result="ok",
            detail=f"findings={open_findings} chain_ok={chain.get('ok')}",
        )

        prev = cur
        prev_audit_size = audit_size

        if args.once:
            break
        time.sleep(args.interval)

    audit("agent_end", agent_id=args.agent_id, role="watcher", run_id=args.run_id, detail="watcher_loop end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
