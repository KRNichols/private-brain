#!/usr/bin/env python3
"""Release-gate adapter — exactly one JSON object; success only when releasable."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from pathlib import Path


def _one_json(obj: dict) -> None:
    """Emit exactly one JSON object (no dual documents)."""
    print(json.dumps(obj, ensure_ascii=True, separators=(",", ":")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-artifact", default="")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    run_id = f"release-{uuid.uuid4().hex[:8]}"
    if args.mock or os.environ.get("PB_LOCAL_RAG_MOCK") == "1":
        _one_json(
            {
                "ok": True,
                "verified": True,
                "releasable": True,
                "violations": 0,
                "run_id": run_id,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        return 0

    art = Path(args.judge_artifact) if args.judge_artifact else None
    if not art or not art.is_file():
        _one_json(
            {
                "ok": False,
                "verified": False,
                "releasable": False,
                "violations": 1,
                "reason": "missing_judge_artifact",
                "run_id": run_id,
            }
        )
        return 1

    raw = art.read_bytes()
    # Path containment: must live under codex home or workspace
    resolved = art.resolve()
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).resolve()
    if ".." in art.as_posix():
        _one_json(
            {
                "ok": False,
                "verified": False,
                "releasable": False,
                "violations": 1,
                "reason": "path_traversal",
                "run_id": run_id,
            }
        )
        return 1

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        _one_json(
            {
                "ok": False,
                "verified": False,
                "releasable": False,
                "violations": 1,
                "reason": f"schema_json:{e}",
                "run_id": run_id,
            }
        )
        return 1

    # Nested judge_output projection
    judge_output = data.get("judge_output") if isinstance(data, dict) else None
    core = data if isinstance(data, dict) else {}
    if isinstance(judge_output, dict):
        # require exact equality of projected core fields when both present
        for k in ("verified", "releasable", "violations"):
            if k in core and k in judge_output and core[k] != judge_output[k]:
                _one_json(
                    {
                        "ok": False,
                        "verified": False,
                        "releasable": False,
                        "violations": 1,
                        "reason": f"nested_mismatch:{k}",
                        "run_id": run_id,
                    }
                )
                return 1
        core = {**core, **judge_output}

    sha = hashlib.sha256(raw).hexdigest()
    verified = bool(core.get("verified", core.get("ok", False)))
    releasable = bool(core.get("releasable", verified))
    violations = int(core.get("violations") or 0)
    ok = verified and releasable and violations == 0
    _one_json(
        {
            "ok": ok,
            "verified": verified,
            "releasable": releasable,
            "violations": violations,
            "artifact_path": str(resolved),
            "sha256": sha,
            "byte_count": len(raw),
            "run_id": run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
