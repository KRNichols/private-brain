"""Demo workers — honest jagged edge on duration strings.

Task: sum a "sheet" of durations ("1h52m", "30m", "0s", ...).
Attempt 1 uses a parser correct on every input a person would try — and
genuinely raises on "0s". The rule-based verifier catches it; the loop retries
with a boring, total parser.

    Karpathy 10:35 — models are "jagged": peak on obvious, rough on edges
Nothing here is faked. The failure is real.
"""
from __future__ import annotations

import re

from .harness import Context
from .loop import Report, run_loop

_SCALE = {"h": 3600, "m": 60, "s": 1}


def _parse_v1(text: str) -> int:
    """Attempt 1. Bulletproof on 1h52m, 30m, 2h, 45s. Dies on '0s'."""
    text = text.strip().lower()
    h = re.search(r"(\d+)h", text)
    m = re.search(r"(\d+)m", text)
    s = re.search(r"(\d+)s", text)
    hours = int(h.group(1)) if h else 0
    mins = int(m.group(1)) if m else 0
    secs = int(s.group(1)) if s else 0
    if hours or mins or secs:  # "0s" → 0 or 0 or 0 → False
        return hours * 3600 + mins * 60 + secs
    return int(text)  # int("0s") raises — jagged


def _parse_v2(text: str) -> int:
    """Attempt 2. Boring and total."""
    parts = re.findall(r"(\d+)([hms])", text.strip().lower())
    if not parts:
        raise ValueError(f"not a duration: {text!r}")
    return sum(int(amount) * _SCALE[unit] for amount, unit in parts)


def sum_sheet_worker(ctx: Context, tools: dict, task: str, material: str) -> dict:
    """Loop-worker inside its own clean ctx. Returns a tiny dict, not the sheet."""
    lines = tools["grep"](r"\d+[hms]", material)
    ctx.add(f"gathered {len(lines)} lines")

    # Verifier written BEFORE we choose a parser — it IS the spec.
    def verify(candidate: dict) -> Report:
        fails: list[str] = []
        if candidate.get("error"):
            fails.append(str(candidate["error"]))
        elif candidate.get("total", 0) < 0:
            fails.append("negative total")
        elif candidate.get("count") != len(lines):
            fails.append("did not parse every line")
        return Report(not fails, fails)

    def act(sheet: str, prior_failures: list[str]) -> dict:
        parse = _parse_v1 if not prior_failures else _parse_v2
        try:
            total = sum(parse(ln.strip()) for ln in lines)
            return {"total": total, "count": len(lines)}
        except Exception as exc:  # noqa: BLE001 — feed to verifier
            return {"total": 0, "count": 0, "error": f"{type(exc).__name__}: {exc}"}

    result = run_loop(material, act, verify, max_attempts=3)
    name = task.split(":", 1)[-1].strip() or "sheet"
    if not result.accepted:
        return {"sheet": name, "total": None, "attempts": result.attempts, "ok": False}
    return {
        "sheet": name,
        "total": result.value["total"],  # type: ignore[index]
        "attempts": result.attempts,
        "ok": True,
    }
