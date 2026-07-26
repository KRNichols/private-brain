"""Tests pin the PIPELINE, not incidental numbers.

  - loop fails attempt 1 on "0s" and recovers (not faked)
  - harness never leaks a full sheet into parent
  - adversarial gate can reject a bad merge
  - brain pipeline returns structured packs (when brain available)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# package root = parent of tests/
PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parent  # private-brain
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from loop_graph_harness.demo import SHEETS, run
from loop_graph_harness.graph import adversarial_verify, fan_out
from loop_graph_harness.harness import (
    BudgetExhausted,
    Harness,
    default_tools,
)
from loop_graph_harness.loop import Report, run_loop
from loop_graph_harness.workers import (
    _parse_v1,
    _parse_v2,
    sum_sheet_worker,
)


class TestLoop(unittest.TestCase):
    def test_jagged_bug_is_real(self):
        self.assertEqual(_parse_v1("1h52m"), 6720)
        self.assertEqual(_parse_v1("45s"), 45)
        with self.assertRaises(ValueError):
            _parse_v1("0s")
        self.assertEqual(_parse_v2("0s"), 0)

    def test_loop_recovers_from_failure(self):
        calls = {"n": 0}

        def act(material, prior_failures):
            calls["n"] += 1
            return "good" if prior_failures else "bad"

        def verify(c):
            return Report(c == "good", [] if c == "good" else ["not good"])

        r = run_loop("m", act, verify, max_attempts=3)
        self.assertTrue(r.accepted)
        self.assertEqual(r.attempts, 2)

    def test_loop_fails_closed(self):
        r = run_loop(
            "m",
            lambda mat, f: "bad",
            lambda c: Report(False, ["nope"]),
            max_attempts=3,
        )
        self.assertFalse(r.accepted)
        self.assertIsNone(r.value)


class TestHarness(unittest.TestCase):
    def test_child_context_is_not_forked_from_parent(self):
        h = Harness(tools=default_tools())
        h.parent.add("X" * 5000)
        seen = {}

        def worker(ctx, tools, task, material):
            seen["child_has_parent_data"] = any("XXXX" in m for m in ctx.messages)
            return "tiny"

        h.spawn(worker, "t", "big material " * 100)
        self.assertFalse(seen["child_has_parent_data"])

    def test_parent_grows_by_result_not_material(self):
        h = Harness(tools=default_tools())
        before = h.parent.size
        big = "line\n" * 10000
        h.spawn(lambda ctx, t, task, mat: {"ok": 1}, "t", big)
        self.assertLess(h.parent.size - before, 100)

    def test_spawn_budget_enforced(self):
        h = Harness(tools=default_tools(), spawn_budget=2)
        w = lambda ctx, t, task, mat: 1
        h.spawn(w, "a", "m")
        h.spawn(w, "b", "m")
        with self.assertRaises(BudgetExhausted):
            h.spawn(w, "c", "m")


class TestGraph(unittest.TestCase):
    def test_adversarial_verifier_rejects_bad_artifact(self):
        h = Harness(tools=default_tools())
        ok = adversarial_verify(
            h,
            {"grand_total_seconds": 10, "sheets": 3},
            lambda a: [] if a["grand_total_seconds"] > 0 else ["neg"],
        )
        self.assertTrue(ok)
        bad = adversarial_verify(
            h,
            {"grand_total_seconds": -1, "sheets": 3},
            lambda a: [] if a["grand_total_seconds"] > 0 else ["neg"],
        )
        self.assertFalse(bad)

    def test_fan_out_one_result_per_item(self):
        h = Harness(tools=default_tools())
        items = [(f"sum sheet: {n}", b) for n, b in SHEETS.items()]
        parts = fan_out(h, sum_sheet_worker, items)
        self.assertEqual(len(parts), len(SHEETS))
        self.assertTrue(all(p["ok"] for p in parts))


class TestEndToEnd(unittest.TestCase):
    def test_pipeline_runs_and_verifies(self):
        r = run()
        self.assertTrue(r.verified)
        self.assertEqual(r.merged["sheets"], 3)
        b = next(p for p in r.parts if "sheet-B" in p["sheet"])
        self.assertGreater(b["attempts"], 1)

    def test_parent_stays_tiny(self):
        r = run()
        # three sheets + adversarial → parent still under 1KB
        self.assertLess(r.parent_bytes, 1000)


class TestBrainPipeline(unittest.TestCase):
    def test_brain_pipeline_structure(self):
        from loop_graph_harness.pipeline import run_brain_pipeline

        r = run_brain_pipeline("kafka controllers", n_slices=3, parallel=False, audit=False)
        self.assertIsInstance(r.merged, dict)
        self.assertIn("unique_ids", r.merged)
        self.assertIn("slices", r.merged)
        # adversarial rules accept structural packs even if empty graph
        self.assertTrue(r.verified)
        self.assertLess(r.parent_bytes, 8000)


if __name__ == "__main__":
    unittest.main()
