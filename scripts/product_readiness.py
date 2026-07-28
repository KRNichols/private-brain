#!/usr/bin/env python3
"""Canonical structured product readiness — NO heuristic filename scans.

Consumes installed entrypoint paths under CODEX_HOME/local-rag/ only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ENTRYPOINTS = {
    "ask_cli": ("cli", "ask.py"),
    "agent_runner": ("agents", "run_agent.py"),
    "scope_gate_runner": ("agents", "run_scope_citation_gate.py"),
    "release_gate_runner": ("agents", "run_release_gate_workflow.py"),
    "finalize_runner": ("agents", "run_finalize.py"),
    "tui": ("ui", "rag_tui.py"),
    "dashboard": ("ui", "dashboard.py"),
    "mock_provider": ("providers", "mock.py"),
    "sovereign_provider": ("providers", "sovereign.py"),
}


def readiness(codex: Path | None = None) -> dict:
    codex = codex or Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    codex = codex.expanduser().resolve()
    root = codex / "local-rag"
    out: dict = {}
    for key, parts in ENTRYPOINTS.items():
        p = root.joinpath(*parts)
        out[key] = p.is_file()
    out["installer_integration"] = all(
        out[k]
        for k in (
            "ask_cli",
            "agent_runner",
            "scope_gate_runner",
            "release_gate_runner",
            "finalize_runner",
            "tui",
            "dashboard",
            "mock_provider",
            "sovereign_provider",
        )
    )
    out["local_rag_root"] = str(root)
    out["local_rag_root_exists"] = root.is_dir()
    # Prefer installed READINESS.json if present and schema-valid
    snap = root / "READINESS.json"
    if snap.is_file():
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "ask_cli" in data:
                # Re-verify files rather than trust stale true flags
                pass
        except Exception:
            pass
    return out


def main() -> int:
    r = readiness()
    print(json.dumps(r, indent=2))
    # exit 0 even if not ready — diagnostics must not crash; consumers check booleans
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
