#!/usr/bin/env python3
"""Finalize runner — attach immutable artifacts via workflow_state only."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    run_id = f"finalize-{uuid.uuid4().hex[:8]}"
    if args.mock or os.environ.get("PB_LOCAL_RAG_MOCK") == "1":
        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "finalized": True,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
        )
        return 0

    run_dir = Path(args.run_dir) if args.run_dir else None
    if not run_dir or not run_dir.is_dir():
        print(json.dumps({"ok": False, "run_id": run_id, "reason": "missing_run_dir"}))
        return 1

    state = {
        "ok": True,
        "run_id": run_id,
        "finalized": True,
        "run_dir": str(run_dir.resolve()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (run_dir / "workflow_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
