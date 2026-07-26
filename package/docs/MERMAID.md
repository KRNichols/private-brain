# Private Brain — Mermaid architecture diagrams
Source of truth extracted from `/Users/kevinnichols/private-brain-codex/README.md`.
Open this file in VS Code / GitHub / any Mermaid preview.

**Deps model:** Core RAG is stdlib. Optional packages (e.g. GodsEye) install from **Corporate Library / Protected Gateway** Corporate Package Index via `PIP_INDEX_URL` — **no prepackaged libraries** in the kit. Missing package → request onboard.

## Where on this machine
| Path | Role |
|------|------|
| `/Users/kevinnichols/private-brain-codex/README.md` | Full README with embedded mermaid (11 diagrams) |
| `~/.codex/private-brain/docs/MERMAID.md` | Diagrams-only (this file, live) |
| `~/private-brain-codex/docs/MERMAID.md` | Kit docs |
| `~/private-brain-codex/package/docs/MERMAID.md` | Package mirror |
| **`docs/LOOP_GRAPH_SOVEREIGN.md`** | **Loop + graph one-pager (US sovereign models only)** |

---

## Loop + Graph Engineering (US sovereign) — master canvas

Mirrors the “How to Master Loop Engineering + Graph Engineering” layout.  
**Worker = gpt-5.1 US sovereign · Planner/Judge = gpt-5.1 high / enterprise-frontier-model.** Full 9-panel breakdown: [`LOOP_GRAPH_SOVEREIGN.md`](./LOOP_GRAPH_SOVEREIGN.md).

```mermaid
flowchart TB
  subgraph HEADER["How to Master Loop + Graph Engineering — Private Brain · US Sovereign only"]
    direction TB
  end

  subgraph R1[" "]
    direction LR
    subgraph P1["① Loop engineering"]
      direction LR
      p[plan] --> a[act] --> o[observe] --> e[evaluate] --> i[improve]
      i -.->|repeat| p
    end
    subgraph P2["② Graph engineering"]
      n[Node] --- ed[Edges]
      n --- at[Attributes]
      n --- mem[Memory]
      n --- ctx[Context]
    end
    subgraph P3["③ Two-model stack"]
      direction TB
      w["WORKER · gpt-5.1 US sovereign<br/>execute · draft · code · iterate"]
      j["PLANNER/JUDGE · gpt-5.1 high · GSS 120B<br/>plan · decompose · critique · decide"]
      w --- j
    end
  end

  subgraph R2[" "]
    direction LR
    subgraph P4["④ Loop patterns"]
      direction TB
      L1["research: ask→search→synthesize→critique→refine"]
      L2["coding: spec→plan→code→test→fix→repeat"]
      L3["ops: monitor→detect→diagnose→act→review"]
    end
    subgraph P5["⑤ Graph patterns"]
      direction TB
      G1["knowledge · dependency · task · memory graphs"]
      G2["ops: ingest · link · retrieve · rank · update · traverse"]
    end
    subgraph P6["⑥ Loop + graph together"]
      le[loop engine] <--> gm[RAG-DAG graph] <--> ta[tools / APIs]
      ta -.->|feedback| le
    end
  end

  subgraph R3[" "]
    direction LR
    subgraph P7["⑦ Workflows"]
      direction TB
      W1["research copilot — judge synthesizes"]
      W2["coding copilot — judge reviews"]
      W3["memory system — graph stores"]
      W4["decision engine — judge picks"]
      W5["monitoring — scripts + judge on hard"]
    end
    subgraph P8["⑧ Practices"]
      direction TB
      good["✓ one loop + one graph · metrics · separate eval · tidy graph"]
      bad["✗ no loop · self-grade · low-quality retrieve · shiny tools"]
    end
    subgraph P9["⑨ Measure + progress"]
      direction TB
      m1["loop: success · latency · iterations"]
      m2["graph: relevance · parity · freshness"]
      m3["path: sandbox→graph→memory→optimize"]
    end
  end

  subgraph E2E["end-to-end — close the loop always"]
    direction LR
    A[Define goal] --> B[Plan<br/>5.1-high / GSS]
    B --> C[Decompose<br/>graph edges]
    C --> D[Execute<br/>5.1 worker]
    D --> E[Observe<br/>metrics · GodsEye]
    E --> F[Evaluate<br/>separate judge]
    F --> G[Update graph<br/>+ memory]
    G --> H[Improve<br/>prompts · heal]
    H --> I[Repeat until stable]
    I -.-> A
  end

  R1 --> R2 --> R3 --> E2E
```

