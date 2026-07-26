# Monday Mission — Zero-Fail Pilot Day-1

**Mission:** walk into Corporate Monday, restore Codex memory, install Private Brain once, answer the credential interview, reach a **100% hard-gate green** local RAG-DAG, then attach AWS (OpenSearch · Neptune · Titan · Bedrock via SHIM) without ever stranding the pilot.

**Private Brain is a Codex sideload only** — never a separate product CLI.  
**Human life is at stake → zero hard fails. Soft gaps (unknown Corporate Library/AWS) degrade, never crash core.**

---

## Your mental model — verdict

**Yes, it makes sense.** Order below is the zero-fail refinement of what you described. Two corrections:

| Your step | Refinement (why) |
|-----------|------------------|
| Collect all tokens then ingest | **Split interviews.** Sessions are **local disk** — harvest them **before** GitLab/Jira need AppGate. |
| Packages + Corporate Library then code fix | Correct — but **core RAG is stdlib**; if Corporate Library is down, stay **headless/healthy**, do not block pilot. |
| AWS SHIM after local green | **Correct.** Never make OpenSearch/Neptune a gate for local READY. |
| GodsEye monitors Neptune | **Target architecture.** Today GodsEye monitors **local graph + concert**; Neptune KPI panel activates when dual-write is configured. |

---

## Phase 0 — Before you open the kit (you)

```
1. Backup   ~/.codex/sessions/   (and any auth you own)
2. Uninstall Codex (clean)
3. Reinstall Codex
4. Restore  sessions/ into new ~/.codex/sessions/
5. Receive PrivateBrain-CORPORATE-*.zip (email / approved channel)
6. Extract → run OS single starter:
     mac/START.command   or   windows/START.ps1
```

Do **not** hand-run Python. Starter → SETUP → DAY1 / mission.

---

## Phase 1 — Install sideload (machine)

```
SETUP → copy kit → ~/.codex/private-brain
     → venv (internal)
     → hooks + beast profiles
     → brain tree
```

**Gate `INSTALL_OK`:** `orchestrate.py` present · hooks installed · beastMode on PATH.

---

## Phase 2 — Credential interview A (packages + identity)

Asked once (stored in **local** `day1.env` — never committed):

| Prompt | Purpose |
|--------|---------|
| Program id / classification | Enterprise tags |
| **Corporate Library / Corporate Package Index URL** (`PIP_INDEX_URL`) | Optional packages (pygame, numpy, …) |
| **Corporate Library trusted host** | pip TLS |
| Corporate Library user/token *if index requires auth* | Not the same as GitLab token |

**Gate `PACKAGES_OK`:**  
- With index: `capabilities --heal` installs optional packs from Corporate Library **or** degrades cleanly.  
- Without index: **stdlib headless** still green (GodsEye off until Corporate Library has pygame).

Self-heal picks modules that **import**; never assumes Corporate Library has every wheel.

---

## Phase 3 — Sessions first (local gold)

```
smart_discover → sessions/YYYY/MM/DD/rollout-*.jsonl + sqlite
             → CodexSession / SessionTurn nodes
             → vectors + snapshot
```

Runs on **every SessionStart** and on mission boot.  
No AppGate required.

**Gate `SESSIONS_OK`:** ≥1 CodexSession **or** sessions tree scanned clean; vector parity after reindex.

---

## Phase 4 — Self-heal · self-repair · DAG init · zero-fail self-check

```
beastMode --enterprise --heal
  → capabilities self-repair
  → tree · audit seal · vector parity · snapshot
beastMode --enterprise --doctor
  → hard checks only (soft: pilot_ready purity until internal ingest)
```

**Gate `LOCAL_READY` (hard 100%):**

| Check | Must |
|-------|------|
| enterprise profile | present |
| audit chain | ok (post-seal window) |
| vector parity | nodes == vectors |
| optional capabilities | soft (degrade OK) |
| Corporate Library missing | soft (headless OK) |

