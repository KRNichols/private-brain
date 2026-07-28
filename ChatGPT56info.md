# ChatGPT 5.6 / Codex — master Private Brain (Windows READY)

**Audience:** GPT‑5.6 Terra, GPT‑5.1 edge Codex, co‑workers, parent models (Grok handoff).  
**Human rule:** you almost never run Python. **You** (the model) run scripts via hooks/shell when needed. Human talks.

This file is the **teach pack**: what the system does, what to read, what to run, what never to invent.

---

## 0 · What this whole thing will do

Private Brain is **not** a separate product CLI. It is a **Codex sideload**:

```text
You talk in Codex
    → hooks (SessionStart / UserPromptSubmit / Stop)
    → filesystem RAG-DAG under PRIVATE_BRAIN_HOME/.brain
    → answers with node_id cites (beast mode) or plain Codex (normal mode)
    → optional GodsEye graph HUD
    → optional crawl of GitLab / Jira / Confluence (internal after AppGate)
    → golden config + co-worker join (no secrets in git)
```

**Day-to-day human UX**

| Human does | System does |
|------------|-------------|
| Install once (`START.ps1` / Windows READY zip) | Hooks, beast profile, venv, enterprise flags |
| Open Codex | SessionStart → beast on, golden inject |
| Talk (fire drill, heal, crawl, golden…) | conversation_router + orchestrate concert |
| Say `stop beast mode` | RAG off this session only |
| Reopen Codex | Beast on again |
| Optional: `beastMode -GodsEye` | Live graph (not from hook Popen) |

**Windows Corporate release law**

| Law | Value |
|-----|--------|
| One auto CI pipeline | **Windows Release MVP** only |
| Codex CLI pin | **0.144.3** (do not upgrade to “latest”) |
| Max agents | **64** |
| GitLab inter-repo wait | hard cap **≤ 15s** |
| Public OSS on CI | only with **`PB_ALLOW_PUBLIC_INGEST=1`** |
| Corporate default | block public forges; **AppGate → internal hosts** |
| Soft-pass blocked ingest | **banned** |

**Release artifact**

- GitHub Release tags: `windows-ready-<sha7>`
- Files: `PrivateBrain-WINDOWS-READY.zip` + `.sha256`
- Latest example pattern: repo **Releases** → Windows READY

---

## 1 · Mental model (one page)

```text
┌─────────────────────────────────────────────────────────────┐
│  Codex CLI 0.144.3  +  hooks.json  +  beast-enterprise      │
└───────────────────────────┬─────────────────────────────────┘
                            │ stdin JSON / stdout JSON
┌───────────────────────────▼─────────────────────────────────┐
│  hooks: session_start · user_prompt_submit · stop_validate  │
│  stop: only continue | decision+reason (no illegal fields)  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  scripts/: orchestrate · enterprise · golden_config         │
│            gitlab/github ingest · scenario_heal             │
│            corporate_infra_probe · organism · fire_drill    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  .brain/  graph + audit + state (golden, day1_map, probes)  │
└─────────────────────────────────────────────────────────────┘
```

**Harmony (Corporate laptop)**

```text
AppGate UP  → corporate_infra_probe → reachable hosts → crawl/ingest
AppGate DOWN → probe: likely_appgate_blocked → tell human connect ZTNA
               → do NOT fall back to public gitlab.com
No hosts in map → heal from env/day1/golden → if still empty ASK ONCE
                  → synthesizer agents ≤64 → write map → re-probe
```

**CI (GitHub free Windows runner)**

```text
No AppGate. Public OSS force-feed only with PB_ALLOW_PUBLIC_INGEST=1.
Hard gates: real node growth on ingest, not "enterprise" string soft-pass.
```

---

## 2 · Read these files (in order) to master the release build

### A. Release & CI (must)

| # | Path | Why |
|---|------|-----|
| 1 | `.github/workflows/windows-release.yml` | The **one** pipeline: box, Codex pin, E2E, mint zip, GitHub Release |
| 2 | `scripts/windows_release_mvp.py` | Hard gate chain (lint, hooks, ingest, nuclear, scenarios) |
| 3 | `scripts/codex_cli_smoke.py` | Install/smoke **@openai/codex@0.144.3** |
| 4 | `installers/windows/START.ps1` | User install / water-pipe |
| 5 | `installers/windows/README.md` | Human install story |

### B. Product law & Corporate map

