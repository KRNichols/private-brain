"""LAYER 3 — THE HARNESS.

Runtime every loop and every graph node executes inside. Gives each worker:
  - a clean (empty) context session
  - a small tool bag
  - a spawn budget
  - an isolation boundary (parent grows by RESULT only)

The one rule that makes isolation real: a spawned worker gets a NEW, EMPTY
context. It never inherits the parent's. Heavy material enters the child only;
the parent adds `str(result)` and nothing else.

    Anthropic 69:12 — avoid context pollution; start a new context session
    Anthropic 80:02 — harness hides plumbing so you pick what to spawn
    Anthropic 16:38 — one general tool (grep) beats N bespoke ones
"""
from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any


class BudgetExhausted(RuntimeError):
    pass


@dataclass
class Context:
    """A worker's private window. `.size` is what you'd pay for every turn."""

    messages: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add(self, msg: str) -> None:
        self.messages.append(str(msg))

    @property
    def size(self) -> int:
        return sum(len(m) for m in self.messages)


Tool = Callable[..., Any]
# worker(ctx, tools, task, material) -> small result
Worker = Callable[["Context", dict, str, str], Any]


@dataclass
class Harness:
    tools: dict[str, Tool] = field(default_factory=dict)
    spawn_budget: int = 32
    events: list[str] = field(default_factory=list)
    parent: Context = field(default_factory=Context)
    _spawns: int = 0
    # Optional audit hook: callable(event_dict) — never required
    on_event: Callable[[dict[str, Any]], None] | None = None

    def spawn(self, worker: Worker, task: str, material: str) -> Any:
        """Run worker in a FRESH context. Return only its result to the parent.

        Does NOT pass self.parent into the child. Forking would copy the mess.
        """
        if self._spawns >= self.spawn_budget:
            raise BudgetExhausted(f"spawn budget {self.spawn_budget} exhausted")
        self._spawns += 1
        spawn_n = self._spawns

        child = Context()  # new session — NOT self.parent
        child.add(task)
        child.add(material)  # heavy material enters the CHILD only
        before = self.parent.size
        result = worker(child, self.tools, task, material)
        result_str = _compact_result(result)
        self.parent.add(result_str)  # parent grows by the RESULT only
        delta = self.parent.size - before
        event = (
            f"spawn #{spawn_n}: child_ctx={child.size}B  parent +{delta}B "
            f"({task[:48]})"
        )
        self.events.append(event)
        if self.on_event:
            try:
                self.on_event(
                    {
                        "spawn": spawn_n,
                        "task": task[:120],
                        "child_bytes": child.size,
                        "parent_delta": delta,
                        "result_bytes": len(result_str),
                    }
                )
            except Exception:
                pass
        return result

    def spawn_many(
        self,
        worker: Worker,
        items: list[tuple[str, str]],
        *,
        parallel: bool = False,
        max_workers: int | None = None,
    ) -> list[Any]:
        """Spawn one worker per (task, material). Parallel optional (ThreadPool).

        Sequential by default for deterministic demos. Parallel is the real
        harness job when race conditions matter — each child still gets a
        clean context; only tool side-effects need external locks.
        """
        if not parallel or len(items) <= 1:
            return [self.spawn(worker, task, material) for task, material in items]

        # Parallel: pre-reserve budget slots, run workers, then parent-append results
        n = len(items)
        if self._spawns + n > self.spawn_budget:
            raise BudgetExhausted(
                f"spawn budget {self.spawn_budget} would be exceeded by {n} parallel spawns"
            )
        workers = max_workers or min(8, n)
        results: list[Any] = [None] * n

        def _run(idx: int, task: str, material: str) -> tuple[int, Any, int, str]:
            # Each thread builds its own child context (no parent share).
            child = Context()
            child.add(task)
            child.add(material)
            result = worker(child, self.tools, task, material)
            return idx, result, child.size, task

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [
                ex.submit(_run, i, task, material) for i, (task, material) in enumerate(items)
            ]
            for fut in as_completed(futs):
                idx, result, child_size, task = fut.result()
                results[idx] = result
                self._spawns += 1
                before = self.parent.size
                result_str = _compact_result(result)
                self.parent.add(result_str)
                delta = self.parent.size - before
                self.events.append(
                    f"spawn #{self._spawns}: child_ctx={child_size}B  parent +{delta}B "
                    f"({task[:48]}) [parallel]"
                )
        return results


def _compact_result(result: Any) -> str:
    """Parent should only grow by a small representation of the result."""
    s = str(result)
    if len(s) > 400:
        return s[:380] + f"…(+{len(s) - 380}B)"
    return s


def grep(pattern: str, text: str) -> list[str]:
    """One general tool — not a drawer of bespoke finders."""
    return [ln for ln in text.splitlines() if re.search(pattern, ln)]


def default_tools() -> dict[str, Tool]:
    return {"grep": grep}
