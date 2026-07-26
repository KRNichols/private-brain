# Private Brain

[![CI](https://github.com/KRNichols/private-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/KRNichols/private-brain/actions/workflows/ci.yml)
[![Windows first-boot](https://github.com/KRNichols/private-brain/actions/workflows/windows-first-boot.yml/badge.svg)](https://github.com/KRNichols/private-brain/actions/workflows/windows-first-boot.yml)
[![Mac first-boot](https://github.com/KRNichols/private-brain/actions/workflows/mac-first-boot.yml/badge.svg)](https://github.com/KRNichols/private-brain/actions/workflows/mac-first-boot.yml)
[![Nuclear Winter](https://github.com/KRNichols/private-brain/actions/workflows/nuclear-winter.yml/badge.svg)](https://github.com/KRNichols/private-brain/actions/workflows/nuclear-winter.yml)
[![Conversation E2E](https://github.com/KRNichols/private-brain/actions/workflows/conversation-e2e.yml/badge.svg)](https://github.com/KRNichols/private-brain/actions/workflows/conversation-e2e.yml)

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

## Example prompts (paste into Codex)

Use these **in order** if you want a guided Day 1. Skip what you don’t have.  
Tell Codex you want **artifacts and outcomes**, not process theater.

### Block 1 — Wake and baseline (always)

```text
Private Brain is sideloaded. Confirm hooks are live and beast is on.
Give me a short status: local brain ready? sessions? purity/quarantine? any hard fails?
I only care about real readiness — not agent counts or token use.
```

```text
Fire drill. Report green/red in plain English and list any hard fails I must fix before trusting answers.
```

```text
Heal yourself if anything is hurt. Then restate only what actually changed.
```

### Block 2 — Learn from my work so far (always useful)

```text
Harvest my recent Codex sessions into the brain. Summarize what topics you actually ingested
(with counts). Do not invent sessions that are not on disk.
```

```text
What do you already know about my active work? Cite node_ids. If thin, say exactly what is missing.
```

```text
Show GodsEye if available. If not, say why and continue headless — I still want graph truth in chat.
```

### Block 3 — Dirty Neo4j (only if you have it)

```text
I have a Neo4j database on this Windows laptop. Data is dirty and incomplete.
Do NOT bulk ingest yet.

1) Tell me what connection inputs you need (URI, auth via secrets store — never print secrets).
2) When connected read-only: profile labels, rel types, property shapes, null rates, sample nodes.
3) In plain English: what is this graph trying to represent?
4) Propose a CLEAN schema mapped to Private Brain entities (Issue/MR/Repo/Page/Person/Chunk/etc).
5) Output keep / quarantine / reject rules for this data.
Stop after the profile + plan. Wait for my go before ingest.
```

```text
Using the Neo4j profile: for each major label family, infer likely source systems
(Jira, GitLab, Confluence, web scrape, unknown). Mark public/web-sourced material for quarantine.
Do not fetch external URLs unless I explicitly allow an allowlisted host.
```

```text
GO: ingest only the KEEP set into Private Brain with provenance.
Quarantine weak/public. Reject junk.
When done: numbers kept / quarantined / rejected, and 5 example node_ids I can query.
Reindex vectors. Then answer: what can we now prove that we could not before?
```

### Block 4 — PDF plan (only if you have the file)

```text
I have a plan PDF at: <FULL_PATH_TO_PDF>
It is NOT set in stone. Read it.

1) Summarize what it claims we should build.
2) Compare to Private Brain best practice (local RAG-DAG, cite-or-block, US sovereign path,
   quarantine public, golden map, conversation not flags).
3) Table: KEEP (aligns) | FLAG (vague/risky) | REJECT (anti-pattern / conflicts with law).
4) Propose concrete Day-1..Day-5 actions from KEEP only.
Do not implement the whole plan. Do not pretend rejected parts are done.
```

```text
From the KEEP rows of the plan: turn them into golden/map notes and ingestible brain nodes
(tier them). Skip REJECT. For FLAG, list questions I must answer before ingest.
```

### Block 5 — Neo4j + PDF together (best Day‑1 “onboarding intelligence”)

```text
You have (or will have) Neo4j profile + plan PDF judgment.
Build one onboarding brief:
- What the dirty graph is good for
- What the plan wants
- Intersection: data we can use NOW to serve the plan
- Gaps: plan wants X but graph has no evidence
- First three queries I should run that produce real work outcomes
No agent theater. No token discussion. Artifacts only.
```

### Block 6 — Real work cooking (replace with your domain)

```text
Using only cited graph evidence: what is the current state of <PROJECT/TICKET/THEME>?
If evidence is thin, list exact sources to crawl or files to add — do not invent.
```

```text
Give me a Monday action list grounded in evidence we actually have.
Each bullet: action + why + cite. No filler.
```

```text
Day brief for offline handoff: what we installed, what the brain knows, hard risks, next actions.
Write the file path when done.
```

### Block 7 — Control surface (as needed)

```text
stop beast mode
```
→ plain Codex this chat only.

```text
beast mode
```
→ RAG back on this chat.

```text
show golden config
```
→ machine map (after golden exists).

```text
add co-worker
```
→ how to emit/join `golden_join.json` (no secrets).

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

---

## Sanitized vocabulary (public)

This public repo uses neutral names only:

| Public term | Meaning |
|-------------|---------|
| **Corporate** | Your organization name |
| **Corporate Library** | Approved internal package repositories |
| **Protected Gateway** | Proxied / protected package gateway |
| **Corporate Package Index** | Approved pip/index URL for optional deps |

No customer-specific names appear in scripts, docs, or kit labels.

---

## What free runners prove

GitHub Actions (ubuntu + windows + macos) abuse free hosted runners for **product contracts**, not just compile:

| Claim | Workflow / test |
|-------|-----------------|
| **Open Codex → beast auto on** | Conversation E2E · SessionStart hook |
| **Answers cite evidence or refuse** | Conversation E2E · citation_gate + Stop hook |
| **`stop beast mode` session-only** | Conversation E2E · UserPromptSubmit + reopen SessionStart |
| **GodsEye + Corporate Library soft/hard** | Conversation E2E · module + package policy |
| **Kit first-boot (Mac/Windows)** | Mac/Windows first-boot · freeze → START → hooks.json |

No Codex Desktop GUI on runners (no app install/login). Hooks + DAG are the same code path Codex calls after sideload. Optional live `codex` CLI later via `PB_E2E_REAL_CODEX=1`.

### Nuclear conversational testing

Every push runs **`scripts/nuclear_conversation_e2e.py`** on ubuntu + windows + macos:

- SessionStart auto-beast · cite-or-refuse Stop gate · multi-turn SimCodex
- stop beast mode / reopen · router (fire drill, GodsEye, golden, doctor)
- orchestrate concert · organism/day1/fire_drill soft · Corporate Library policy
- nested `conversation_e2e` · scripted 5-beat production play

Report: `.brain/state/NUCLEAR_CONVERSATION_E2E.json`

### GodsEye layout

Continuous **live** motion by default (no auto-settle freeze). Space only **pauses**. Opt-in old settle: `PB_GODSEYE_ALLOW_SETTLE=1`.

