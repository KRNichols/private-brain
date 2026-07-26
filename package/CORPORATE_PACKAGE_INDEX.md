# Corporate Library / Protected Gateway Corporate Package Index — approved package sources (Corporate)

Corporate is **not** treated as fully offline. The rule is:

> **Any third-party dependency must come from Corporate Library Corporate Package Index, Protected Gateway-approved repos, or an approved equivalent index** (via `PIP_INDEX_URL` / `PB_PIP_INDEX_URL`).  
> If it is not there, you must either (1) **request onboarding** of that package, or (2) discover an approved equivalent and change the code, or (3) **drop the feature** that needs it.

Public PyPI (`pypi.org`) is **not** an approved default at install time in enterprise mode.

**Primary model (preferred):**

1. Point pip at **Corporate Library / Protected Gateway** with `PIP_INDEX_URL`  
2. **Request package** in Corporate Library / Protected Gateway if missing  
3. **Core is stdlib** — headless enterprise works with **zero** third-party packages  

**Not the primary model:** shipping a prebuilt offline `vendor/wheels` kit. See `config/judge_corporate_library_policy.json`.

---

## Dependency inventory (what we actually use)

### Required for core RAG-DAG / enterprise (no third-party packages)

| Component | Runtime | Notes |
|-----------|---------|--------|
| Concert / orchestrate | **Python 3.10+ stdlib** | json, pathlib, urllib, re, zipfile, … |
| Graph store | stdlib + filesystem | `.brain/nodes`, edges |
| TF-IDF vectors | stdlib | no numpy / scipy |
| Audit chain | stdlib | hash chain + seal |
| Session discover | stdlib + sqlite3 | |
| Enterprise policy | stdlib | optional PyYAML if present; has fallback parser |
| Hooks | stdlib | SessionStart / Prompt / Stop |

**Ship gate:** if only stdlib is available, `beastMode --enterprise` (headless) is still valid.

### Optional third-party (feature-gated)

| Package | Used for | If missing / not in Corporate Package Index |
|---------|----------|----------------------------------|
| **pygame** | GodsEye live GUI only | **Skip `-GodsEye`**. Headless pilot continues. |
| **PyOpenGL** (+ accelerate if available) | GodsEye `PB_GODSEYE_BACKEND=gl` free-universe OpenGL layout | Use `PB_GODSEYE_BACKEND=cpu` (pygame only) or stay headless |
| **PyYAML** | nicer parse of `enterprise.yaml` / `backend.yaml` | **Not required** — code has line-parser fallback |
| AWS SDK / Neptune / OpenSearch clients | Government Cloud dual-write (future) | **Not implemented** — do not install until ATO path + Corporate Package Index packages exist |

### Not used (do not add without Corporate Package Index review)

- numpy, scipy, torch, transformers  
- openai / anthropic SDKs (Codex binary talks to models; brain does not)  
- requests (stdlib urllib is used)  
- fastapi / flask  

---

## Preferred install model: Corporate Library / Protected Gateway via `PIP_INDEX_URL`

### 1. Configure pip to Corporate Library or Protected Gateway only

```bash
# Example — replace with your real Corporate Library or Protected Gateway PyPI remote
export PIP_INDEX_URL="https://corporate-library.corporate-package-index.example/corporate-package-index/api/pypi/pypi-virtual/simple"
export PIP_TRUSTED_HOST="corporate-library.corporate-package-index.example"
# Protected Gateway (or other approved equivalent):
# export PIP_INDEX_URL="https://…protected-gateway…/corporate-package-index/api/pypi/…/simple"
# export PIP_EXTRA_INDEX_URL="https://…approved…/simple"

# Never fall back to public PyPI in enterprise:
# pip install --index-url "$PIP_INDEX_URL" --trusted-host ...
```

Also supported by SETUP:

