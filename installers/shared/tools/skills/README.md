# skills/

**Anyone:** specialized helpers (retriever, auditor, synthesizer, …) the swarm can run.  
**Senior:** agent role cards + Codex agent toml under the engine.

| Path in engine | Role |
|----------------|------|
| `engine/agents/*.md` | Role cards (retriever, critic peers, gitlab/jira deep, …) |
| `engine/codex-agents/*.toml` | Codex multi-agent definitions |
| `engine/scripts/agent_swarm.py` | Swarm orchestration (capped, shared graph) |

Skills do **not** invent facts alone — intelligence + non_hallucination still gate answers.
