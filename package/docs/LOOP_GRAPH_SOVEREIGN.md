# Loop Engineering + Graph Engineering — US Sovereign (Private Brain)

Same structure as the “Master Loop + Graph Engineering” one-pager.  
**Models: OpenAI enterprise / US sovereign only** — no Kimi, no Opus on the work path.

| Diagram role | Sovereign assignment |
|--------------|----------------------|
| Fast worker (ship) | `gpt-5.1` US sovereign (edge) · optional fast enterprise SKU |
| Deep planner / judge | `gpt-5.1` high effort · `enterprise-frontier-model` when AWS SHIM up |

Preview any block in VS Code Mermaid, GitHub, or `mmdc`.

---

## 1 · What loop engineering is

```mermaid
flowchart LR
  subgraph LOOP["① Loop engineering — repeatable cycles"]
    P[plan] --> A[act] --> O[observe] --> E[evaluate] --> I[improve]
    I -.->|repeat| P
  end
  note1["break work into cycles"]
  note2["measure every cycle"]
  note3["optimize for improvement — not one-shot perfection"]
```

**Private Brain:** organism water-pipe + concert + heal ledger + day brief.

---

## 2 · What graph engineering is

```mermaid
flowchart TB
  subgraph GRAPH["② Graph engineering — structured context"]
    N[Node<br/>entity]
    ED[Edges<br/>relationships]
    AT[Attributes<br/>properties]
    M[Memory<br/>past + context]
    C[Context<br/>scope + time]
    N --- ED
    N --- AT
    N --- M
    N --- C
  end
```

**Private Brain:** `.brain` nodes / edges / props / tiers / golden config.

---

## 3 · Two-model stack — who does what (US sovereign only)

```mermaid
flowchart LR
  subgraph WORKER["gpt-5.1 US sovereign · WORKER"]
    W1[fast execution]
    W2[broad exploration]
    W3[drafting and generation]
    W4[coding and tool use]
    W5[iteration and refinement]
  end
  subgraph PLANNER["OpenAI enterprise · PLANNER / JUDGE"]
    P1[planning and strategy]
    P2[decomposition]
    P3[architecture and design]
    P4[critique and evaluation]
    P5[decision-making]
  end
  WORKER -->|"ships fast"| OUT[answer / patch / crawl]
  PLANNER -->|"thinks deep"| OUT
  PLANNER -.->|"never grades own homework alone"| WORKER
```

```text
rule of thumb: gpt-5.1 worker ships fast.
rule of thumb: gpt-5.1-high / enterprise-frontier-model thinks deep.
Corporate: edge sovereign · AWS gov-region-1 GSS when SHIM live.
```

---

## 4 · Core loop patterns that matter

```mermaid
flowchart TB
  subgraph L1["1 research loop"]
    direction LR
    r1[ask] --> r2[search] --> r3[synthesize] --> r4[critique] --> r5[refine]
  end
  subgraph L2["2 coding loop"]
    direction LR
    c1[spec] --> c2[plan] --> c3[code] --> c4[test] --> c5[fix] --> c6[repeat]
  end
  subgraph L3["3 content loop"]
    direction LR
    t1[idea] --> t2[draft] --> t3[edit] --> t4[publish] --> t5[learn]
  end
  subgraph L4["4 ops loop"]
    direction LR
    o1[monitor] --> o2[detect] --> o3[diagnose] --> o4[act] --> o5[review]
  end
```

**Never let a model grade its own homework** — critique / evaluate uses **judge** tier (separate role; GSS when available).

---

## 5 · Core graph patterns that matter

```mermaid
flowchart LR
  subgraph TYPES["graph types"]
    KG[knowledge graph<br/>facts and relations]
    DG[dependency graph<br/>deps and impacts]
    TG[task graph<br/>workflows and steps]
    MG[memory graph<br/>users projects history]
  end
  subgraph OPS["common graph operations"]
    direction TB
    op1[ingest]
    op2[link]
    op3[retrieve]
    op4[rank]
    op5[update]
    op6[traverse]
  end
  TYPES --> OPS
```

**Private Brain:** knowledge + structural nodes; ingest_bus · vector search · origin trails · quarantine rank.

---

## 6 · How loop + graph systems work together

```mermaid
flowchart LR
  LE[loop engine<br/>plan → act → observe<br/>→ evaluate → improve]
  GM[graph memory<br/>RAG-DAG context layer]
  TA[tools / actions<br/>search · code · analyze<br/>store · APIs]
  LE <--> GM
  GM <--> TA
  TA -.->|feedback to next cycle| LE
```

**Private Brain:** hooks + orchestrate + organism + kingdom keys (GitLab/Jira/Confluence/Corporate Package Index/AWS).

---

## 7 · Proper workflows people actually use

