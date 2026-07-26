"""Classic offline demo — three duration sheets through LOOP/GRAPH/HARNESS.

Run:  python -m loop_graph_harness.demo
      or  ./loop_graph_harness/run.sh

No API key, no network. Sheet-B contains "0s" so attempt 1 fails for real.
"""
from __future__ import annotations

from .graph import GraphResult, adversarial_verify, fan_out
from .harness import Harness, default_tools
from .workers import sum_sheet_worker

# Sheet B contains "0s" — the jagged edge lives here.
SHEETS = {
    "sheet-A: builds": "1h52m\n30m\n2h\n45m",
    "sheet-B: tests": "15m\n0s\n1h05m\n30s",
    "sheet-C: deploys": "3h\n20m\n10m",
}


def run(*, parallel: bool = False) -> GraphResult:
    harness = Harness(tools=default_tools(), spawn_budget=16)

    # LAYER 2 — GRAPH: fan out one loop-worker per sheet
    items = [(f"sum sheet: {name}", body) for name, body in SHEETS.items()]
    parts = fan_out(harness, sum_sheet_worker, items, parallel=parallel)

    total = sum(int(p["total"]) for p in parts if p.get("ok") and p.get("total") is not None)
    merged = {"grand_total_seconds": total, "sheets": len(parts)}

    def rules(artifact: dict) -> list[str]:
        bad: list[str] = []
        if artifact.get("grand_total_seconds", 0) <= 0:
            bad.append("non-positive grand total")
        if artifact.get("sheets") != len(SHEETS):
            bad.append("sheet count mismatch")
        return bad

    verified = adversarial_verify(harness, merged, rules)

    print("LOOP results (one worker per sheet):")
    for p in parts:
        tag = "PASS" if p.get("ok") else "FAIL"
        note = "  <- attempt 1 failed on '0s', loop retried" if int(p.get("attempts") or 0) > 1 else ""
        print(
            f"  {tag}  {p.get('sheet')!s:20} total={p.get('total')}s  "
            f"attempts={p.get('attempts')}{note}"
        )

    print("\nHARNESS event log (parent context grows by RESULTS, not by sheets):")
    for e in harness.events:
        print("  " + e)

    print(f"\nGRAPH merge: {merged}")
    print(f"ADVERSARIAL verify (fresh context): {'ACCEPTED' if verified else 'REJECTED'}")
    print(
        f"\nparent (main-agent) context size: {harness.parent.size} bytes "
        "— it never held a full sheet."
    )

    return GraphResult(
        merged=merged,
        parts=parts,
        verified=verified,
        parent_bytes=harness.parent.size,
        events=list(harness.events),
    )


if __name__ == "__main__":
    result = run()
    raise SystemExit(0 if result.verified else 1)
