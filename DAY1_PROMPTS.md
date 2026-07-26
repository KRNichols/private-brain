# Day 1 prompts — paste into Codex in order

Install first (Windows `START.ps1` / Mac `START.command`), then open Codex.

## Checklist

After START: **open Codex** (do not type beast mode — it is already on).  
Check the box after each prompt returns something useful (or a clear refuse/gap).

### Always (do these first)

- [ ] **0 · Auto-discover kingdom (run first after install)**
```text
Map my environment now. Ingest all Codex sessions under .codex.
Find Corporate Library package index and Protected Gateway.
Find Corporate GitLab roots and crawl recursively if token is available.
Find local Neo4j; profile intelligently — do NOT bulk ingest dirty data.
Report what you found, what you ingested, and what is still missing (no secrets).
```


- [ ] **1 · Wake up**
```text
Private Brain is sideloaded. Confirm hooks are live and beast is on.
Short status only: local ready? sessions? any hard fails?
Real readiness only — not agent counts or tokens.
```

- [ ] **2 · Fire drill**
```text
Fire drill. Green or red in plain English.
List any hard fails I must fix before I trust answers.
```

- [ ] **3 · Heal if hurt**
```text
Heal yourself if anything is hurt. Then say only what actually changed.
```

- [ ] **4 · Learn my past work**
```text
Harvest my recent Codex sessions into the brain.
Summarize what you actually ingested (with counts). Do not invent sessions.
```

- [ ] **5 · What do you know about me?**
```text
What do you already know about my active work? Cite node_ids.
If thin, say exactly what is missing — do not invent.
```

- [ ] **6 · Prove non-hallucination**
```text
Answer only from evidence: what is one real thing you can prove about my work right now?
If you cannot prove it, refuse and list the gap. Cite `node_id` or say no evidence.
```

### Optional (only if you have the data)

- [ ] **7 · Dirty Neo4j (profile only — no bulk ingest)**
```text
I have a Neo4j database on this laptop. Data is dirty.
Do NOT bulk ingest yet.
1) What connection inputs do you need (secrets store — never print secrets)?
2) When connected read-only: profile labels, rels, property shapes, sample nodes.
3) Plain English: what is this graph trying to represent?
4) Propose clean schema + keep / quarantine / reject rules.
Stop after the plan. Wait for my GO before ingest.
```

- [ ] **8 · Neo4j GO (only after you approve KEEP)**
```text
GO: ingest only the KEEP set into Private Brain with provenance.
Quarantine weak/public. Reject junk.
Report: kept / quarantined / rejected counts + 5 example node_ids.
Then: what can we prove now that we could not before?
```

- [ ] **9 · PDF plan**
```text
I have a plan PDF at: <FULL_PATH_TO_PDF>
Read it. Table: KEEP | FLAG | REJECT vs Private Brain law
(local RAG-DAG, cite-or-block, no secrets in git, conversation not flags).
Propose Day-1..Day-5 actions from KEEP only. Do not implement the whole plan.
```

- [ ] **10 · Real work query (your domain)**
```text
Using only cited graph evidence: current state of <PROJECT or TICKET or THEME>?
If thin, list exact sources or files to add — do not invent.
```

- [ ] **11 · Monday action list**
```text
Monday action list grounded in evidence we actually have.
Each bullet: action + why + cite. No filler.
```


- [ ] **12 · Golden config + Phase-2 handoff**
```text
Write golden config and prepare phase 2 handoff. Confirm golden_join.json path (no secrets).
```

### Session controls (as needed)

| You say | What happens |
|---------|----------------|
| `stop beast mode` | RAG off this chat only |
| `beast mode` | RAG on again this chat |
| `show GodsEye` | Live graph HUD (if pygame available) |
| `show golden config` | Shared map (when golden exists) |
| `fire drill` | Health check any day |

### Day 1 done when

- [ ] START installed without hard fail  
- [ ] Prompts **1–6** done (or honest gaps)  
- [ ] At least **one useful cited answer** or a clear gap list  
- [ ] You know reopen Codex = beast on again  

**Not done:** agent counts, token burn, pretty graph with no proof.

---
