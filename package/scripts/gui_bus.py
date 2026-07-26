"""Emit live GUI events as the concert DAG runs (on the fly)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _path() -> Path:
    home = os.environ.get("PRIVATE_BRAIN_HOME")
    if not home:
        codex = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
        home = str(Path(codex) / "private-brain")
    p = Path(home) / ".brain" / "state" / "gui_events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def gui_event(stage: str, status: str, detail: str = "", **props: Any) -> None:
    """Append one live tick for live_gui.py (best-effort, never raises)."""
    try:
        from datetime import datetime, timezone

        line = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stage": stage,
            "status": status,
            "result": status,
            "detail": detail,
            "props": props,
            "run_id": os.environ.get("PRIVATE_BRAIN_RUN_ID"),
        }
        path = _path()
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        # cap file size ~2MB
        if path.stat().st_size > 2_000_000:
            lines = path.read_text(encoding="utf-8").splitlines()[-2000:]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