### End-to-end only (clean strip)

```mermaid
flowchart LR
  A[Define goal] --> B[Plan with<br/>gpt-5.1 high / GSS]
  B --> C[Decompose tasks]
  C --> D[Execute with<br/>gpt-5.1 worker]
  D --> E[Observe results]
  E --> F[Evaluate with<br/>separate judge]
  F --> G[Update graph + memory]
  G --> H[Improve prompts / tools]
  H --> I[Repeat until stable]
  I -.-> A
```

### Model stack only

```mermaid
flowchart LR
  subgraph EDGE["Edge · Corporate laptop"]
    E1["gpt-5.1 US sovereign<br/>WORKER — ships fast"]
  end
  subgraph AWS["AWS gov-region-1 when SHIM"]
    A1["enterprise-frontier-model<br/>PLANNER / JUDGE — thinks deep"]
  end
  EDGE -->|"hard tasks · high stakes"| AWS
  AWS -.->|"never self-grade alone"| EDGE
```

---

## Architecture (current)

```mermaid
flowchart TB
  subgraph You["You — zero Python"]
    BM["beastMode · SETUP · UNINSTALL · DAY1"]
  end

  subgraph Approved["Approved package sources — Corporate"]
    Corporate Library["Corporate Library Corporate Package Index"]
    Protected Gateway["Protected Gateway repos"]
    PIP["PIP_INDEX_URL / PIP_TRUSTED_HOST"]
    REQ["Request package onboard if missing"]
    Corporate Library --> PIP
    Protected Gateway --> PIP
    PIP -.-> REQ
  end

  subgraph Host["Codex host"]
    CX["ChatGPT.app → codex CLI"]
  end

  subgraph Edge["AppGate ZTNA"]
    AG["AppGate SDP"]
    SRC["GitLab · Jira · Confluence"]
    AG --> SRC
  end

  subgraph PB["~/.codex/private-brain sideload only"]
    direction TB
    H["hooks SessionStart / Prompt / Stop"]
    O["orchestrate.py concert DAG"]
    SW["agent_swarm shared topology"]
    LGH["LOOP → GRAPH → HARNESS"]
    SD["smart_discover sessions"]
    IB["ingest_bus"]
    IN["gitlab_ingest / ingest_url"]
    IC["internal_crawl_swarm polite multi-agent"]
    VM["vector_manager TF-IDF"]
    G[".brain nodes · edges · vectors"]
    AC["append-only audit chain"]
    ENT["enterprise quarantine · rank_evidence"]
    PUR["corpus purity · report_hash"]
    VAL["validate-enterprise · doctor · sap"]
    COC["config_of_config → DAY1 map"]
    V["vault IDENTITY · projects"]
    GE["GodsEye optional OpenGL free-universe"]
  end

  subgraph AWS["AWS gov-region-1 when enabled"]
    SSM["SSM port-forward → localhost"]
    LLM["GSS 120B · Nova Pro · Nova Mini"]
    RAG["OpenSearch + Neptune dual-write later"]
    SSM --> LLM
  end

  BM --> COC
  COC --> CX
  BM -->|exec -p beast-enterprise| CX
  BM -->|PIP_INDEX_URL from Corporate Library / Protected Gateway| Approved
  Approved -.->|optional pygame/PyOpenGL if in repo| GE
  BM -->|--swarm| SW
  BM -->|--enterprise| ENT
  BM -->|--validate-enterprise| VAL
  BM -->|--day1 / --config-of-config| COC
  BM -->|-GodsEye| GE
  BM -->|-ingestion / crawl| IN
  CX --> H
  H --> O
  O --> SW
  O --> LGH
  O --> SD
  O --> G
  O --> AC
  O --> ENT
  AG --> IN
  SRC --> IN
  IN --> IC
  IC --> IB --> G
  IB --> AC
  SD --> IB
  IB --> VM --> G
  SW --> G
  LGH --> G
  ENT --> G
  ENT --> PUR
  ENT --> AC
  PUR --> AC
  VAL --> SW
  VAL --> ENT
  VAL --> AC
  V --> CX
  GE -.-> G
  O -.-> GE
  CX -.->|PB_LLM_BASE_URL loopback| SSM
  G -.->|future dual-write| RAG
```