| # | Path | Why |
|---|------|-----|
| 6 | `package/docs/KINGDOM_KEYS.md` | API shapes: GitLab/Jira/Confluence/Library/AWS |
| 7 | `config/corporate_golden_join.example.json` | Join fields + AppGate step (examples only) |
| 8 | `config/enterprise.yaml` | block public presets / allowlist |
| 9 | `package/CORPORATE_PACKAGE_INDEX.md` | PIP_INDEX / no public PyPI default |
| 10 | `DAY1_PROMPTS.md` | What the human pastes day 1 |
| 11 | `beast-mode.md` | Roles, audit, spawn law |

### C. Ingest, AppGate, heal→ask→synthesize

| # | Path | Why |
|---|------|-----|
| 12 | `scripts/corporate_infra_probe.py` | Probe hosts; AppGate vs missing map |
| 13 | `scripts/scenario_heal.py` | Gaps: hosts/tokens/index/AWS/sessions/GodsEye ≤64 agents |
| 14 | `scripts/ingest_scenario.py` | Blocked public ingest → heal / ask / synthesizer |
| 15 | `scripts/gitlab_ingest.py` | Real GitLab ingest + ALLOW_PUBLIC |
| 16 | `scripts/github_ingest.py` | GitHub ingest (CI public path) |
| 17 | `scripts/ci_force_feed_public.py` | Multi-source public feed (CI) |
| 18 | `scripts/conversation_router.py` | “probe corporate”, fire drill, gaps… |
| 19 | `hooks/session_start.py` | Beast on + pending scenario inject |
| 20 | `hooks/user_prompt_submit.py` | Modes, RAG, GodsEye **flag-only** (no Popen) |
| 21 | `hooks/stop_validate.py` | Cite gate; **minimal Stop JSON** for 0.144 |

### D. Launchers

| # | Path | Why |
|---|------|-----|
| 22 | `scripts/beastMode.cmd` | Windows primary launcher |
| 23 | `scripts/install_hooks.py` | hooks.json + commandWindows |

### E. Live evidence after install / CI (optional)

| Path | Why |
|------|-----|
| `.brain/state/golden_config.json` | Live map (no secrets) |
| `.brain/state/corporate_infra_probe.json` | Last infra probe |
| `.brain/state/pending_scenarios.json` | Open gaps + agents |
| `e2e-reports/WINDOWS_RELEASE_MVP.json` | CI gate transcript |
| GitHub **Releases** `windows-ready-*` | What humans download |

---

## 3 · Minimal 10-file pack (if context is tight)

1. `.github/workflows/windows-release.yml`  
2. `scripts/windows_release_mvp.py`  
3. `scripts/codex_cli_smoke.py`  
4. `scripts/corporate_infra_probe.py`  
5. `scripts/scenario_heal.py`  
6. `scripts/ingest_scenario.py`  
7. `package/docs/KINGDOM_KEYS.md`  
8. `config/corporate_golden_join.example.json`  
9. `hooks/stop_validate.py`  
10. `DAY1_PROMPTS.md`  

One-liner law: **Corporate laptop = Codex 0.144.3; public CI ingest only with `PB_ALLOW_PUBLIC_INGEST=1`.**

---

## 4 · Commands the model (or agent) may run

Windows (venv first):

```powershell
$env:CODEX_HOME = "$env:USERPROFILE\.codex"
$env:PRIVATE_BRAIN_HOME = "$env:CODEX_HOME\private-brain"
$env:PYTHONPATH = "$env:PRIVATE_BRAIN_HOME\scripts"
$env:PB_ENTERPRISE = "1"
$env:PYTHONUTF8 = "1"
$py = "$env:PRIVATE_BRAIN_HOME\venv\Scripts\python.exe"

codex --version
# expect ~0.144.3 on Corporate laptop

& $py "$env:PRIVATE_BRAIN_HOME\scripts\enterprise.py" doctor
& $py "$env:PRIVATE_BRAIN_HOME\scripts\fire_drill.py"
& $py "$env:PRIVATE_BRAIN_HOME\scripts\golden_config.py"
& $py "$env:PRIVATE_BRAIN_HOME\scripts\corporate_infra_probe.py" --write
& $py "$env:PRIVATE_BRAIN_HOME\scripts\scenario_heal.py" synthesize --reason "teach"
& $py "$env:PRIVATE_BRAIN_HOME\scripts\brain_status.py"
```

**CI-only public feed (never default Corporate):**

```powershell
$env:PB_ALLOW_PUBLIC_INGEST = "1"
& $py "$env:PRIVATE_BRAIN_HOME\scripts\ci_force_feed_public.py"
```

