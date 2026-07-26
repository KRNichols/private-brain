#!/usr/bin/env python3
"""Heal ledger — self-heal once, remember forever (no thrash loops).

Stores error signatures that were successfully repaired so subsequent boots
do not re-apply destructive or redundant fixes.

  from heal_ledger import should_heal, record_heal, record_fail
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
LEDGER = _ROOT / ".brain" / "state" / "heal_ledger.json"


def _load() -> dict[str, Any]:
    if not LEDGER.exists():
        return {"version": 1, "healed": {}, "failed": {}, "access_repairs": []}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "healed": {}, "failed": {}, "access_repairs": []}


def _save(d: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=2), encoding="utf-8")


def sig(kind: str, detail: str = "") -> str:
    raw = f"{kind}|{detail}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:16]


def should_heal(kind: str, detail: str = "", *, cooldown_s: float = 86400 * 7) -> bool:
    """False if this signature was healed successfully recently."""
    d = _load()
    key = sig(kind, detail)
    ent = (d.get("healed") or {}).get(key)
    if not ent:
        return True
    age = time.time() - float(ent.get("ts_unix") or 0)
    if age < cooldown_s and ent.get("ok"):
        return False
    return True


def record_heal(kind: str, detail: str = "", *, actions: list | None = None) -> None:
    d = _load()
    key = sig(kind, detail)
    d.setdefault("healed", {})[key] = {
        "kind": kind,
        "detail": detail[:200],
        "ok": True,
        "ts_unix": time.time(),
        "actions": actions or [],
    }
    # drop from failed if present
    d.get("failed", {}).pop(key, None)
    _save(d)


def record_fail(kind: str, detail: str = "", *, error: str = "") -> None:
    d = _load()
    key = sig(kind, detail)
    d.setdefault("failed", {})[key] = {
        "kind": kind,
        "detail": detail[:200],
        "error": error[:300],
        "ts_unix": time.time(),
    }
    _save(d)


def record_access_repair(note: str) -> None:
    d = _load()
    d.setdefault("access_repairs", []).append({"ts_unix": time.time(), "note": note[:300]})
    d["access_repairs"] = d["access_repairs"][-50:]
    _save(d)


def summary() -> dict[str, Any]:
    d = _load()
    return {
        "healed_count": len(d.get("healed") or {}),
        "failed_count": len(d.get("failed") or {}),
        "access_repairs": len(d.get("access_repairs") or []),
        "path": str(LEDGER),
    }
