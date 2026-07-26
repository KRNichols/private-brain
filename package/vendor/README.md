# vendor/

## Corporate package model (primary)

**Corporate Library / Protected Gateway via `PIP_INDEX_URL` (or `PB_PIP_INDEX_URL`).**

Optional GodsEye packages install at the destination from the approved Corporate Package Index remote:

```bash
export PIP_INDEX_URL="https://…corporate-package-index…/simple"
export PIP_TRUSTED_HOST="…"
# then SETUP / pip install -r visualizer/requirements.txt
```

If a package is missing from Corporate Library/Protected Gateway → **request onboarding** or stay **headless** (core is stdlib).

## Local wheels (`vendor/wheels/`)

- **Last-resort cache only** — never required for freeze, SETUP, or enterprise pilot.
- Not the primary Corporate delivery model.
- Must be Corporate Package Index-origin if used; do not scrape public PyPI into this folder.
- Empty directory is normal and correct.

See `../CORPORATE_PACKAGE_INDEX.md`, `../config/judge_corporate_library_policy.json`, and `../config/judge_freeze.json`.
