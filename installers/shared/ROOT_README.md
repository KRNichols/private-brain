# Private Brain

**Codex sideload.** Install once. Open Codex. Talk.  
**Goal: real results only** — not agent counts, not token theater.

Mac ≡ Windows.  
Corporate `golden_join.json` (no secrets) goes in `tools/install/` when you have it.

**Picture of the system:** [`DIAGRAM.md`](./DIAGRAM.md)

---

## Day 1 checklist (Windows work laptop)

Print this. Check boxes as you go.

### 0 · Prep

- [ ] Codex / ChatGPT Desktop with Codex is installed  
- [ ] You have **`PrivateBrain-WINDOWS-READY.zip`** (or CORPORATE zip → open **`windows/`**)  
- [ ] **Quit Codex completely**  
- [ ] Optional: USB/copy of dirty Neo4j access notes (URI only — **tokens later in secrets store**)  
- [ ] Optional: PDF plan file path on disk (local)  
- [ ] Optional: real `golden_join.json` from a co-worker (no secrets) → put in `tools\install\`

### 1 · Unzip — root must look like this

```text
README.md      ← this file
DIAGRAM.md     ← one picture
tools\         ← install + engine + planes
```

- [ ] Root is **only** those three (no random package dump)

### 2 · Install once (PowerShell)

```powershell
cd <path-to-extracted-folder>
Set-ExecutionPolicy -Scope Process Bypass
.\tools\install\START.ps1
```

- [ ] START finishes **without red fail-closed error**  
- [ ] If asked for package route and you don’t know → **headless** is fine for Day 1  
- [ ] Missing Corporate Library/AWS/Jira is **soft** — local brain still works  

**Mac:** `./tools/install/START.command` (same checklist).

### 3 · Open Codex and cook (no shell parade)

- [ ] Open **Codex** (normal app)  
- [ ] **Do not** type `beast mode` — it is **already on** every open  
- [ ] Paste prompts from **Example prompts** below in order  

### 4 · Prove memory + non-hallucination (real results)

- [ ] Ask something about **your** work that should hit sessions/graph  
- [ ] Answer either **cites evidence** or **refuses / says gap** — not free invent  
- [ ] Optional: `fire drill` → want healthy/green language, not vibes  

### 5 · Optional Day‑1 intelligence tracks (when data exists)

**Only if you have them on this laptop:**

| Track | You have… | Goal |
|-------|-----------|------|
| **A. Sessions** | Past Codex chats | Brain learns what you already did |
| **B. Neo4j** | Dirty graph DB | Profile → clean schema → keep/quarantine/reject → ingest **good only** |
| **C. PDF plan** | Plan/requirements PDF | Read plan → keep best practice, flag/shitcan bad parts |
| **D. Kingdom** | GitLab/Jira/Confluence URLs + tokens in **secrets store** | Real internal crawl later — not Day 1 mandatory |

- [ ] Ran at least **one** of A–C with a concrete output (report, ingest count, or refuse list)  
- [ ] Did **not** bulk-trust dirty Neo4j without a keep/reject pass  

### 6 · End of Day 1 “done” definition

You are done when **all** of these are true:

- [ ] START installed once without hard fail  
- [ ] Codex opens and brain is on without a daily launcher  
- [ ] You got **at least one useful answer** grounded in local evidence **or** a clear gap list  
- [ ] If Neo4j/PDF used: you have a **keep / quarantine / reject** outcome, not a blind dump  
- [ ] You know: `stop beast mode` = pause RAG this chat; reopen Codex = on again  

**Not** Day 1 success: “spun 64 agents” / “burned tokens” / “pretty graph with no proof.”

---

## Day 1 prompt checklist (paste into Codex in order)

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

## What success looks like (your bar)

| Good | Ignore |
|------|--------|
| Evidence-backed answers or honest gaps | Agent count, swarm size |
| Keep/quarantine/reject from dirty Neo4j | “Ingested everything” |
| Plan KEEP actions you can run Monday | PDF chapter regurgitation |
| Fire drill / doctor hard-green or listed fixes | Token burn reports |
| Files written (brief, profile, schema) | Process poetry |

---

## Every day after Day 1

1. Open **Codex**  
2. Talk  
3. Optional: `stop beast mode` if you want plain Codex this session  
4. Reopen Codex → brain **on** again  

Shell `beastMode` is a power tool only — not the daily path.

---

## Layout (so you know where things hide)

```text
README.md          ← Day 1 checklist + prompts (you are here)
DIAGRAM.md         ← system picture
tools/
  install/         ← START.ps1 / START.command (run once)
  engine/          ← sideload code → %USERPROFILE%\.codex\private-brain
  intelligence/    ← RAG-DAG / future Neo4j sense notes
  non_hallucination/ ← cite-or-block wall
  judging/         ← fire drill / doctor
  …                ← see tools/README.md
```

**Never email tokens.** Secrets → secrets store only after install.

---

## If something is red

| Symptom | Do |
|---------|-----|
| START fail-closed | Read the red line; fix Python 3.10+ / path; re-run START |
| Codex ignores brain | Confirm install wrote hooks; fully quit and reopen Codex |
| Invented answers | Stay in beast; demand cites; run fire drill |
| Neo4j unknown | Stay on profile-only until you approve KEEP set |
| No golden yet | Headless/local is fine; drop `golden_join.json` later |

Day 1 is successful when **work got smarter with proof**, not when the graph looked busy.