## Concert stage graph

```mermaid
flowchart LR
  boot --> swarm{"swarm×N?<br/>PB_SWARM_AGENTS"}
  swarm -->|yes| swarmRun["agent_swarm shared graph"]
  swarm -->|no or LGH on| lgh["LOOP → GRAPH → HARNESS"]
  swarmRun --> wave1
  lgh --> wave1
  subgraph wave1["parallel wave 1"]
    cost
    security
    retrieve
  end
  security -->|chain_break| seal["audit chain seal"] --> security
  retrieve -->|thin| crawl_gap --> retrieve2["retrieve'"]
  wave1 --> wave2
  retrieve2 --> wave2
  subgraph wave2["parallel wave 2"]
    validate
    metrics
  end
  wave2 --> synthesize --> critic --> rate
  rate -->|FAIL/weak or PB_ALWAYS_OPTIMIZE| optimize
  rate -->|SAP_SHIP/PASS| skip_opt["optimize skip"]
  optimize --> emit
  skip_opt --> emit
```

## Runtime path (one question)

```mermaid
sequenceDiagram
  participant U as You
  participant BM as beastMode
  participant CX as codex -p beast
  participant H as hooks
  participant C as concert
  participant SW as swarm xN
  participant LGH as LOOP-GRAPH-HARNESS
  participant G as .brain
  participant AC as audit chain
  participant GE as GodsEye free-universe

  U->>BM: beastMode [-GodsEye] [--swarm N] [--enterprise]
  BM-->>GE: start graph_gl if -GodsEye OpenGL
  BM->>CX: exec codex -p beast or beast-enterprise
  CX->>H: SessionStart
  H->>C: dag_boot + smart_discover
  C->>G: snapshot / incremental sessions
  C->>AC: seal if chain_break
  U->>CX: question
  CX->>H: UserPromptSubmit
  H->>C: dag_concert
  alt PB_SWARM_AGENTS = N
    C->>SW: shared-topology sweep xN
    SW->>G: crumbs / writes
  else LGH default
    C->>LGH: clean-context fan-out packs
    LGH->>G: verified slices only
  end
  C->>G: hybrid TF-IDF + graph walk
  Note over C,G: enterprise demote quarantine / public-oss
  C->>AC: stage + retrieve events
  C-->>GE: stage lights + pathway fire
  C-->>CX: inject evidence pack
  CX-->>U: answer with node_id citations
  Note over GE: free-universe OpenGL · click origin trail · Space LIVE layout
```

## Data plane

```mermaid
flowchart LR
  SS["~/.codex/sessions rollouts"] --> SD[smart_discover]
  GL[GitLab] --> IB[ingest_bus]
  JI[Jira] --> IB
  CF[Confluence] --> IB
  SD --> IB
  IB --> N[".brain/nodes"]
  IB --> E[".brain/edges"]
  IB --> X["embeddings TF-IDF"]
  IB --> A["append-only audit chain"]
  N --> Q{"enterprise?<br/>public host"}
  Q -->|yes| QT["quarantine stamp<br/>enterprise_quarantine"]
  QT --> A
  QT --> PUR["corpus_purity_audit<br/>report_hash"]
  PUR --> A
  Q -->|clean| N
  N --> Snap[brain_snapshot]
  X --> Snap
  Snap --> GE["GodsEye free-universe OpenGL"]
  VA[vault/IDENTITY] --> SK[skills + AGENTS.md]
```