```mermaid
flowchart TB
  subgraph WF["⑦ workflows — sovereign model lead"]
    direction TB
    R["research copilot<br/>Planner frames · Worker gathers · Planner synthesizes"]
    C["coding copilot<br/>Planner architecture · Worker code · Planner review/tests"]
    M["agent memory system<br/>Worker acts · Graph stores · Planner evaluates"]
    D["decision engine<br/>Worker drafts · Planner critiques · graph holds options"]
    O["monitoring loop<br/>Worker monitors · Planner diagnoses · scripts fix"]
  end
```

| Workflow | Worker (fast) | Planner / judge (deep) |
|----------|---------------|-------------------------|
| research | crawl / gather | synthesize · cite |
| coding | implement · test | plan · review |
| memory | write nodes | distill · golden |
| decision | options | pick + log |
| monitoring | metrics · heal | hard diagnose |

---

## 8 · Best practices + common mistakes

```mermaid
flowchart LR
  subgraph GOOD["best practices"]
    g1[start with one loop and one graph]
    g2[define success metrics]
    g3[separate execution from evaluation]
    g4[keep graphs tidy — not bloated]
    g5[version prompts schemas memory]
    g6[design for what matters — Corporate pilot]
  end
  subgraph BAD["common mistakes"]
    b1[no real loop — fake feedback]
    b2[overloading tools without clear purpose]
    b3[mixing planning and judging]
    b4[retrieving low-quality context]
    b5[graph with no action path]
    b6[chasing shiny ideas]
  end
```

---

## 9 · What to measure + how to progress

```mermaid
flowchart TB
  subgraph LM["loop metrics"]
    lm1[task success rate]
    lm2[iteration count]
    lm3[improvement per cycle]
    lm4[latency]
    lm5[cost / tokens if metered]
    lm6[eval / cite score]
  end
  subgraph GM2["graph metrics"]
    gm1[retrieval relevance]
    gm2[node / edge quality]
    gm3[freshness]
    gm4[coverage]
    gm5[reasoning usefulness]
  end
  subgraph PATH["4-step learning path"]
    p1[1 build a sandbox loop]
    p2[2 add an initial graph]
    p3[3 attach agent memory]
    p4[4 optimize with metrics and iteration]
  end
  LM --> PATH
  GM2 --> PATH
```

**Private Brain maps:** ops_metrics · fire_drill · purity · godseye fps · stress_rag · day brief.

---

## End-to-end workflow (full bar)

```mermaid
flowchart LR
  A[Define goal] --> B[Plan with<br/>gpt-5.1 high / GSS]
  B --> C[Decompose tasks<br/>graph edges]
  C --> D[Execute with<br/>gpt-5.1 worker]
  D --> E[Observe results<br/>metrics · GodsEye]
  E --> F[Evaluate with<br/>separate judge]
  F --> G[Update graph<br/>+ memory]
  G --> H[Improve prompts<br/>tools · heal ledger]
  H --> I[Repeat until<br/>stable]
  I -.-> A
```

**Close the loop always.** Air-gap: day brief / phase-2 handoff → Grok parent offline (lab only).

---

## Master diagram (one canvas)

```mermaid
flowchart TB
  subgraph TITLE["Private Brain — Loop + Graph Engineering · US Sovereign only"]
    direction TB
  end

  subgraph ONE["① LOOP"]
    direction LR
    p[plan] --> a[act] --> o[observe] --> e[evaluate] --> i[improve]
    i -.-> p
  end

  subgraph TWO["② GRAPH"]
    n[Node] --- ed[Edges]
    n --- at[Attributes]
    n --- mem[Memory]
    n --- ctx[Context]
  end

  subgraph THREE["③ MODELS"]
    direction LR
    w["WORKER<br/>gpt-5.1 sovereign"]
    j["PLANNER / JUDGE<br/>gpt-5.1 high · GSS 120B"]
  end

  subgraph SIX["⑥ SYSTEM"]
    direction LR
    le[loop engine] <--> gm[RAG-DAG] <--> tools[tools · APIs]
  end

  ONE --> SIX
  TWO --> SIX
  THREE --> SIX
  SIX --> E2E

  subgraph E2E["end-to-end"]
    direction LR
    e1[goal] --> e2[plan] --> e3[decompose] --> e4[execute] --> e5[observe] --> e6[evaluate] --> e7[update graph] --> e8[improve] --> e9[repeat]
  end
```

---

## Starter projects (from the diagram)

```mermaid
flowchart LR
  S1["research agent<br/>gather · synthesize · update knowledge graph"]
  S2["code repair agent<br/>plan · fix · test · learn failures"]
  S3["personal knowledge copilot<br/>sessions · vault · queryable memory graph"]
```

| Starter | Private Brain path |
|---------|-------------------|
| Research | concert + crawl + graph |
| Code repair | Codex beast + graph cites |
| Knowledge copilot | sessions ingest + golden + vault |

---

*Source shape: loop/graph one-pager. Model column: OpenAI US sovereign / enterprise only.*
