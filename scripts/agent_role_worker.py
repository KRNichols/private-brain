#!/usr/bin/env python3
"""Background worker for spawn_agent.ps1 roles (Windows/Codex).

Runs crawl/retrieve/audit work for a single role, then exits.
Never blocks Codex hooks — launched via Start-Process only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_SCRIPTS.parent))


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain role worker")
    ap.add_argument("--role", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--scope-json", default="{}")
    args = ap.parse_args()

    os.environ["PRIVATE_BRAIN_AGENT_ID"] = args.agent_id
    os.environ["PRIVATE_BRAIN_ROLE"] = args.role
    os.environ["PRIVATE_BRAIN_RUN_ID"] = args.run_id

    try:
        scope = json.loads(args.scope_json or "{}")
    except json.JSONDecodeError:
        scope = {}

    try:
        from audit_lib import audit

        audit(
            "worker_start",
            agent_id=args.agent_id,
            role=args.role,
            run_id=args.run_id,
            result="ok",
            detail=json.dumps(scope)[:400],
        )
    except Exception as e:
        print(f"audit start fail: {e}", file=sys.stderr)

    t0 = time.perf_counter()
    result: dict = {"role": args.role, "ok": True}

    try:
        if args.role.startswith("gitlab"):
            url = scope.get("url") or scope.get("gitlab") or os.environ.get("PB_GITLAB_URL")
            if url:
                from crawl_public import crawl_gitlab
                from urllib.parse import urlparse

                u = urlparse(url)
                instance = f"{u.scheme}://{u.netloc}"
                group = (u.path or "").strip("/") or scope.get("group") or ""
                max_p = int(scope.get("max_projects") or 5)
                if group:
                    result["counts"] = crawl_gitlab(
                        instance,
                        group,
                        max_p,
                        int(scope.get("max_mrs") or 5),
                        agent_id=args.agent_id,
                        run_id=args.run_id,
                    )
                else:
                    result["ok"] = False
                    result["error"] = "gitlab scope missing group path"
            else:
                result["note"] = "no gitlab url in scope — registered only"
        elif args.role.startswith("jira"):
            url = scope.get("url") or scope.get("jira") or os.environ.get("PB_JIRA_URL")
            if url:
                from crawl_public import crawl_jira

                result["counts"] = crawl_jira(
                    url.rstrip("/"),
                    int(scope.get("max_projects") or 5),
                    int(scope.get("max_issues") or 20),
                    agent_id=args.agent_id,
                    run_id=args.run_id,
                )
            else:
                result["note"] = "no jira url"
        elif args.role.startswith("confluence"):
            url = scope.get("url") or scope.get("confluence") or os.environ.get("PB_CONFLUENCE_URL")
            if url:
                from crawl_public import crawl_confluence

                result["counts"] = crawl_confluence(
                    url.rstrip("/"),
                    int(scope.get("max_spaces") or 3),
                    int(scope.get("max_pages") or 20),
                    agent_id=args.agent_id,
                    run_id=args.run_id,
                )
            else:
                result["note"] = "no confluence url"
        elif args.role in ("retriever", "graph-writer", "auditor"):
            from brain_lib import query

            q = scope.get("query") or scope.get("token") or "status"
            hits = query(q, limit=8)
            result["hits"] = len(hits)
            result["ids"] = [h.get("id") for h in hits[:8] if isinstance(h, dict)]
        elif args.role == "visualizer":
            # Flags only — no GUI from worker unless PB_GODSEYE_FORCE
            if os.environ.get("PB_GODSEYE_FORCE") == "1":
                import godseye as ge

                result["godseye"] = ge.ensure_gui(force=True)
            else:
                result["note"] = "visualizer: set PB_GODSEYE_FORCE=1 to launch GUI"
        else:
            result["note"] = f"role {args.role}: heartbeat only"
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)[:400]

    result["ms"] = int((time.perf_counter() - t0) * 1000)
    try:
        from audit_lib import audit

        audit(
            "worker_done",
            agent_id=args.agent_id,
            role=args.role,
            run_id=args.run_id,
            result="ok" if result.get("ok") else "fail",
            detail=json.dumps(result)[:500],
        )
    except Exception:
        pass

    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