## Architecture (install + runtime)

```mermaid
flowchart TB
  subgraph User["You"]
    S["SETUP / UNINSTALL"]
    B["beastMode flags"]
  end

  subgraph Corporate Library["Corporate Library Corporate Package Index"]
    AF["corporate-package-index.env<br/>PIP_INDEX_URL"]
    DEPS["optional: pygame + PyOpenGL"]
    AF --> DEPS
  end

  subgraph CodexHome["~/.codex"]
    H[hooks.json]
    P["beast / beast-godseye / beast-enterprise"]
    PB[private-brain/]
    SK[skills/private-brain/]
    AG[AGENTS.md]
  end

  subgraph Engine["private-brain engine"]
    Hooks["hooks: SessionStart / UserPromptSubmit / Stop"]
    Concert["orchestrate.py concert DAG"]
    Swarm["agent_swarm · swarm×N"]
    LGH["LOOP → GRAPH → HARNESS"]
    Ingest["gitlab_ingest + ingest_url"]
    Bus[ingest_bus]
    Graph[".brain/ nodes · edges · vectors"]
    Audit["append-only audit chain"]
    Ent["enterprise quarantine · purity report_hash"]
    Val["validate-enterprise multi-agent"]
    Vault["vault/ IDENTITY · projects · distill"]
    GUI["GodsEye free-universe OpenGL / cpu fallback"]
  end

  S --> AF
  S --> PB
  S --> H
  S --> P
  DEPS -.->|GodsEye venv only| GUI
  B --> GUI
  B --> Ingest
  B --> Swarm
  B --> LGH
  B --> Ent
  B --> Val
  B --> Vault
  B -->|exec| Codex[codex CLI]
  Codex --> H
  H --> Hooks
  Hooks --> Concert
  Concert --> Graph
  Concert --> LGH
  Concert --> Audit
  Swarm --> Graph
  LGH --> Graph
  Ingest --> Bus --> Graph
  Bus --> Audit
  Ent --> Graph
  Ent --> Audit
  Val --> Swarm
  Val --> Ent
  Val --> Audit
  Vault -->|--sync-memory| SK
  Vault --> AG
  GUI --> Graph
  Concert --> GUI
```

## Corporate Library / Protected Gateway Corporate Package Index (approved source)

```mermaid
flowchart LR
  ENV["corporate-package-index.env<br/>PIP_INDEX_URL · PIP_TRUSTED_HOST"] --> Corporate Library["Corporate Library Corporate Package Index<br/>approved PyPI remote"]
  Corporate Library --> CORE["Core RAG-DAG / concert / audit / enterprise<br/>stdlib only — no Corporate Package Index required"]
  Corporate Library --> GE["GodsEye free-universe OpenGL<br/>pygame + PyOpenGL + accelerate"]
  GE --> VENV["private-brain venv"]
  CORE --> ENGINE["hooks · orchestrate · swarm · LGH"]
  VENV --> GUI["-GodsEye graph_gl"]
  ENV -.->|PB_PIP_REQUIRE_CORPORATE_INDEX=1| GATE["block public PyPI"]
```

## Enterprise quarantine · purity · multi-agent validate

```mermaid
flowchart TB
  subgraph Quarantine["Enterprise quarantine path"]
    PUB["public-host nodes<br/>gitlab.com · gnome · salsa · apache…"]
    Q["quarantine_public_nodes"]
    STAMP["props.enterprise_quarantine<br/>tags: public-oss · enterprise-quarantine"]
    PUB --> Q --> STAMP
  end

  subgraph Purity["Corpus purity"]
    AUD["corpus_purity_audit"]
    RH["report_hash = SHA-256<br/>counts + host histogram fingerprint"]
    STAMP --> AUD --> RH
  end

  subgraph Validate["validate-enterprise · multi-agent"]
    direction TB
    LINT[lint]
    SW["swarm×N shared topology"]
    CON[concert]
    Q2[quarantine]
    PR["purity×3 · same report_hash"]
    RET[retrieve_hygiene]
    VEC[vector_parity]
    CH["audit chain verify"]
    DOC[doctor]
    SAP[sap_pack]
    LINT --> SW --> CON --> Q2 --> PR --> RET --> VEC --> CH --> DOC --> SAP
  end

  RH --> PR
  STAMP --> Q2
  PR -->|reproducible hash| OUT[".brain/state/validate_enterprise.json"]
  CH --> AC["append-only audit chain"]
  Q --> AC
  AUD --> AC
```

