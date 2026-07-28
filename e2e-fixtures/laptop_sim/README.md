# Laptop sim fixtures (data only — not product)

Used by `scripts/laptop_sim_harness.py` to reproduce developer-issues scenarios
in an isolated `CODEX_HOME` without AppGate, without mutating production install,
and without soft-pass branches in hooks.

| File | Purpose |
|------|---------|
| `donut_page_body.md` | Synthetic Confluence body for page 633240886 |
| `last_dag_evidence.json` | last_dag-shaped retrieve evidence |
| `current_evidence.json` | Stop handoff evidence bundle |
| `neo_exports_missing_paths.json` | LocalExport nodes without approved_relative_path |
| `neo_exports_with_paths.json` | LocalExport nodes with approved_relative_path |

Never ship corporate secrets or real internal hosts here.
