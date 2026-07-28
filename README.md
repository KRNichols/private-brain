# Private Brain

**Codex sideload.** Download your OS zip → install once → open Codex → talk.

Mac ≡ Windows. Real results only (cite-or-block). Not agent theater.

| | Download | Install |
|--|----------|---------|
| **Windows** | [PrivateBrain-WINDOWS-READY.zip](https://github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-WINDOWS-READY.zip) | Unzip → `tools\install\START.ps1` |
| **Mac** | [PrivateBrain-MAC-READY.zip](https://github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-MAC-READY.zip) | Unzip → `./tools/install/START.command` |

**Full one-pager:** [`DOWNLOAD.md`](./DOWNLOAD.md) · **Picture:** [`DIAGRAM.md`](./DIAGRAM.md) · **Teach GPT 5.6 / Codex the release:** [`ChatGPT56info.md`](./ChatGPT56info.md)

**Laptop closeout / test pack (browser GPT 5.6 + Codex 5.1):** see [§ Ready to test — developer issues closeout](#ready-to-test--developer-issues-closeout) below.

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

---

## Ready to test — developer issues closeout

This section is the **test plan + orchestration brief** after the developer-issues handoff work.  
**Pin:** Windows Release MVP green on `windows-ready-364093e` (or newer `windows-ready-*` on [Releases](https://github.com/KRNichols/private-brain/releases)).

### 10× readiness audit (what “ready to test” means)

**Shipped and CI-proven (do not re-litigate in chat):**

| Area | Proof |
|------|--------|
| Permanent Windows `.cmd` hook wrappers | `install_hooks.py` → `pb-session-start.cmd` / `pb-user-prompt-submit.cmd` / `pb-stop-validate.cmd` |
| SessionStart / UPS under timeout | Fast path + deferred work; MVP gates `session_start_under_budget`, `ups_under_budget` |
| Stop: ops acks + current evidence | Beast/normal acks continue; uncited source claims block; cited Confluence continues |
| `config.toml` managed keys before tables | `merge_codex_config._prepend_managed_before_first_table` |
| GodsEye machine-readable status | `godseye.py status --json` (enabled, dismissed, pids, alive, backend, capability, last_error, last_started_at) |
| local-rag product surface | `%USERPROFILE%\.codex\local-rag\` via `install_local_rag.py` + `product_readiness.py` |
| Canonical diagnostic | `e2e_status_report.py` (read-only; doctor for vectors — no path guesses) |
| Neo4J path recon honesty | `neoj_path_reconcile.py` — no `preserved_verified` without `approved_relative_path` |
| Short pages always chunk | `brain_lib.write_node` + `confluence_page_rechunk.py` |
| `programs.yaml` contract | `config/programs.yaml` present |
| Nuclear / zero-fail on Windows CI | Windows Release MVP **success** + READY zip mint |

**Still laptop / AppGate only (test will discover; code cannot invent):**

| Residual | Honest expectation |
|----------|-------------------|
| Live `confluence:page:633240886` chunks | Needs local content or AppGate ingest; rechunk tool fixes empty `chunk_ids` when body exists |
| GodsEye GUI process | `enabled=true` + `alive_count=0` is valid until explicit `godseye.py start` |
| Full program metadata on every node | Schema file exists; not every historical node is backfilled |
| Corporate hosts/tokens | Heal/ask once — never invent |

**Ready to test on the golden Windows laptop when:** latest READY zip is installed, Codex **0.144.x** is present, **Windows Release MVP is green for that SHA**, and you can run PowerShell + paste outputs into a **browser** GPT 5.6 thread (5.6 does **not** run inside Codex CLI).

### Laptop sim (no AppGate, no real `~/.codex`, no product debt)

Isolated fixture harness reproduces developer-issues gates with synthetic graph data only:

```bash
# from repo root (CI also runs this inside Windows Release MVP)
python scripts/laptop_sim_harness.py
# report: e2e-reports/LAPTOP_SIM.json  ·  home: .codex-sim/run-*
```

| What it proves | How |
|----------------|-----|
| `.cmd` wrappers + local-rag install | `install_hooks` / `install_local_rag` in temp home |
| SessionStart / UPS budgets | Pipe JSON into hooks; wall-clock gates |
| Stop ops + cite + report evidence | Fixture `current_evidence` / `last_dag` |
| Donut page chunks + rechunk empty→filled | Local `write_node` + `confluence_page_rechunk` |
| GodsEye enabled, not running (honest) | Flag file + `status --json` |
| Neo path false-positive | Fixture LocalExport without `approved_relative_path` |
| Retrieve donut without network crawl | `dag_turn(..., allow_crawl=False)` |

Does **not** replace one real Windows laptop pass with AppGate. Does **not** soft-pass. Does **not** write into your real Codex home (refuses `~/.codex` unless `PB_LAPTOP_SIM_ALLOW_REAL_HOME=1`).

---

### Roles (do not confuse)

| Who | Where | Does | Does **not** |
|-----|--------|------|----------------|
| **GPT 5.6 software manager** | **Web browser chat only** | Plan, score pastes, sequence next step, write Codex prompts | Run PowerShell, open files, call Codex |
| **Human** | Laptop | Run PowerShell / open Codex / paste results into the browser thread | — |
| **Codex + GPT 5.1** | Codex CLI on laptop | Install repair, execute tools, local code under `PRIVATE_BRAIN_HOME` | Declare green without evidence |

**Law:** zero soft-pass. No invented hosts, tokens, or graph state. Prefer read-only evidence first.

---

### GPT 5.6 (browser) — operating pattern

Every 5.6 reply should look like:

```text
STATUS: gathering | installing | testing | blocked | ready for architect
HAVE: <evidence already pasted>
NEED: <one next artifact>
ACTION FOR KEVIN:
  [PowerShell] <one block>   OR   [Codex] <one prompt to paste into Codex CLI>
COPY BACK: <exactly what to paste into this browser chat>
```

Rules for 5.6:

- One primary action per turn.
- Never claim a command ran unless the human pasted output.
- Prefer PowerShell evidence first; Codex only after path baseline exists.
- Quote failing lines; map to the score table below.
- Do not start GodsEye from hooks; do not delete audit/state to “heal.”

**Optional custom instruction (paste into ChatGPT / 5.6 settings):**

> I am a browser-only software manager for Private Brain. I do not execute code. I give Kevin one PowerShell block or one Codex CLI prompt at a time, score pasted outputs against hard gates (hooks `.cmd` wrappers, SessionStart/UPS budget, Stop ops+cites, local-rag readiness, GodsEye JSON, neo recon, e2e_status, donut chunks), ban soft-pass, and produce a compact evidence handoff. I never invent laptop state.

---

### Phase A — Evidence pack (human runs in PowerShell)

Manager tells Kevin: *open PowerShell, run this entire block, paste everything from `EVIDENCE_DIR=` onward (or the listed files).*

```powershell
$ErrorActionPreference = "Continue"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$out = Join-Path $env:USERPROFILE "Desktop\pb-evidence-$ts"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$Brain = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME } else { Join-Path $CodexHome "private-brain" }
$env:CODEX_HOME = $CodexHome
$env:PRIVATE_BRAIN_HOME = $Brain
$env:PYTHONPATH = Join-Path $Brain "scripts"

$PyExe = Join-Path $Brain "venv\Scripts\python.exe"
if (-not (Test-Path $PyExe)) { $PyExe = "python" }

function Run-Save($name, [scriptblock]$sb) {
  $path = Join-Path $out $name
  Write-Host "`n=== $name ===" -ForegroundColor Cyan
  try { $text = & $sb 2>&1 | Out-String } catch { $text = $_ | Out-String }
  $text | Tee-Object -FilePath $path | Out-Host
}

Run-Save "00-env.txt" {
  "CODEX_HOME=$CodexHome"
  "PRIVATE_BRAIN_HOME=$Brain"
  "PY=$PyExe"
  "codex=$(try { (codex --version 2>&1 | Out-String).Trim() } catch { 'missing' })"
  "python=$(& $PyExe --version 2>&1)"
}

Run-Save "01-hooks-head.txt" {
  $hj = Join-Path $CodexHome "hooks.json"
  if (Test-Path $hj) { Get-Content $hj -Raw } else { "MISSING hooks.json" }
  Get-ChildItem (Join-Path $Brain "hooks") -ErrorAction SilentlyContinue |
    Format-Table Name, Length -AutoSize | Out-String
}

Run-Save "02-hook-smoke.txt" {
  $ss = Join-Path $Brain "hooks\session_start.py"
  $st = Join-Path $Brain "hooks\stop_validate.py"
  $ups = Join-Path $Brain "hooks\user_prompt_submit.py"
  if (Test-Path $ss) {
    $sw = Measure-Command { $script:so = ('{"source":"startup"}' | & $PyExe $ss 2>&1 | Out-String) }
    "SESSION_START_MS=$([int]$sw.TotalMilliseconds)"
    "SESSION_START_OUT=$so"
  } else { "MISSING session_start.py" }
  if (Test-Path $st) {
    "STOP_BEAST_ACK=" + ('{"last_assistant_message":"Beast mode is already active."}' | & $PyExe $st 2>&1 | Out-String)
    "STOP_UNCITED=" + ('{"last_assistant_message":"According to confluence the donut rules require X."}' | & $PyExe $st 2>&1 | Out-String)
    "STOP_CITED=" + ('{"last_assistant_message":"See `confluence:page:633240886` for donut rules."}' | & $PyExe $st 2>&1 | Out-String)
  }
  if (Test-Path $ups) {
    $uw = Measure-Command { $script:uo = ('{"prompt":"graph status cite nodes"}' | & $PyExe $ups 2>&1 | Out-String) }
    "UPS_MS=$([int]$uw.TotalMilliseconds)"
    "UPS_OUT=$($uo.Substring(0, [Math]::Min(600, $uo.Length)))"
  }
}

Run-Save "03-doctor.txt" { & $PyExe (Join-Path $Brain "scripts\enterprise.py") doctor 2>&1 | Out-String }
Run-Save "04-godseye.json" { & $PyExe (Join-Path $Brain "scripts\godseye.py") status --json 2>&1 | Out-String }
Run-Save "05-product.json" { & $PyExe (Join-Path $Brain "scripts\product_readiness.py") 2>&1 | Out-String }
Run-Save "06-e2e.json" { & $PyExe (Join-Path $Brain "scripts\e2e_status_report.py") 2>&1 | Out-String }
Run-Save "07-neoj.json" {
  & $PyExe (Join-Path $Brain "scripts\neoj_path_reconcile.py") --json 2>&1 | Out-String
  & $PyExe (Join-Path $Brain "scripts\neoj_path_reconcile.py") --self-test 2>&1 | Out-String
}
Run-Save "08-donut.txt" {
  & $PyExe -c @"
import json,os,sys
sys.path.insert(0, r'''$($Brain.Replace('\','\\'))\\scripts''')
os.environ['PRIVATE_BRAIN_HOME']=r'''$Brain'''
pid='confluence:page:633240886'
try:
  from brain_lib import node_path, read_json
  p=node_path(pid)
  print('exists', p.is_file(), p)
  if p.is_file():
    n=read_json(p) or {}
    print(json.dumps({
      'id': n.get('id'),
      'chunk_ids': n.get('chunk_ids'),
      'chunk_count': len(n.get('chunk_ids') or []),
      'content_path': n.get('content_path'),
      'title': n.get('title'),
    }, indent=2))
except Exception as e:
  print('error', e)
"@
}

Write-Host "EVIDENCE_DIR=$out"
explorer $out
```

---

### Phase A — Score table (5.6 marks the paste)

| Check | Pass if pasted output shows |
|-------|-----------------------------|
| Wrappers | `pb-session-start.cmd`, `pb-user-prompt-submit.cmd`, `pb-stop-validate.cmd` present under hooks |
| hooks.json | `commandWindows` references those `.cmd` files (not multiline raw python) |
| SessionStart | JSON `continue`, **SESSION_START_MS &lt; 25000** (target &lt; 5000) |
| Stop beast ack | `{"continue":true}` — **not** `decision":"block"` |
| Stop uncited | `decision":"block"` under enterprise |
| Stop cited | continue / not block when message cites `` `confluence:page:633240886` `` |
| UPS | UPS_MS &lt; 40000; single JSON object |
| product_readiness | `installer_integration: true` + ask/agent/tui/providers true |
| GodsEye JSON | keys: enabled, dismissed, pids, alive, backend, capability, last_error, last_started_at |
| Neo self-test | self-test ok; live recon not `preserved_verified` if approved paths = 0 |
| e2e_status_report | one JSON + summary; no crash |
| Donut page | `chunk_count > 0` **or** honest missing / `no_content` |

Missing scripts (`product_readiness.py`, etc.) → **install phase**, not pass.

---

### Phase B — Install repair (human pastes into **Codex CLI**, not the browser)

Only if Phase A shows missing wrappers, readiness false, or pre-`364093e` engine.

**5.6 → Kevin:** open Codex CLI (GPT 5.1), paste:

```text
You are on the Windows Private Brain laptop.

1) CODEX_HOME default %USERPROFILE%\.codex ; PRIVATE_BRAIN_HOME default %CODEX_HOME%\private-brain
2) Run:
   python %PRIVATE_BRAIN_HOME%\scripts\install_hooks.py
   python %PRIVATE_BRAIN_HOME%\scripts\install_local_rag.py
3) If scripts missing: install/sideload latest windows-ready release, then re-run (2).
4) Smoke:
   - session_start {"source":"startup"} — elapsed ms + JSON head
   - stop_validate: beast ack / uncited confluence / cited confluence:page:633240886
   - product_readiness.py ; godseye.py status --json ; e2e_status_report.py
5) Print markdown table: check | pass/fail | evidence snippet.
Zero soft-pass. Do not start GodsEye GUI unless asked. Do not invent hosts/tokens.
```

Then 5.6 has Kevin re-run the short PowerShell smoke (hooks + readiness) so the **browser thread** has ground truth, not only Codex’s summary.

---

### Phase C — Optional mutates (after baseline)

**Donut rechunk** (only if page exists with content and `chunk_count=0`):

```powershell
$Brain = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME } else { Join-Path $env:USERPROFILE ".codex\private-brain" }
$Py = Join-Path $Brain "venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
& $Py "$Brain\scripts\confluence_page_rechunk.py" --page-id confluence:page:633240886
```

If `no_content` / missing node → report need for AppGate + bounded Confluence ingest (**not** synchronous UPS). Do not invent page body.

**GodsEye GUI** (only if Kevin wants the window):

```powershell
python "$env:PRIVATE_BRAIN_HOME\scripts\godseye.py" start
python "$env:PRIVATE_BRAIN_HOME\scripts\godseye.py" status --json
```

Pass = `alive_count > 0` and honest `claim_started_ok`. `enabled=true` with `alive_count=0` is degraded-but-honest until start.

---

### Phase D — Optional live Codex session (UI)

```powershell
codex -p beast-enterprise
```

In chat: `Beast mode is already active.` → must not get `no_evidence_refuse`.  
Factual Confluence claim without cite → Stop should block.  
Paste any Stop `reason` text into the browser thread verbatim.

---

### Phase E — Handoff back to architect (Grok / next engineer)

When hard gates pass or work is blocked, 5.6 produces **one** markdown block for Kevin to forward:

```markdown
## Laptop evidence handoff
- Codex version:
- PRIVATE_BRAIN_HOME:
- Release/commit:
- SessionStart_ms / UPS_ms:
- Stop beast / uncited / cited:
- product_readiness.installer_integration:
- godseye enabled / alive_count / dismissed:
- donut chunk_count / reason:
- neo path_identity_status:
- e2e classification:
- Open gaps (bullets only):
- Evidence folder:
```

Attach key JSON under each field. No essays.

---

### Hard “done testing” definition

- [ ] Evidence folder from Phase A exists  
- [ ] Hooks use permanent `.cmd` wrappers  
- [ ] SessionStart/UPS under budget on **this** machine  
- [ ] Stop ops + cite rules match score table  
- [ ] local-rag readiness all true  
- [ ] GodsEye JSON honest (GUI only if start requested)  
- [ ] Neo recon not lying about paths  
- [ ] Donut: chunks &gt; 0 **or** documented `no_content` + next step  
- [ ] One `e2e_status_report` classification defended by files  

**Not done:** agent counts, token burn, pretty graph with no proof, soft-pass on doctor/nuclear.

