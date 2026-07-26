# non_hallucination/

**Anyone:** the wall that stops made-up answers.  
**Senior:** multi-layer cite-or-block.

| Layer | What | Engine |
|-------|------|--------|
| Validate | no evidence → cannot answer as grounded | `orchestrate.stage_validate` |
| Critic | empty / uncited bullets → FAIL / re-route | `orchestrate.stage_critic` |
| Emit | `final_ok` blocked if critic FAIL | `orchestrate.py` |
| Citation gate | message must cite real `node_id`s | `enterprise.citation_gate` |
| Stop hook | Codex Stop → **block** rewrite if uncited | `engine/hooks/stop_validate.py` |
| Quarantine | public hosts demoted / not preferred as truth | `enterprise.quarantine_public_nodes` |

Beast mode (default): wall **on**.  
`stop beast mode` / normal mode: wall **off** for that session only.  
Reopen Codex: wall **on** again.
