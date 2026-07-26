#!/usr/bin/env python3
"""ZERO SOFT LAW — no optional gates, no fail-but-green, no soft-skip.

PB_ZERO_SOFT defaults to ON (1). Set PB_ZERO_SOFT=0 only for local debug
(never in CI). When ON:
  - hard=False is ignored — every failed gate increments FAIL
  - SOFT status is abolished
  - exit helpers return non-zero if any gate failed

Import and use force_hard() at the top of gate() implementations, or
call enforce_zero_soft_env() in main().
"""
from __future__ import annotations

import os


def zero_soft_enabled() -> bool:
    """Default ON. Only explicit 0/false/off disables (local debug)."""
    v = os.environ.get("PB_ZERO_SOFT", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def force_hard(hard: bool = True) -> bool:
    """Return True always when zero-soft law is on."""
    if zero_soft_enabled():
        return True
    return bool(hard)


def enforce_zero_soft_env() -> None:
    """Pin CI/E2E to zero-soft. Call from nuclear / conversation / x10 mains."""
    if "PB_ZERO_SOFT" not in os.environ:
        os.environ["PB_ZERO_SOFT"] = "1"
    # Companion: install loops already hard; ban real-codex soft-skip forever
    os.environ.setdefault("PB_E2E_INSTALL_CODEX", "1")
