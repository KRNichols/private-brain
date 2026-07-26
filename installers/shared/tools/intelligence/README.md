# intelligence/

**Anyone:** the brain that remembers work and packs context into Codex.  
**Senior:** filesystem RAG-DAG + concert stages + model routing.

| Piece | Engine |
|-------|--------|
| Concert / DAG | `engine/scripts/orchestrate.py` |
| Retrieve / rank | enterprise rank_evidence · vector_manager |
| Vectors | `engine/scripts/vector_manager.py` (tfidf default) |
| Models | `engine/config/model_routing.json` · US sovereign intent |
| Loop+graph law | `engine/docs/LOOP_GRAPH_SOVEREIGN.md` (after install: live docs) |

Flow: **retrieve → validate → synthesize → critic → rate → emit**.
