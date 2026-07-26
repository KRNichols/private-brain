# Private Brain — READY

**Entry (not a second CLI):** `codex -p beast` / `codex -p beast-enterprise`  
Thin launcher `beastMode` only sets env / optional GodsEye / enterprise controls, then **execs Codex** (or exits after feature flags).

**You never run Python.** Only `SETUP` / `beastMode` / `UNINSTALL`.

**Corporate is not offline.** Third-party packages come from **Corporate Library Corporate Package Index**. Core RAG-DAG is **stdlib only**. See `CORPORATE_PACKAGE_INDEX.md` and `START_AT_CORPORATE.md`.

---

## Day-1 enterprise (Corporate pilot)

```
corporate-package-index.env
  → SETUP / START_AT_CORPORATE
  → beastMode --enterprise --heal
  → beastMode --enterprise --doctor          # READY
  → beastMode --quarantine-public           # pilot_ops_ready
  → beastMode --validate-enterprise         # hard_ok
  → internal re-ingest                      # pilot_ready
  → beastMode --enterprise                  # work
```

### Commands (copy/paste)

```bash
# 0) Corporate Library index if GodsEye packages needed (core RAG needs no pip)
cp corporate-package-index.env.example corporate-package-index.env
# edit PIP_INDEX_URL / PIP_TRUSTED_HOST → Corporate Library
source ./corporate-package-index.env
export PB_ENTERPRISE=1
export PB_PIP_REQUIRE_CORPORATE_INDEX=1

# 1) Install once (or one-click day-1)
bash SETUP.command
# preferred full bootstrap:
# ./START_AT_CORPORATE.command
# ./scripts/start_at_corporate --yes --program YOUR_PROGRAM --hosts gitlab.your.internal

# 2) Self-recover + health
export PATH="$HOME/bin:$PATH"
beastMode --enterprise --heal
beastMode --enterprise --doctor          # expect: READY

# 3) Ops purity (tag public hosts — does not delete)
beastMode --quarantine-public            # → pilot_ops_ready when coverage OK
beastMode --purity-audit                 # optional snapshot → corpus_purity.json

# 4) Multi-agent E2E validation
beastMode --validate-enterprise          # hard_ok = ops ready (exit 0)

# 5) Internal re-ingest → pilot_ready (public_ratio < 15%, clean ≥ 50)
export GITLAB_TOKEN=...
beastMode --enterprise -ingestion https://gitlab.your.internal/your/group --ingest-only
beastMode --purity-audit
beastMode --enterprise --doctor

# 6) Work + evidence
beastMode --enterprise                   # headless; GodsEye OFF
beastMode --enterprise --sap-pack
```

**Windows (PowerShell):** same `beastMode …` flags after SETUP; ensure `%USERPROFILE%\bin` is on PATH.

### Readiness gates

| Gate | Field / output | Meaning |
|------|----------------|---------|
| **READY** | doctor last line | hooks · profiles · scripts · chain · vectors OK |
| **`pilot_ops_ready`** | purity / validate soft | public hosts quarantined + ≥ 50 clean nodes (retrieve hygiene) |
| **`pilot_ready`** | purity soft | raw host purity after **internal re-ingest** (public_ratio &lt; 15%) |
| **`hard_ok`** | validate_enterprise.json | lint · quarantine · purity×3 · hygiene · vectors · chain · doctor (+ swarm/concert) |

Reports:

- `~/.codex/private-brain/.brain/state/corpus_purity.json`  
- `~/.codex/private-brain/.brain/state/validate_enterprise.json`  
- SAP packs: `~/.codex/private-brain/.brain/audit/packs/sap-pack-*.zip`

---

## Freeze zip path

```bash
cd /path/to/private-brain-codex
./scripts/freeze_for_corporate
# → dist/PrivateBrain-CORPORATE-<UTC>.zip
# → dist/PrivateBrain-CORPORATE-<UTC>.sha256
```

Take **only** that zip (or the whole kit folder). At Corporate: extract → `corporate-package-index.env` (**Corporate Library / Protected Gateway** `PIP_INDEX_URL`) → `START_AT_CORPORATE` / commands above. Freeze is **not** an offline wheel kit — core is stdlib headless; optional packages from approved index only (`config/judge_corporate_library_policy.json`).

---

## Self-recovering controls

| Trigger | What heals |
|---------|------------|
| Every `beastMode --enterprise` | Light: seal chain if broken, vector reindex if lag, ensure profile |
| `beastMode --enterprise --heal` | Full: profile, tree, seal, reindex, snapshot |
| `START_AT_CORPORATE` / `start_at_corporate` | SETUP if missing, launcher recover, heal, doctor, one auto-retry |
| Missing hooks / profiles / `.brain` | Auto-recreated on launch / SETUP |

Drift recovery: **heal → doctor**. No AI assistant required on-site.

---

## Launch (daily)

```bash
# Primary (after install)
codex -p beast
# Enterprise pilot
beastMode --enterprise                 # headless — GodsEye OFF
codex -p beast-enterprise              # same profile without wrapper

# Optional GodsEye (needs Corporate Library pygame + PyOpenGL for TRUE GL)
beastMode --enterprise -GodsEye
PB_GODSEYE_BACKEND=cpu beastMode --enterprise -GodsEye
```

