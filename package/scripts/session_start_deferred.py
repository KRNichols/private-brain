#!/usr/bin/env python3
"""Background SessionStart deferred work — never runs inside the Codex hook.

Bounded, best-effort: harvest, light scenario scan, golden refresh.
Does not block Codex startup. Safe to kill.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _brain() -> Path:
    home = Path.home()
    return Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or Path(os.environ.get("CODEX_HOME", home / ".codex")) / "private-brain"
    ).expanduser().resolve()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", default="")
    args = ap.parse_args()
    brain = _brain()
    scripts = brain / "scripts"
    sys.path.insert(0, str(scripts))
    os.environ["PRIVATE_BRAIN_HOME"] = str(brain)
    state = brain / ".brain" / "state"
    state.mkdir(parents=True, exist_ok=True)
    task_id = args.task_id or f"ss-orphan-{int(time.time())}"
    report: dict = {
        "task_id": task_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "steps": [],
        "status": "running",
    }

    def step(name: str, fn) -> None:
        t0 = time.perf_counter()
        try:
            fn()
            report["steps"].append(
                {"name": name, "ok": True, "sec": round(time.perf_counter() - t0, 3)}
            )
        except Exception as e:
            report["steps"].append(
                {
                    "name": name,
                    "ok": False,
                    "sec": round(time.perf_counter() - t0, 3),
                    "error": str(e)[:200],
                }
            )

    def do_harvest() -> None:
        from smart_discover import run_discover_ingest  # type: ignore

        run_discover_ingest(max_files=50, force=False, agent_id="session-start-deferred")

    def do_dag() -> None:
        from orchestrate import dag_boot  # type: ignore

        dag_boot()

    def do_scenario() -> None:
        from scenario_heal import synthesize_all  # type: ignore

        synthesize_all(reason="session_start_deferred")

    def do_golden() -> None:
        from golden_config import write_golden  # type: ignore

        write_golden()

    step("session_harvest", do_harvest)
    step("dag_boot", do_dag)
    step("scenario_heal", do_scenario)
    step("golden_refresh", do_golden)

    report["status"] = "completed"
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = state / "deferred" / f"{task_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (state / "session_start_deferred.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
