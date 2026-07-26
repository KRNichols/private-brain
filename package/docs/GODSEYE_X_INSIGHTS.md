# GodsEye roadmap — insights from X (GraphRAG / visual RAG)

Scouted public posts on GraphRAG, agent knowledge graphs, and visual explainability (2025–2026). Mapped to what we ship and what we added.

## What people keep saying

1. **Naive RAG = top-k chunks. GraphRAG = entities + relationships + multi-hop path.**  
   Visuals should show the *path*, not just a hairball.  
   → GodsEye: **E** lights last concert evidence trail; **click** origin trail; **N** 1-hop expand.

2. **Inspectable stages beat bigger context windows.**  
   Pipeline: Documents → Entities → Relationships → Agents → Graph → Answer.  
   → GodsEye already has **CONCERT STAGES** live from `last_dag.json` (boot→swarm→retrieve→…→rate).

3. **Hybrid vector + graph.** Vectors find “looks related”; graph keeps going along edges.  
   → HUD shows **nodes + vectors** parity; filters isolate sources/tiers before you zoom.

4. **Communities / source islands.** Partition graph so zoom-out is readable.  
   → Free-universe **source islands** + **L** legend counts; **F** source filter includes `local`.

5. **Explainable reasoning = show the chain.**  
   → Evidence path (E) + trail walk ([ ]) + selected node card (id/type/source/tier) + rate **band**.

6. **Don’t launder LLM summaries into the graph as ground truth** (LightRAG-style warning).  
   → We still store swarm crumbs as T2/T3; enterprise **rank_evidence** demotes noise; purity quarantine for public hosts.

## Implemented now (this pass)

| Feature | Key / UI |
|---------|----------|
| Evidence path from last concert | **E** |
| Source legend with counts | **L** |
| 1-hop neighbor expand | **N** |
| Quick tier keys | **1–4**, **5** = all |
| Filter includes local/metrics | **F** cycle |
| Rate band on HUD | top bar when concert has rate |
| Help text updated | **H** |

## Next wave (build when you want more “show everything”)

| Idea from field | GodsEye plan |
|-----------------|--------------|
| Community summaries (GraphRAG communities) | Precompute community labels offline; color by community id |
| Multi-hop slider (2–3 hops) | **N** then **N** again with hop counter |
| Provenance strip | Panel: file path / uri / quarantined flag |
| Time scrub | Filter by `created` / concert run_id timeline |
| Dual-pane: graph + retrieved text | Right panel tab: evidence snippets |
| Query → path animation | Pipe concert retrieve hits into animated walk |
| Export screenshot / path JSON | Key **P** write path to `.brain/state/godseye_path.json` |
| Surrealist-style “map mode” | Already free-universe; add minimap inset |

## Not copying blindly

- No requirement for Neo4j GUI to demo — filesystem RAG-DAG + GL is the edge demo  
- No wheels kit / offline prepackage story  
- Enterprise: public OSS stays demoted/quarantined in the picture too (filter + tier)

## Sources (public X themes)

GraphRAG explainers (entities→traverse→LLM), agentic KG construction courses, Neo4j/LlamaIndex GraphRAG intros, hybrid vector+graph retrieval, “show the path not just chunks,” community partitioning, inspectable multi-agent pipelines.