**Human conversation triggers** (no flags):

| Say | Effect |
|-----|--------|
| `fire drill` | Health smoke |
| `doctor` / `are we green` | Enterprise doctor |
| `heal yourself` | Self-heal + ledger |
| `show golden config` | Refresh golden |
| `probe corporate` / `appgate` | Infra probe + scenarios |
| `pilot gaps` / `what is missing` | heal→ask→synthesize |
| `stop beast mode` | RAG off this session |
| `beast mode` | RAG on |
| `show GodsEye` | Flags only; launch via beastMode -GodsEye |

---

## 5 · Env matrix (do not guess)

| Env | Meaning |
|-----|---------|
| `CODEX_HOME` | Usually `%USERPROFILE%\.codex` |
| `PRIVATE_BRAIN_HOME` | Usually `%CODEX_HOME%\private-brain` |
| `PB_ENTERPRISE=1` | Corporate law, cite gate, block public forges |
| `PB_ALLOW_PUBLIC_INGEST=1` | **Explicit** CI/lab public OSS override |
| `PB_CODEX_VERSION=0.144.3` | Pin for smoke/install |
| `PB_MAX_AGENTS=64` | Swarm / scenario agent ceiling |
| `PB_GITLAB_INTER_REPO_SEC` | Wait between projects, **max 15** |
| `PB_GODSEYE=0` | Headless default on CI / pilot often headless |
| `PB_CI=1` | Unattended; no “ask human” interviews |
| `PB_SESSIONS_EMPTY_ACK=1` | Empty sessions OK on bare runners |
| `PB_GITLAB_URL` / `PB_JIRA_URL` / `PB_CONFLUENCE_URL` | Internal bases (after AppGate) |
| `PIP_INDEX_URL` / `PB_PIP_INDEX_URL` | Corporate Library / Protected Gateway |
| `GITLAB_TOKEN` etc. | secrets_store / env — **never print** |

---

## 6 · What you must **never** do

1. **Upgrade Codex** past the Corporate pin “because latest exists”.  
2. **Soft-pass** a failed ingest because the error contained the word “enterprise”.  
3. **Invent** hosts, tickets, or node cites.  
4. **Use public gitlab.com** under enterprise without `PB_ALLOW_PUBLIC_INGEST`.  
5. **Popen GodsEye from UserPromptSubmit** (hook hang on Windows 0.144).  
6. **Put tokens in golden_join.json or git**.  
7. **Tell the human to type a flag parade** when conversation can run the script.  
8. **Claim READY** if Windows Release MVP or doctor hard gates are red.

---

## 7 · Paste this into a new GPT 5.6 / Codex session

```text
You are learning Private Brain Windows READY. Read ChatGPT56info.md first, then the
10-file pack listed in section 3 (or full list in section 2).

Summarize back:
A) What the product does end-to-end (hooks → RAG-DAG → cites)
B) Windows Release MVP pipeline steps and hard gates
C) Codex 0.144.3 pin and why
D) Enterprise vs PB_ALLOW_PUBLIC_INGEST
E) AppGate harmony: probe → reachable / blocked / missing hosts → ask once
F) heal→ask→synthesize (scenario_heal, ≤64 agents)
G) How a human reinstalls from GitHub release windows-ready-*

Rules: never invent hosts/tokens; never soft-pass blocked ingest; cite file paths.
When unsure, open the file — do not hallucinate CI or Corporate DNS.
```

---

## 8 · Related entry points

| Doc | Role |
|-----|------|
| `README.md` | Public product overview |
| `DOWNLOAD.md` | How to get READY kits |
| `DAY1_PROMPTS.md` | Day-1 conversation checklist |
| `DIAGRAM.md` | Architecture pictures |
| `ChatGPT56info.md` | **This file — teach GPT 5.6 the release** |

---

## 9 · Quick “are we READY?” checklist for the model

- [ ] `codex --version` matches pin (0.144.x Corporate)  
- [ ] `hooks.json` present under CODEX_HOME; Stop JSON legal  
- [ ] `enterprise.on` / beast mode; doctor hard green (or known CI soft names only)  
- [ ] Ingest: either internal hosts after AppGate, or CI with ALLOW_PUBLIC and **node counts grew**  
- [ ] `corporate_infra_probe` / golden map honest about missing hosts  
- [ ] Windows Release MVP green + `PrivateBrain-WINDOWS-READY.zip` on Releases  

If any hard gate fails: **fix**, do not greenwash.
