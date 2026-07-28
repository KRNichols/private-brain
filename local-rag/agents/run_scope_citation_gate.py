#!/usr/bin/env python3
"""Scope + citation gate — one JSON object, immutable artifact attach."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    evidence = []
    if args.evidence and Path(args.evidence).is_file():
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        if isinstance(evidence, dict):
            evidence = evidence.get("evidence") or []

    if args.mock or os.environ.get("PB_LOCAL_RAG_MOCK") == "1":
        out = {
            "ok": True,
            "gate": "scope_citation",
            "cited": ["mock:node:1"],
            "reason": "ok",
            "run_id": f"scope-{uuid.uuid4().hex[:8]}",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        print(json.dumps(out))
        return 0

    brain = Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain"
    )
    sys.path.insert(0, str(brain / "scripts"))
    from enterprise import citation_gate  # type: ignore

    gate = citation_gate(args.message, evidence if isinstance(evidence, list) else [])
    out = {
        "ok": bool(gate.get("ok")),
        "gate": "scope_citation",
        "cited": gate.get("cited") or [],
        "missing": gate.get("missing") or [],
        "reason": gate.get("reason"),
        "run_id": f"scope-{uuid.uuid4().hex[:8]}",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(json.dumps(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