If anything hard fails → **heal again** → re-doctor. Loop until green.  
**This is pilot-safe local RAG-DAG.** You can work offline of AWS.

---

## Phase 5 — Credential interview B (internal sources)

Only after `LOCAL_READY`:

| Prompt | Purpose |
|--------|---------|
| AppGate connected? (y/n) | ZTNA honesty |
| **GitLab URL** + **GITLAB_TOKEN** | Internal code/wiki |
| **Jira URL** + token | Issues |
| **Confluence URL** + token | Pages |

Then multi-agent internal crawl (polite, allowlisted hosts).  
Public OSS hosts → **quarantine** (never preferred for pilot retrieve).

**Gate `OPS_READY`:** `pilot_ops_ready` (quarantine_coverage=1.0 + clean retrieve hygiene).  
**Gate `PILOT_READY` (corpus purity):** public_ratio &lt; 15% — only after enough **internal** re-ingest (not day-1 block if internal crawl is thin).

---

## Phase 6 — Credential interview C (AWS SHIM / data plane)

Only after `LOCAL_READY` (and preferably `OPS_READY`):

| Prompt | Env |
|--------|-----|
| AWS profile / region (gov-region-1 default) | `AWS_PROFILE`, `AWS_DEFAULT_REGION` |
| SSM / SHIM LLM base URL | `PB_LLM_BASE_URL` → e.g. `http://127.0.0.1:8443/v1` |
| OpenSearch endpoint | `PB_OPENSEARCH_ENDPOINT` |
| Neptune endpoint | `PB_NEPTUNE_ENDPOINT` |
| Bedrock region / Titan embed model | `PB_BEDROCK_REGION`, titan model id |
| Preferred model class | nova-pro / gss-120b / … |

Then:

```
infra_test cloud  → 100% assessment of configured endpoints
backends.yaml     → dual_write filesystem + cloud when green
```

**Gate `CLOUD_READY`:** every **configured** endpoint reachable (401/403 on OpenSearch = up).  
Unconfigured cloud = **skip**, not fail (local still flies).

When green:

- Durable vectors → OpenSearch  
- Graph dual-write → Neptune (when writers land)  
- Embeddings → Bedrock Titan  
- Orchestrator / hard synthesis → AWS-hosted LLMs via SHIM (Codex edge only)

---

## Phase 7 — GodsEye ops watch

| Mode | What it watches |
|------|-----------------|
| Always | Local graph, concert stages, vectors on disk, FPS/LOD, audit health |
| When Neptune configured | Endpoint health + dual-write lag (KPI panel) |
| Hardware | Apple Metal / NVIDIA GL — self-selected; CUDA not required for HUD |

---

## Self-heal / self-repair / self-optimize (always on)

| Loop | Trigger |
|------|---------|
| **Self-configure** | Every `beastMode` launch — probe importable modules |
| **Self-heal** | `--heal` or enterprise soft heal — chain seal, vector parity, snapshot |
| **Self-repair** | capabilities: install from Corporate Library **or** degrade |
| **Self-check** | `--doctor` · `--validate-enterprise` · `infra_test` · GodsEye suite |
| **Self-optimize** | layout settle, LOD, reindex, dead-code policy, no public PyPI in enterprise |

---

## Monday one-liner (operator)

```bash
# After START / SETUP installed the sideload:
beastMode --day1
# or kit:
./scripts/DAY1
```

Mission phases print gates. **Do not proceed to AWS until `LOCAL_READY`.**  
**Do not treat missing Jira/Confluence as hard fail** if GitLab-only is all you have Monday morning.

---

## Zero-fail definition (this program)

- **Hard fail** = cannot trust local evidence path (broken chain, vector desync, hooks missing).  
- **Soft fail** = Corporate path unknown (no Corporate Library, no Neptune yet, public_ratio high until internal crawl). Soft fails **warn** and **degrade**; they do **not** ground the pilot.

When in doubt: **heal → doctor → work local → attach AWS when green.**
