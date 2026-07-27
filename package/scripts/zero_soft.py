#!/usr/bin/env python3
"""ZERO SOFT LAW — no optional gates, no fail-but-green, no soft-skip.

PB_ZERO_SOFT defaults to ON in CI (PB_CI=1). Local interactive defaults OFF
unless PB_ZERO_SOFT=1 so Corporate soft-degrade remains usable until secrets.

When ON:
  - hard=False is ignored in CI gates
  - doctor soft_names emptied (except truly env-dependent library index if unset)
  - day1_auto_discover / organism soft-fail becomes hard fail
  - discovery may exit non-zero

Import force_hard() / soft_fail_ok() / doctor_soft_names().
"""
from __future__ import annotations

import os
from typing import Iterable


def zero_soft_enabled() -> bool:
    """ON when PB_ZERO_SOFT truthy, or default ON under PB_CI/GITHUB_ACTIONS."""
    if "PB_ZERO_SOFT" in os.environ:
        v = os.environ.get("PB_ZERO_SOFT", "").strip().lower()
        return v not in ("0", "false", "no", "off", "")
    # CI defaults hard
    if os.environ.get("PB_CI", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() in ("true", "1"):
        return True
    return False


def force_hard(hard: bool = True) -> bool:
    """Return True always when zero-soft law is on."""
    if zero_soft_enabled():
        return True
    return bool(hard)


def soft_fail_ok() -> bool:
    """If False, callers must hard-fail instead of soft-continue."""
    return not zero_soft_enabled()


def doctor_soft_names(base: Iterable[str] | None = None) -> set[str]:
    """Doctor check names allowed to fail without red. Empty under zero-soft
    except corporate_library when no PIP index configured (no secrets yet)."""
    base_set = set(base or ())
    if not zero_soft_enabled():
        return base_set
    # Until Corporate secrets: library index may be unset — keep that one soft.
    # Everything else is hard under zero-soft CI.
    pip = (
        os.environ.get("PIP_INDEX_URL")
        or os.environ.get("PB_PIP_INDEX_URL")
        or os.environ.get("PB_CORPORATE_PIP_INDEX")
        or ""
    ).strip()
    if not pip:
        return {"corporate_library_approved_source", "optional_capabilities"}
    return set()


def enforce_zero_soft_env() -> None:
    """Pin CI/E2E to zero-soft. Call from nuclear / conversation / x10 mains."""
    if "PB_ZERO_SOFT" not in os.environ:
        if os.environ.get("PB_CI") == "1" or os.environ.get("GITHUB_ACTIONS"):
            os.environ["PB_ZERO_SOFT"] = "1"
    os.environ.setdefault("PB_E2E_INSTALL_CODEX", "1")
