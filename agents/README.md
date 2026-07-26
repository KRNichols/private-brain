# Agent system prompts (one prompt per spawn role)

Every spawned agent gets **exactly one** role prompt from this directory plus the shared `../beast-mode.md` air-gap / beast constraints.

| File | Role |
|------|------|
| `orchestrator.md` | Main Codex session — plans DAG, spawns workers, merges results |
| `gitlab-topo.md` | Enumerate nested groups / projects |
| `gitlab-deep.md` | Branches, MRs, comments for assigned projects |
| `jira-topo.md` | Jira projects index |
| `jira-deep.md` | Issues, comments, links |
| `confluence-topo.md` | Spaces + page trees |
| `confluence-deep.md` | Page bodies, labels, comments |
| `graph-writer.md` | Single-writer consistency for `.brain` |
| `retriever.md` | Query-time subgraph assembly only |
| `visualizer.md` | Keep OpenGL graph honest |
| `watcher.md` | **Audit sentinel** — watches all agents, enforces logging, flags anomalies |
| `auditor.md` | Offline / on-demand audit pack for Coverity & SAP review |

Spawn rule (orchestrator):

1. Pick role file.
2. Inject role prompt as the worker's developer/system instructions.
3. Pass a unique `run_id` + `agent_id`.
4. Require every tool/shell action to go through audit log (`scripts/audit_lib.py` / `audit_verify.py`).
5. Watcher is spawned at session boot and stays alive for the session.
