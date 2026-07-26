# ROLE: smart-discover

Find Codex corporate workspace artifacts and catalog them as pure knowledge.

Primary tree (Windows Corporate):
  %USERPROFILE%\.codex\sessions\YYYY\MM\DD\rollout-*.jsonl

Also discovers: state_*.sqlite, memories_*.sqlite, logs_*.sqlite, goals_*.sqlite, AGENTS.md

Pipeline per file: classify → ingest → vectorize → rate → label/tag → audit

```bash
python smart_discover.py run --max-files 200
python smart_discover.py full   # + codex exec DAG validation
```
