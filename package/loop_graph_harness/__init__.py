"""LOOP → GRAPH → HARNESS — one stack, three nested layers.

Built bottom-up (and run offline):

  HARNESS   clean-context spawn, tools, spawn budget, sandbox boundary
    └── GRAPH   fan-out N loop-workers, merge, adversarial verify
          └── LOOP   gather → act → verify → repeat until rule-based pass

Reference: github.com/Archive228/loop-graph-harness (ArchiveExplorer lecture).
Private Brain wires this into concert/swarm so heavy graph slices never land
in the main agent window — only verified RESULT dicts do.
"""
from __future__ import annotations

from .graph import GraphResult, adversarial_verify, fan_out, merge_parts
from .harness import BudgetExhausted, Context, Harness, default_tools, grep
from .loop import LoopResult, Report, run_loop

__all__ = [
    "BudgetExhausted",
    "Context",
    "GraphResult",
    "Harness",
    "LoopResult",
    "Report",
    "adversarial_verify",
    "default_tools",
    "fan_out",
    "grep",
    "merge_parts",
    "run_loop",
]

__version__ = "1.0.0"
