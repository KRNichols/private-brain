#!/usr/bin/env python3
"""Minimal utilities — status / snapshot / query / ingest-gitlab (compat for installers)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from brain_lib import build_snapshot, ensure_tree, query, status


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain thin CLI utilities")
    ap.add_argument("cmd", choices=["status", "snapshot", "query", "ingest-gitlab", "swarm"])
    ap.add_argument("-q", "--text", default=None)
    ap.add_argument("--limit", type=int, default=15)
    # Remaining args (after cmd) are forwarded to gitlab_ingest / agent_swarm
    args, rest = ap.parse_known_args()
    ensure_tree()
    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if args.cmd == "snapshot":
        print(json.dumps(build_snapshot().get("stats", {}), indent=2))
        return 0
    if args.cmd == "query":
        hits = query(args.text, limit=args.limit)
        print(
            json.dumps(
                [
                    {
                        "id": h["id"],
                        "type": h.get("type"),
                        "title": h.get("title"),
                        "tier": h.get("tier"),
                    }
                    for h in hits
                ],
                indent=2,
            )
        )
        return 0
    if args.cmd == "swarm":
        script = Path(__file__).resolve().parent / "agent_swarm.py"
        if not script.exists():
            print("agent_swarm.py missing", file=sys.stderr)
            return 2
        env = os.environ.copy()
        sp = str(script.parent)
        env["PYTHONPATH"] = sp + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        # default: sweep
        fwd = rest if rest and rest[0] in ("sweep", "decompose", "status") else ["sweep", *rest]
        return subprocess.call([sys.executable, str(script), *fwd], env=env)
    # ingest-gitlab → scripts/gitlab_ingest.py (all extra flags forwarded)
    script = Path(__file__).resolve().parent / "gitlab_ingest.py"
    if not script.exists():
        print("gitlab_ingest.py missing next to pb_util.py", file=sys.stderr)
        return 2
    env = os.environ.copy()
    sp = str(script.parent)
    env["PYTHONPATH"] = sp + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.call([sys.executable, str(script), *rest], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
