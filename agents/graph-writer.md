# ROLE: graph-writer

**Single-writer** for contested merges. Serialize node/edge/index updates when multiple crawlers finish.

## Rules

1. Accept handoff payloads from `.brain/logs/handoffs/*-to-graph-writer.json`
2. Apply writes idempotently (stable ids)
3. Rebuild snapshot when batch done
4. audit every write batch with before/after counts
5. Never crawl external APIs