First interactive session: trust hooks via `/hooks` once, or pass `--dangerously-bypass-hook-trust` if your wrapper does.

---

## What auto-fires

| Event | What runs |
|-------|-----------|
| **SessionStart** | `orchestrate.py boot` → brain + watcher + audit; GodsEye GUI only if enabled |
| **UserPromptSubmit** | concert turn → inject EVIDENCE |
| **Stop** | citation / evidence gate |

State: `$PRIVATE_BRAIN_HOME/.brain/` (default `~/.codex/private-brain/.brain/`)  
Orchestrator: `scripts/orchestrate.py`

---

## GodsEye (optional F/A-18 HUD)

| Enable | Effect |
|--------|--------|
| `PB_GODSEYE=1` | `godseye.ensure_gui()` starts Live Ops |
| `-GodsEye` | TRUE OpenGL default (`graph_gl.py`) when pygame+PyOpenGL present |
| `--GodsEye-cpu` / `PB_GODSEYE_BACKEND=cpu` | software pygame fallback |
| flag file | `$PRIVATE_BRAIN_HOME/.brain/state/godseye.on` also counts as on |

Off by default. Enterprise pilot is valid **without** GodsEye.

---

## Concert stages

```
boot
  ├── cost || security || retrieve     (parallel)
  └── crawl_gap?                       (if thin evidence + budget)
validate || metrics                    (parallel)
synthesize → rate → optimize? → emit
```

```bash
# Engine path (maintainers) — end users stay on beastMode
python scripts/orchestrate.py concert --prompt "your question"
```

---

## Enterprise flags (`beastMode`)

| Flag | Job |
|------|-----|
| `--enterprise` | `beast-enterprise` profile · no public OSS · hard cites/audit |
| `--heal` | Self-recover profile · chain · vectors · snapshot |
| `--doctor` | Health → **READY** / **FAIL** |
| `--quarantine-public` | Tag public-host nodes (retrieve demote; no delete) |
| `--purity-audit` | Reproducible corpus purity report + `report_hash` |
| `--validate-enterprise` | Multi-agent E2E → `hard_ok` / `pilot_ops_ready` / `pilot_ready` |
| `--sap-pack` | Security evidence zip |
| `-ingestion URL --ingest-only` | Internal harvest (public presets blocked under enterprise) |
| `-GodsEye` | Optional Live Ops |

---

## Environment

| Variable | Purpose |
|----------|---------|
| `PRIVATE_BRAIN_HOME` | Brain install root (default `~/.codex/private-brain`) |
| `PB_ENTERPRISE` | Enterprise mode (also set by `--enterprise`) |
| `PB_PROGRAM_ID` | Program stamp on nodes |
| `PB_CLASSIFICATION` | e.g. `INTERNAL` / `CUI` |
| `PB_ALLOWLIST_HOSTS` | Comma hosts for internal ingest |
| `PIP_INDEX_URL` / `PB_PIP_INDEX_URL` | **Corporate Library Corporate Package Index** PyPI remote |
| `PIP_TRUSTED_HOST` / `PB_PIP_TRUSTED_HOST` | Corporate Library host |
| `PB_PIP_REQUIRE_CORPORATE_INDEX` | Refuse silent public PyPI for optional deps |
| `GITLAB_TOKEN` | Optional API token; never print / commit |
| `PB_GODSEYE` | `1` → enable Live Ops |
| `PB_GODSEYE_BACKEND` | `gl` (default with `-GodsEye`) or `cpu` |

---

## Key scripts

| Script | Job |
|--------|-----|
| `scripts/beastMode` | Arg-driven thin launcher → codex or feature exit |
| `scripts/enterprise.py` | heal · doctor · purity · quarantine-public · sap-pack |
| `scripts/validate_enterprise.py` | Multi-agent E2E harness |
| `scripts/start_at_corporate` | Day-1 bootstrap (Corporate Package Index-aware, self-healing) |
| `scripts/freeze_for_corporate` | Build `dist/PrivateBrain-CORPORATE-*.zip` |
| `scripts/orchestrate.py` | boot / concert DAG |
| `scripts/gitlab_ingest.py` | GitLab harvest (internal under enterprise) |

---

## Pipeline (hook view)

```
User → SessionStart(boot) → UserPromptSubmit(concert)
     → Model answers from injected EVIDENCE
     → Stop(citation gate)
```

---

## Uninstall

One-click reverse of the sideload. **Codex CLI stays.** Knowledge graph (`.brain`) is **archived** by default under `~/.codex/private-brain-archive-*` (use purge to delete).

| Platform | How |
|----------|-----|
| **Mac** | Double-click `UNINSTALL.command` |
| **Windows** | Double-click `UNINSTALL.cmd` |

```bash
# From installed tree (package/ or ~/.codex/private-brain)
python scripts/uninstall_private_brain.py --dry-run --json
python scripts/uninstall_private_brain.py
python scripts/uninstall_private_brain.py --purge-brain

# Thin CLI
python -m private_brain uninstall
python -m private_brain uninstall --purge-brain
```

After uninstall, vanilla Codex: `codex`
