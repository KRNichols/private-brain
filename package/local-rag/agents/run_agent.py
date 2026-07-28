#!/usr/bin/env python3
"""Bounded local agent runner — declared nodes only, one JSON out, no secret leak."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def _runs_root() -> Path:
    if os.environ.get("PB_LOCAL_RAG_RUNS"):
        return Path(os.environ["PB_LOCAL_RAG_RUNS"]).expanduser().resolve()
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    return (codex / "local-rag-runtime" / "runs").resolve()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="retriever")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--inputs", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    run_id = f"agent-{uuid.uuid4().hex[:10]}"
    runs = _runs_root() / run_id
    runs.mkdir(parents=True, exist_ok=True)

    inputs = {}
    if args.inputs:
        p = Path(args.inputs)
        if p.is_file():
            inputs = json.loads(p.read_text(encoding="utf-8"))

    # Mock path for CI / readiness
    if args.mock or os.environ.get("PB_LOCAL_RAG_MOCK") == "1":
        out = {
            "ok": True,
            "run_id": run_id,
            "role": args.role,
            "prompt_registered": True,
            "process_started": True,
            "process_running": False,
            "process_completed": True,
            "process_failed": False,
            "artifacts": [],
            "inputs_resolved": bool(inputs) or not args.inputs,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    else:
        brain = Path(
            os.environ.get("PRIVATE_BRAIN_HOME")
            or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain"
        )
        sys.path.insert(0, str(brain / "scripts"))
        try:
            from orchestrate import dag_turn  # type: ignore

            res = dag_turn(args.prompt or f"role={args.role}", allow_crawl=False)
            out = {
                "ok": bool(res.get("final_ok", True)),
                "run_id": run_id,
                "role": args.role,
                "prompt_registered": True,
                "process_started": True,
                "process_running": False,
                "process_completed": True,
                "process_failed": False,
                "evidence": (res.get("retrieve") or {}).get("evidence") or [],
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except Exception as e:
            out = {
                "ok": False,
                "run_id": run_id,
                "role": args.role,
                "prompt_registered": True,
                "process_started": False,
                "process_running": False,
                "process_completed": False,
                "process_failed": True,
                "error": str(e)[:300],
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

    (runs / "agent_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2 if args.json else None))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
