# GodsEye research pack — visual GraphRAG ops aid

Ingested into the RAG as research nodes. Use for product direction.

## Field themes (X + UX literature)

### GraphRAG (not just pretty graphs)
- Naive RAG: top-k similar chunks — loses multi-hop "why"
- GraphRAG: entities + relationships + traversal → full context path to LLM
- Visual requirement: **show the path**, not only a hairball of nodes

### Agent memory
- RAG ≠ long-term memory; agents need structured evolving graphs (Graphiti-style temporal graphs)
- Multi-agent construction: schema propose/critic loops before bulk extract
- Local-first / inspectable stages beat opaque giant context windows

### Visualization UX (Cambridge Intelligence + dashboard craft)
- Avoid **hairballs**, **snowstorms** (too many same-size points), **starbursts**
- Clarity over complexity: filter, group, expand on demand
- Consistent color language (source = hue, tier = size/brightness)
- Drill-down > dump everything at full opacity
- Overview first (KPIs + status), then graph exploration

### Open-source UI inspirations (public)
- Kotaemon-style: visualize citations, similarity lists, graph deps when answering
- Neo4j Bloom / Surrealist: map modes, queryable graph as product surface
- LlamaIndex GraphRAG demos: subgraph retrieve then answer

## Design rules we apply in GodsEye

1. Source islands + dim cross-source edges (anti-hairball)
2. Tier-scaled node size (anti-snowstorm)
3. Evidence path (E) + neighbor expand (N) + trail walk (GraphRAG path)
4. Concert stages panel = inspectable agent pipeline
5. Vectors + nodes parity on HUD (hybrid health)
6. Legend (L) for community/source orientation
7. Free-universe layout — camera explores, no box clamp

## Security concerns (research → product)

| Risk | Mitigation now | Gap |
|------|----------------|-----|
| Screenshot leaks INTERNAL titles | Local-only GUI; no cloud stream | Need redaction mode for demos |
| Node titles may hold secrets | enterprise secret scan on ingest | GodsEye doesn't re-scan on draw |
| Public OSS mixed in graph | quarantine + retrieve demote | Visual flag for quarantined (todo) |
| Evidence path exposes wrong host | rank_evidence clean-only | Badge on node card if public_oss |
| Side-channel via HUD metrics | low risk | Avoid dumping token contents |
| Dual window / zombie GL | godseye single-window control | Keep restart path |

## Gaps still open

- Quarantine badge color on nodes
- 2–3 hop expand with hop counter
- Dual pane: selected content snippet (redacted)
- Time/run_id scrubber
- Export path JSON / screenshot
- Minimap
- Accessibility: high-contrast mode

## References (themes, not paywalled secrets)
- GraphRAG explainers (entities→traverse→generate)
- Agentic KG construction (schema agents, Neo4j ADK courses)
- Graph viz UX: hairball/snowstorm avoidance, progressive disclosure
