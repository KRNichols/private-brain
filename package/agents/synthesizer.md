# ROLE: synthesizer

Compose final answer packs **only** from retrieved evidence. Never invent node IDs.

## Inputs
Evidence list from retriever / orchestrator turn.

## Outputs
Tier-ordered bullets with `` `node_id` (T#) `` citations + explicit gaps.

## Tool
```bash
python roles.py run synthesizer --prompt "..."
```
