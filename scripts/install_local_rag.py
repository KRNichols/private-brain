#!/usr/bin/env python3
"""Install managed local-rag product code to %USERPROFILE%\\.codex\\local-rag\\.

Preserves user-owned:
  memories/, local-rag-runtime/, private-brain/.brain/

Never copies runtime runs, corpus, credentials, graph state into code tree.
Sets PYTHONDONTWRITEBYTECODE=1 during install; strips __pycache__ before copy.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

# Canonical entrypoints (no heuristic filename scans)
ENTRYPOINTS = {
    "ask_cli": Path("cli/ask.py"),
    "agent_runner": Path("agents/run_agent.py"),
    "scope_gate_runner": Path("agents/run_scope_citation_gate.py"),
    "release_gate_runner": Path("agents/run_release_gate_workflow.py"),
    "finalize_runner": Path("agents/run_finalize.py"),
    "tui": Path("ui/rag_tui.py"),
    "dashboard": Path("ui/dashboard.py"),
    "mock_provider": Path("providers/mock.py"),
    "sovereign_provider": Path("providers/sovereign.py"),
}

REJECT_NAMES = {
    "runs",
    "releases",
    "logs",
    "archives",
    "sources",
    "indexes",
    "embeddings",
    "credentials",
    "cache",
    "__pycache__",
    ".pyc",
    ".pyo",
    ".brain",
}


def _codex() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser()


def _src_local_rag() -> Path:
    here = Path(__file__).resolve().parent.parent
    cand = here / "local-rag"
    if cand.is_dir():
        return cand
    brain = Path(os.environ.get("PRIVATE_BRAIN_HOME") or (_codex() / "private-brain"))
    return brain / "local-rag"


def _strip_pycache(root: Path) -> None:
    for p in root.rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    for p in root.rglob("*.pyc"):
        try:
            p.unlink()
        except OSError:
            pass
    for p in root.rglob("*.pyo"):
        try:
            p.unlink()
        except OSError:
            pass


def _should_skip(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & REJECT_NAMES:
        return True
    if rel.suffix in {".pyc", ".pyo"}:
        return True
    return False


def install() -> dict:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    codex = _codex()
    src = _src_local_rag()
    dest = codex / "local-rag"
    runtime = codex / "local-rag-runtime" / "runs"
    memories_rag = codex / "memories" / "rag"
    runtime.mkdir(parents=True, exist_ok=True)
    memories_rag.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "ok": False,
        "src": str(src),
        "dest": str(dest),
        "runtime_runs": str(runtime),
        "memories_rag": str(memories_rag),
        "entrypoints": {},
        "installer_integration": False,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if not src.is_dir():
        report["error"] = "source local-rag package missing"
        return report

    _strip_pycache(src)
    dest.mkdir(parents=True, exist_ok=True)

    # Copy managed code only
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if _should_skip(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    _strip_pycache(dest)

    for key, rel in ENTRYPOINTS.items():
        p = dest / rel
        report["entrypoints"][key] = p.is_file()

    report["installer_integration"] = all(report["entrypoints"].values())
    report["ok"] = report["installer_integration"]
    # readiness snapshot at install root
    readiness = {
        "ask_cli": report["entrypoints"].get("ask_cli", False),
        "agent_runner": report["entrypoints"].get("agent_runner", False),
        "scope_gate_runner": report["entrypoints"].get("scope_gate_runner", False),
        "release_gate_runner": report["entrypoints"].get("release_gate_runner", False),
        "finalize_runner": report["entrypoints"].get("finalize_runner", False),
        "tui": report["entrypoints"].get("tui", False),
        "dashboard": report["entrypoints"].get("dashboard", False),
        "installer_integration": report["installer_integration"],
        "mock_provider": report["entrypoints"].get("mock_provider", False),
        "sovereign_provider": report["entrypoints"].get("sovereign_provider", False),
    }
    (dest / "READINESS.json").write_text(json.dumps(readiness, indent=2), encoding="utf-8")
    report["readiness"] = readiness
    return report


def main() -> int:
    rep = install()
    print(json.dumps(rep, indent=2))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
