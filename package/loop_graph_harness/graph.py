"""LAYER 2 — THE GRAPH.

Several loop-workers, fanned out and back. Each node IS a loop; the graph is
only the wiring. Design the return type before you spawn — the parent's
context grows by exactly that return value.

Ends with an adversarial checker in a fresh context: sees the artifact only,
has no loyalty to how it was made.

    Anthropic 79:12 — multiple read sub-agents on sheet one/two/three
    Anthropic 67:25 — adversarial, no sympathetic relationship to the work
    Anthropic 69:04 — sub-agents check the work of the main agent
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .harness import Context, Harness, Worker


@dataclass
class GraphResult:
    merged: Any
    parts: list[Any]
    verified: bool
    notes: list[str] = field(default_factory=list)
    parent_bytes: int = 0
    events: list[str] = field(default_factory=list)


def fan_out(
    harness: Harness,
    worker: Worker,
    items: list[tuple[str, str]],
    *,
    parallel: bool = False,
    max_workers: int | None = None,
) -> list[Any]:
    """One loop-worker per (task, material). Each runs in its own clean context."""
    return harness.spawn_many(
        worker, items, parallel=parallel, max_workers=max_workers
    )


def adversarial_verify(
    harness: Harness,
    artifact: Any,
    rules: Callable[[Any], list[str]],
) -> bool:
    """Checker in a FRESH context that only sees the artifact + rules.

    Never sees how the artifact was produced — nothing to defend.
    """

    def checker(ctx: Context, tools: dict, task: str, material: str) -> str:
        broken = rules(artifact)
        if broken:
            return "REJECT: " + "; ".join(broken)
        return "ACCEPT"

    verdict = harness.spawn(
        checker,
        task="adversarially verify the merged result",
        material=repr(artifact)[:2000],
    )
    return str(verdict).startswith("ACCEPT")


def merge_parts(
    parts: list[Any],
    *,
    key: str = "total",
    ok_key: str = "ok",
) -> dict[str, Any]:
    """Default numeric merge for demo-style parts. Brain workers use their own."""
    ok_parts = [p for p in parts if isinstance(p, dict) and p.get(ok_key)]
    total = sum(int(p.get(key) or 0) for p in ok_parts)
    return {
        "grand_total": total,
        "parts_ok": len(ok_parts),
        "parts_total": len(parts),
    }
