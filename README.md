# Private Brain

**Codex sideload.** Download your OS zip → install once → open Codex → talk.

Mac ≡ Windows. Real results only (cite-or-block). Not agent theater.

| | Download | Install |
|--|----------|---------|
| **Windows** | [PrivateBrain-WINDOWS-READY.zip](https://github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-WINDOWS-READY.zip) | Unzip → `tools\install\START.ps1` |
| **Mac** | [PrivateBrain-MAC-READY.zip](https://github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-MAC-READY.zip) | Unzip → `./tools/install/START.command` |

**Full one-pager:** [`DOWNLOAD.md`](./DOWNLOAD.md) · **Picture:** [`DIAGRAM.md`](./DIAGRAM.md) · **Teach GPT 5.6 / Codex the release:** [`ChatGPT56info.md`](./ChatGPT56info.md)

---

## Windows (copy/paste)

```powershell
# 1) Download WINDOWS-READY zip from Releases (link above)
# 2) Unzip. Quit Codex completely.
cd <path-to-extracted-folder>
Set-ExecutionPolicy -Scope Process Bypass
.\tools\install\START.ps1
# 3) Open Codex. Talk. Beast is already on.
# Pause: say "stop beast mode"  ·  Reopen Codex → on again
```

## Mac (copy/paste)

```bash
# 1) Download MAC-READY zip from Releases (link above)
# 2) Unzip. Quit Codex completely.
cd <path-to-extracted-folder>
chmod +x tools/install/START.command
./tools/install/START.command
# 3) Open Codex. Talk. Same as Windows.
```

## After install — done means

- START finished without hard fail  
- Codex opens with beast on (no daily shell launcher)  
- Answers **cite evidence** or **refuse** — not free invent  
- `stop beast mode` pauses this session only  

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


- [ ] **12 · Golden config + Phase-2 handoff**
```text
Write golden config and golden_join.json (no secrets).
Confirm paths for GOLDEN_CONFIG.md, golden_config.json, golden_join.json.
Prepare Phase-2 handoff pack for parent AI. List what is complete vs gaps.
Do not invent Corporate hosts or tokens.
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

## Day 1 install detail (optional)

### Prep
- Codex / ChatGPT Desktop with Codex installed  
- Your OS READY zip from [Releases](https://github.com/KRNichols/private-brain/releases/latest)  
- Quit Codex before START  

### Unzip root (only this)

```text
README.md
DIAGRAM.md
tools/     (or tools\ on Windows)
```

### Install
- **Windows:** `tools\install\START.ps1`  
- **Mac:** `tools/install/START.command`  

Missing Corporate Library / AWS is **soft** — local brain still works.  
Optional: drop `golden_join.json` (no secrets) in `tools/install/`.

---

## What this repo is (developers)

| Path | Who cares |
|------|-----------|
| **Releases · READY zips** | **You** (install) |
| `scripts/` `hooks/` | Developers / CI |
| `installers/mac` `installers/windows` | Kit sources for freeze |
| `package/` | Engine payload frozen into kits |
| `.github/workflows/` | CI (do not use to install) |

**Do not clone this repo to install.** Use the Windows/Mac zip.

CI: [Actions](https://github.com/KRNichols/private-brain/actions) · Nuclear Winter / first-boot prove freeze → START → hooks.

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

No Codex Desktop GUI on runners (no app install/login). Hooks + DAG are the same code path Codex calls after sideload. Free runners **install and hard-smoke** the real `codex` CLI (`npm i -g @openai/codex`) — soft-skip banned. Live agent `codex exec` is optional via `PB_E2E_CODEX_EXEC=1` when auth secrets are present.

### Nuclear conversational testing

Every push runs **`scripts/nuclear_conversation_e2e.py`** on ubuntu + windows + macos:

- SessionStart auto-beast · cite-or-refuse Stop gate · multi-turn SimCodex
- stop beast mode / reopen · router (fire drill, GodsEye, golden, doctor)
- orchestrate concert · organism/day1/fire_drill soft · Corporate Library policy
- nested `conversation_e2e` · scripted 5-beat production play

Report: `.brain/state/NUCLEAR_CONVERSATION_E2E.json`

### GodsEye layout

Continuous **live** motion by default (no auto-settle freeze). Space only **pauses**. Opt-in old settle: `PB_GODSEYE_ALLOW_SETTLE=1`.

### RAG-DAG on runners

Yes — free runners execute the **real** multi-agent DAG:

`scripts/rag_dag_e2e.py` → `orchestrate.py concert` (boot → retrieve → validate → synthesize → critic → …)
plus Codex hooks `UserPromptSubmit` → `dag_turn` and `Stop` → `citation_gate`.

No OpenAI key required for hook/DAG stages (local graph retrieve + rules). Real `codex` CLI binary is hard-required on Nuclear Conversation E2E runners. Live LLM `exec` is optional via `PB_E2E_CODEX_EXEC=1`.

### CI force-feed (public OSS)

Nuclear Winter runs `scripts/ci_force_feed_public.py` on free runners with **real** public data:

| Source | Default target |
|--------|----------------|
| GitLab | gitlab.com / gitlab-org (bounded) |
| GitHub | cli/cli or octocat (bounded) |
| Jira | issues.apache.org/jira |
| Confluence | cwiki.apache.org/confluence |

Tiny limits for CI time. On failure: beast heal + retry. Report: `.brain/state/CI_FORCE_FEED_PUBLIC.json`.

### Coverage judge (every package line)

CI runs `scripts/judge_package_coverage.py` on the runner:

1. **py_compile** every `scripts/*.py` + hooks  
2. **Import** every module under `coverage.py`  
3. **CLI --help** smoke for argparse entrypoints  
4. **Functional** brain_lib + citation_gate  
5. **Optional full** (`PB_COVERAGE_FULL=1`): kingdom + rag_dag e2e under coverage  

Fails if critical modules stay at **0%** or mean coverage &lt; `PB_COVERAGE_MIN` (default 15, ratchet up).  
Report: `.brain/state/PACKAGE_COVERAGE_JUDGE.json`