## Doctor

```mermaid
flowchart TB
  subgraph HARNESS["HARNESS — clean-context spawn · tools · budget"]
    subgraph GRAPH["GRAPH — fan-out N workers + adversarial verify"]
      subgraph LOOP["LOOP — gather → act → verify → retry"]
        Gath[gather] --> Act[act] --> Ver["verify rule-based"]
        Ver -->|fail| Gath
        Ver -->|pass| Pack["verified pack only"]
      end
    end
  end
  Concert["concert dag_concert"] --> HARNESS
  Pack --> Main["main agent window<br/>no full graph dump"]
```

## Doctor

```mermaid
flowchart TB
  boot[boot]
  swarm["swarm×N? PB_SWARM_AGENTS>0"]
  lgh["LOOP → GRAPH → HARNESS<br/>clean-context fan-out"]
  cost[cost]
  security[security]
  retrieve[retrieve]
  seal["recovery: seal audit chain"]
  crawl["recovery: crawl_gap"]
  re_ret["retrieve'"]
  validate[validate]
  metrics[metrics]
  synth[synthesize]
  critic[critic]
  re_route["recovery: critic → re-retrieve"]
  rate[rate]
  opt["optimize?"]
  emit[emit context]

  boot --> swarm
  swarm -->|yes| cost
  swarm -->|no / +LGH| lgh
  lgh --> cost
  swarm --> security
  swarm --> retrieve
  lgh --> security
  lgh --> retrieve

  security -->|chain_break| seal --> security
  retrieve -->|gap / thin| crawl --> re_ret
  re_ret --> validate
  re_ret --> metrics
  retrieve --> validate
  retrieve --> metrics
  cost --> validate
  security --> validate

  validate --> synth
  metrics --> synth
  synth --> critic
  critic -->|WEAK/FAIL| re_route --> synth
  critic --> rate
  rate --> opt --> emit
```

## Doctor

```mermaid
flowchart LR
  URL["URL or preset"] --> Root["resolve instance + group root"]
  Root --> Crawl["polite recursive crawl<br/>groups → projects → issues/MRs/wiki/docs"]
  Crawl --> Bus["ingest_bus"]
  Bus --> Nodes[".brain/nodes + edges"]
  Bus --> Vec["TF-IDF vectors"]
  Bus --> Worth["knowledge_worth / tier"]
  Bus --> Audit["append-only audit chain"]
  Nodes --> EntQ{"enterprise + public host?"}
  EntQ -->|yes| Q["quarantine stamp<br/>enterprise_quarantine"]
  Q --> Audit
  Q --> Purity["purity audit → report_hash"]
  Purity --> Audit
  EntQ -->|clean| Nodes
  Nodes --> Snap["brain_snapshot → GodsEye free-universe / status"]
  Vec --> Snap
```

## Multi-source *light* public crawl

```mermaid
flowchart TB
  Note["beastMode --note …"] --> Distill["vault/distill/YYYY-MM-DD.md"]
  Conv["vault/conventions/*.md"] --> Build["build_skill_md"]
  Distill --> Build
  Graph["export high-worth nodes → vault/graph/"] --> Build
  Build --> Skill["~/.codex/skills/private-brain/SKILL.md"]
  Build --> Agents["~/.codex/AGENTS.md marker block"]
  Build --> Ident["vault/IDENTITY.md"]
  Build --> Proj["project PROJECT.md if present"]
```