```bash
export PB_PIP_INDEX_URL="$PIP_INDEX_URL"
export PB_PIP_TRUSTED_HOST="$PIP_TRUSTED_HOST"
export PB_ENTERPRISE=1   # refuses silent public PyPI for optional deps when set
export PB_PIP_REQUIRE_ARTIFACTORY=1
```

Copy `corporate-package-index.env.example` → `corporate-package-index.env` and source before SETUP.

### 2. What SETUP will do

1. Create venv under `~/.codex/private-brain/venv`  
2. **If** `PB_PIP_INDEX_URL` / `PIP_INDEX_URL` set → install optional deps **only** from that Corporate Library / Protected Gateway index  
3. **Else if enterprise** → **do not** hit public PyPI; leave optional packages missing → **headless OK**  
4. Else (dev laptop only) → public PyPI allowed for convenience  

Missing package after step 2 → **request Corporate Library / Protected Gateway onboarding** or drop the feature. Core remains valid.

### 3. Wheels are not the delivery model

A **wheel** (`.whl`) is only the binary format pip installs from an index.  
At Corporate, wheels should be **served by Corporate Library / Protected Gateway** when you `pip install` with `PIP_INDEX_URL` — not bulk-shipped in the travel zip as the primary path.

- **`freeze_for_corporate` does not ship a primary offline wheel kit.**  
- `vendor/wheels/` is **not required** and is **not** the Corporate package model.  
- Do **not** scrape public PyPI into `vendor/wheels` for transfer.  
- If local policy ever allows emergency Corporate Package Index-origin `--find-links`, those bits must still be **Corporate Library / Protected Gateway-promoted**, not internet scrapes.

Machine-readable policy: **`config/judge_corporate_library_policy.json`**.

---

## If pygame / PyOpenGL is not in Corporate Library or Protected Gateway

| Option | Action |
|--------|--------|
| **A. Request package** | File Corporate Library / Protected Gateway onboarding for `pygame` / `PyOpenGL` (and SDL deps if any) |
| **B. Approved equivalent** | Only if org has another 2D UI lib already in Corporate Package Index — would require rewriting `visualizer/live_gui.py` |
| **C. Drop GUI (recommended pilot)** | Document GodsEye as non-pilot; use doctor + concert + SAP pack only |

**Do not** vendor unapproved binaries just to make the GUI pretty.

---

## If you need cloud backends later

`config/backend.yaml` + `scripts/backends.py` are stubs. Before any:

- `boto3` / Bedrock Titan  
- Neptune client  
- OpenSearch client  

…those packages must be **in Corporate Library / Protected Gateway**, versions pinned, and code switched from “local TF-IDF” only after security review. Until then, **filesystem RAG remains the system of record**.

---

## Checklist for Corporate platform eng

- [ ] Confirm Corporate Library (and/or Protected Gateway) PyPI virtual repo URL + auth (token / SSO)  
- [ ] Search Corporate Library / Protected Gateway for `pygame` (and Python version matrix: 3.10/3.11, win/mac/linux)  
- [ ] If missing: **onboarding request** **or** accept headless pilot  
- [ ] Set `corporate-package-index.env` on engineer machines / golden image  
- [ ] SETUP / Install-PrivateBrain uses index URL (no public PyPI in enterprise)  
- [ ] Confirm freeze zip has **no** “must ship wheels” expectation  
- [ ] Document: Codex itself is separate (OpenAI/corporate model endpoint), not a pip package  

---

## Summary

| Question | Answer |
|----------|--------|
| Offline? | No — **approved sources only** (Corporate Library / Protected Gateway Corporate Package Index) |
| Primary install path | `PIP_INDEX_URL` → Corporate Library or Protected Gateway |
| If package missing | **Request onboard**, approved equivalent, or drop feature |
| What must be in Corporate Package Index for pilot? | **Nothing** for headless core; **pygame** (+ PyOpenGL for TRUE GL) only if GodsEye is required |
| Ship offline wheels as primary? | **No** |
| Core without pip? | **Yes** — stdlib headless enterprise is production-valid |
| Policy file | `config/judge_corporate_library_policy.json` |
