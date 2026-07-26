"""LAYER 1 — THE LOOP.

One worker, three parts: gather context, take action, verify the work. It repeats
until a program (the verifier) says the work is done, or a budget runs out and it
ships nothing.

Discipline: the verifier is written BEFORE the action. The loop cannot advance
past a check a human (or a plain rule) wrote first. Failures become the next
attempt's context — the loop closes on that string, not on vibes.

    Anthropic masterclass 22:20 — gather, act, verify
    Anthropic 68:01 — best verification is rule-based
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Report:
    """Verifier answer. Failure text becomes the next attempt's context."""

    passed: bool
    failures: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


# act(material, prior_failures) -> candidate
Action = Callable[[str, list[str]], Any]
# verify(candidate) -> Report
Verifier = Callable[[Any], Report]


@dataclass
class LoopResult:
    accepted: bool
    value: Any = None
    attempts: int = 0
    log: list[str] = field(default_factory=list)


def run_loop(
    material: str,
    act: Action,
    verify: Verifier,
    max_attempts: int = 5,
) -> LoopResult:
    """gather → act → verify → repeat. Fails closed: no verified result, no ship."""
    failures: list[str] = []
    log: list[str] = []
    for attempt in range(1, max_attempts + 1):
        candidate = act(material, failures)  # ACT — sees prior failures as context
        report = verify(candidate)  # VERIFY — rule-based, written first
        if report.passed:
            log.append(f"attempt {attempt}: PASS")
            return LoopResult(True, candidate, attempt, log)
        failures = list(report.failures)  # failure text IS the next context
        log.append(f"attempt {attempt}: FAIL ({'; '.join(report.failures)[:80]})")
    return LoopResult(False, None, max_attempts, log)
