"""Full pipeline entrypoints for Private Brain.

  demo          — offline duration sheets (classic lecture demo)
  brain         — fan-out token slices against live RAG-DAG
  run_pipeline  — unified CLI used by beastMode --pipeline / --lgh

Parent context never holds full sheets or full node dumps — only result packs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .brain_workers import (
    brain_evidence_rules,
    brain_slice_worker,
    tokenize_prompt,
)
from .demo import run as run_demo
from .graph import GraphResult, adversarial_verify, fan_out
from .harness import Harness, default_tools


def run_brain_pipeline(
    prompt: str,
    *,
    n_slices: int = 4,
    parallel: bool = True,
    limit_per_slice: int = 6,
    spawn_budget: int = 32,
    audit: bool = True,
) -> GraphResult:
    """Fan-out brain slice workers; merge evidence; adversarial verify.

    Heavy graph/vector reads happen inside each child context. Parent sees
    only compact packs + the final verdict.
    """
    # Ensure scripts/ is importable for brain_lib
    pb = Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain")
    ).expanduser()
    scripts = pb / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    if str(pb) not in sys.path:
        sys.path.insert(0, str(pb))

    on_event = None
    if audit:
        try:
            from audit_lib import audit as _audit  # type: ignore

            def on_event(ev: dict) -> None:  # type: ignore[misc]
                _audit(
                    "lgh_spawn",
                    agent_id="lgh",
                    role="harness",
                    result="ok",
                    detail=json.dumps(ev)[:400],
                )
        except Exception:
            on_event = None

    harness = Harness(tools=default_tools(), spawn_budget=spawn_budget, on_event=on_event)
    tokens = tokenize_prompt(prompt, n=n_slices)
    items: list[tuple[str, str]] = []
    for tok in tokens:
        material = json.dumps({"token": tok, "limit": limit_per_slice})
        items.append((f"brain slice: {tok}", material))

    parts = fan_out(
        harness,
        brain_slice_worker,
        items,
        parallel=parallel,
        max_workers=min(8, max(1, n_slices)),
    )

    unique: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if not isinstance(p, dict):
            continue
        for nid in p.get("top_ids") or []:
            if nid and nid not in seen:
                seen.add(nid)
                unique.append(nid)

    slices_ok = sum(1 for p in parts if isinstance(p, dict) and p.get("ok"))
    merged = {
        "prompt": prompt[:200],
        "slices": len(parts),
        "slices_ok": slices_ok,
        "unique_ids": unique[:40],
        "n_unique": len(unique),
        "tokens": tokens,
        "parts": [
            {
                "token": p.get("token"),
                "n_hits": p.get("n_hits"),
                "attempts": p.get("attempts"),
                "ok": p.get("ok"),
                "top_ids": (p.get("top_ids") or [])[:3],
            }
            for p in parts
            if isinstance(p, dict)
        ],
    }

    verified = adversarial_verify(harness, merged, brain_evidence_rules)
    notes = []
    if slices_ok < len(parts):
        notes.append(f"{len(parts) - slices_ok} slices failed")
    if not unique:
        notes.append("no graph hits (empty or cold brain)")

    return GraphResult(
        merged=merged,
        parts=parts,
        verified=verified,
        notes=notes,
        parent_bytes=harness.parent.size,
        events=list(harness.events),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="LOOP → GRAPH → HARNESS pipeline (Private Brain)"
    )
    ap.add_argument(
        "mode",
        nargs="?",
        default="demo",
        choices=["demo", "brain", "test"],
        help="demo=offline sheets; brain=RAG fan-out; test=unittest",
    )
    ap.add_argument("--prompt", default="kafka resilience controllers", help="brain mode prompt")
    ap.add_argument("--slices", type=int, default=4)
    ap.add_argument("--parallel", action="store_true", help="parallel fan-out")
    ap.add_argument("--sequential", action="store_true", help="force sequential")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.mode == "test":
        import unittest

        # tests live next to this package
        root = Path(__file__).resolve().parent
        suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    parallel = bool(args.parallel) and not args.sequential
    t0 = time.perf_counter()

    if args.mode == "demo":
        # demo defaults sequential for deterministic log; --parallel ok
        r = run_demo(parallel=parallel)
        dt = time.perf_counter() - t0
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": r.verified,
                        "mode": "demo",
                        "merged": r.merged,
                        "parts": r.parts,
                        "parent_bytes": r.parent_bytes,
                        "events": r.events,
                        "dt_s": round(dt, 3),
                    },
                    indent=2,
                    default=str,
                )
            )
        return 0 if r.verified else 1

    # brain mode
    if not args.sequential:
        parallel = True  # brain default parallel
    r = run_brain_pipeline(
        args.prompt,
        n_slices=args.slices,
        parallel=parallel,
    )
    dt = time.perf_counter() - t0
    if not args.quiet and not args.json:
        print("LOOP → GRAPH → HARNESS  (brain slices)")
        print(f"  prompt: {args.prompt!r}")
        print(f"  slices: {r.merged.get('slices')} ok={r.merged.get('slices_ok')}")
        print(f"  unique evidence ids: {r.merged.get('n_unique')}")
        for p in r.merged.get("parts") or []:
            tag = "PASS" if p.get("ok") else "FAIL"
            print(
                f"  {tag}  token={p.get('token')!r:16} hits={p.get('n_hits')} "
                f"attempts={p.get('attempts')} tops={p.get('top_ids')}"
            )
        print("\nHARNESS events:")
        for e in r.events:
            print("  " + e)
        print(f"\nADVERSARIAL: {'ACCEPTED' if r.verified else 'REJECTED'}")
        print(f"parent context: {r.parent_bytes} bytes  wall={dt:.2f}s")
        if r.notes:
            print("notes:", "; ".join(r.notes))
    if args.json:
        print(
            json.dumps(
                {
                    "ok": r.verified,
                    "mode": "brain",
                    "merged": r.merged,
                    "parent_bytes": r.parent_bytes,
                    "events": r.events,
                    "notes": r.notes,
                    "dt_s": round(dt, 3),
                },
                indent=2,
                default=str,
            )
        )
    return 0 if r.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
