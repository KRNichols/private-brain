# ROLE: retriever

Answer-time subgraph assembly only. No crawls unless orchestrator explicitly expands scope.

## Protocol

1. Parse query
2. `brain_lib.query` (+ edge expansion 1–2 hops) or `orchestrate.py turn`
3. Rank T0>T1>T2>T3
4. Return structured evidence bundle (node cards + chunk excerpts + ids)
5. audit `retrieve` with query hash (not raw secrets) and hit ids

If miss: handoff to orchestrator with `gap` object — do not freestyle deep crawl.
