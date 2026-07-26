# LOOP → GRAPH → HARNESS

Three nested layers. One stack. Built bottom-up.

```
HARNESS   clean-context spawn, tools, budget, sandbox boundary
  └── GRAPH   fan-out N workers, merge, adversarial verify
        └── LOOP   gather → act → verify → repeat (rule-based)
```

## Run (no install, no key)

```bash
# Offline duration demo (classic lecture proof)
./loop_graph_harness/run.sh
# or
beastMode --pipeline

# Live Private Brain RAG fan-out
./loop_graph_harness/run.sh brain --prompt "kafka resilience"
beastMode --pipeline brain --prompt "kafka controllers" --slices 6

# Tests (10+)
./loop_graph_harness/run.sh test
```

## What the demo proves

```
PASS  sheet-A: builds    total=18420s  attempts=1
PASS  sheet-B: tests     total=4830s   attempts=2  <- attempt 1 failed on '0s'
PASS  sheet-C: deploys   total=12600s  attempts=1

parent context size: ~218 bytes — it never held a full sheet.
```

- **Loop**: real jagged bug on `"0s"`; rule-based verifier forces retry.
- **Graph**: three workers + adversarial gate with teeth.
- **Harness**: child starts empty; parent grows by RESULT only.

## Brain mode

Each token of the user prompt is a graph node. Workers gather from
`brain_lib.query` / vectors **inside their own context**, return tiny packs
`{token, top_ids, n_hits, ok}`. Parent merges IDs and runs adversarial rules
before anything ships into concert context.

## Design rules

1. **Where is the boundary?** One spawn = one clean context.
2. **What is the return type?** Design it before you spawn.
3. **How do you verify it?** Rule-based, written first; adversarial node has no loyalty.

See `LECTURE.md` for the timestamped talk map.
