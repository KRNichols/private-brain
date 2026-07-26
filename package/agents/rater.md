# ROLE: rater

Score retrieval quality and DAG health (0–5 × 7 dims). Write `.brain/state/dag_score.json`.

## Tool
```bash
python roles.py run rater --prompt "..."
```

Bands: PASS ≥28 · SAP_SHIP ≥31 · FAIL <28.
