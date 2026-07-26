# Public GitHub design — Private Brain (KRNichols)

**Goal:** A great public repo that showcases the sideload organism, ships dual-OS kits, and **proves Windows first-boot on real GitHub-hosted Windows runners** — without leaking Corporate corpus, tokens, or work Neo4j.

**Account:** https://github.com/KRNichols  
**Suggested repo:** `private-brain` or `private-brain-codex` (public)

---

## 1. Can GitHub do pipelines? Windows runners?

**Yes.**

| Capability | Public repo (standard runners) | Notes |
|------------|----------------------------------|--------|
| **GitHub Actions** | Free for public repos on standard hosted runners | CI/CD, matrix, artifacts |
| **`windows-latest`** | Yes | Real Windows VM — Corporate first-boot smoke |
| **`macos-latest`** | Yes | Real Mac VM — home-lab / Mac READY smoke |
| **`ubuntu-latest`** | Yes | Fast nuclear + freeze |
| **Matrix all three** | Yes | See `.github/workflows/dual-os-matrix.yml` |
| **Artifacts** | Yes | Upload WINDOWS-READY + MAC-READY + CORPORATE zips |
| **Releases** | Yes | Tag → attach zips + checksums |
| **PR checks** | Yes | nuclear_x10 on ubuntu/windows/mac |
| **Larger runners / GPU** | Paid / limited | GodsEye GL: soft on hosted Mac; self-hosted optional |
| **Self-hosted runner** | Possible | Your home Mac for Metal GodsEye; keep private for secrets |

**Sky’s-the-limit productively:**

- Matrix: Ubuntu + Windows + (optional) macOS every PR  
- Nightly: full freeze → nuclear_x10 → attach artifacts  
- Release: signed checksums + provenance (SLSA-ish later)  
- Optional: CodeQL, Dependabot, scorecard  
- Optional: self-hosted Mac for GodsEye OpenGL smoke  

**Not free / careful:** larger runners, GPU, unlimited private minutes, putting **secrets** in public logs.

---

## 2. What goes public vs stays private

| Public (this repo) | Private / never commit |
|--------------------|-------------------------|
| Engine source (`scripts/`, `hooks/`, `visualizer/`, `private_brain/`) | `.brain/` corpus |
| Installers + `tools/` plane docs | `corporate.env`, tokens, `corporate-package-index.env` |
| DIAGRAM, README Day-1 checklist | Live Neo4j dumps |
| CI workflows | Golden join with real hosts (use examples only) |
| Example configs `*.env.example` | Encrypted secrets blobs |
| Nuclear / fire_drill / brutal (headless paths) | Work-only PDFs with export control |

**Rule:** if it would get you fired or doxx a program, it stays off GitHub.

---

## 3. Recommended repo shape (great, not noisy)

```text
private-brain/                    # public
├── README.md                     # vision + Day-1 checklist (from kit ROOT_README)
├── DIAGRAM.md                    # dual-audience picture
├── LICENSE                       # MIT or Apache-2.0 (pick one)
├── SECURITY.md                   # how to report issues; no secrets in issues
├── CONTRIBUTING.md
├── .gitignore                    # .brain, venv, *.env, dist/_staging
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # PR: nuclear on ubuntu + windows + macOS
│   │   ├── windows-first-boot.yml # windows-latest: READY extract + START.ps1
│   │   ├── mac-first-boot.yml     # macos-latest: READY extract + START.command
│   │   ├── dual-os-matrix.yml     # nightly/tag: all three OS + freeze artifacts
│   │   └── release.yml            # tag v* → freeze → nuclear → GH Release
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── DAY1.md
│   ├── ARCHITECTURE.md
│   ├── NON_HALLUCINATION.md
│   └── GITHUB_PUBLIC_DESIGN.md   # this file
├── installers/                   # shared + mac + windows fragments
├── package/                      # engine mirror (or generate on freeze)
├── scripts/                      # source of truth for freeze
├── hooks/
├── visualizer/
├── private_brain/
└── dist/                         # optional: gitignore; CI uploads artifacts instead
```

**Product pitch in README (one line):**

> Codex sideload: local RAG-DAG organism — install once, open Codex, talk. Cite-or-block. Dual OS. Windows first-boot proven in CI.

---

## 4. CI design (real results, not badge theater)

### 4.1 PR / push — `ci.yml`

```yaml
# Conceptual — implement in .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  lint-and-nuclear-ubuntu:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r visualizer/requirements.txt || true  # optional GodsEye
      - run: python -m py_compile $(git ls-files '*.py' | tr '\n' ' ')
      - run: PB_ENTERPRISE=1 python scripts/nuclear_x10.py
        # headless: skip live GodsEye FPS hard if no display
        env:
          PB_NUCLEAR_HEADLESS: "1"

  windows-static-and-layout:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - shell: pwsh
        run: |
          python -m py_compile (Get-ChildItem -Recurse -Filter *.py scripts,hooks,private_brain,visualizer).FullName
          $env:PB_ENTERPRISE=1
          python scripts/nuclear_x10.py
```

### 4.2 Windows first-boot path — `windows-first-boot.yml`

```yaml
# Prove the kit a Corporate human would extract
jobs:
  windows-ready-smoke:
    runs-on: windows-latest
    steps:
      - checkout
      - setup-python 3.11
      - name: Freeze or use cached kit
        run: bash scripts/freeze_for_corporate   # or download last artifact
      - name: Extract WINDOWS-READY
        shell: pwsh
        run: |
          Expand-Archive dist/PrivateBrain-WINDOWS-READY.zip -DestinationPath kit
          Get-ChildItem kit | Select-Object Name
          # Root MUST be README, DIAGRAM, tools only
      - name: Install sideload (noninteractive)
        shell: pwsh
        run: |
          Set-ExecutionPolicy -Scope Process Bypass
          cd kit
          $env:PB_NONINTERACTIVE=1
          $env:PB_NO_OPEN_CODEX=1
          .\tools\install\START.ps1 -Yes -Route headless -NoGodsEye
      - name: Assert hooks + danger profile
        shell: pwsh
        run: |
          Test-Path "$env:USERPROFILE\.codex\hooks.json"
          Select-String -Path "$env:USERPROFILE\.codex\beast-enterprise.config.toml" -Pattern "danger-full-access"
      - name: Upload kit artifact
        uses: actions/upload-artifact@v4
        with:
          name: windows-ready
          path: dist/PrivateBrain-WINDOWS-READY.zip
```

That’s the **“first approach” proof** without your work Neo4j.

### 4.3 Release — `release.yml`

On tag `v*`:

1. freeze_for_corporate  
2. nuclear_x10  
3. Create GitHub Release  
4. Attach:
   - `PrivateBrain-WINDOWS-READY.zip` + `.sha256`  
   - `PrivateBrain-MAC-READY.zip`  
   - `PrivateBrain-CORPORATE-*.zip`  
5. Write release notes from Day-1 checklist + nuclear band  

---

## 5. Optional “sky’s the limit” tracks (phased)

| Phase | What | Value |
|-------|------|--------|
| **P0** | Public repo + README/DIAGRAM + CI nuclear + Windows smoke | Ship credibility |
| **P1** | Release pipeline + checksums | One-click download for Monday |
| **P2** | Neo4j intelligent ingest (optional extra, docker Neo4j service in CI with synthetic dirty data) | Prove dirty→clean path |
| **P3** | PDF plan judge (sample public plan fixture) | KEEP/FLAG/REJECT demo |
| **P4** | Self-hosted Mac runner for GodsEye GL | Visual smoke |
| **P5** | SBOM + CodeQL + scorecard | Enterprise trust signals |
| **P6** | Website / GitHub Pages from DIAGRAM | Story for outsiders |

**Private repo later:** `private-brain-corporate` (private) for golden_join fixtures, Neo4j integration tests, PDF with export control — Actions still work; minutes not free forever on private.

---

## 6. Naming & positioning

| Option | Pros |
|--------|------|
| **`private-brain`** | Clean product name |
| **`private-brain-codex`** | Clear Codex sideload positioning |
| **`codex-private-brain`** | SEO for Codex users |

Tagline options:

- *Local memory organism for Codex. Cite or refuse.*  
- *Install once. Open Codex. Talk. Dual OS. Zero-fail Windows CI.*  

Topics: `codex`, `rag`, `knowledge-graph`, `sideload`, `enterprise`, `windows`, `github-actions`

---

## 7. Security for a public repo

1. **Never** commit `.env`, `.brain`, tokens, work Neo4j dumps  
2. Pre-commit / CI: `gitleaks` or `trufflehog`  
3. `SECURITY.md` + private vulnerability reporting  
4. Branch protection: require `ci.yml` + `windows-first-boot.yml` green  
5. Dependabot for Actions + pip  
6. No `danger-full-access` **secrets** in logs — only assert strings in profiles  

---

## 8. Day-1 for *GitHub* (parallel to product Day-1)

```text
[ ] Create public repo KRNichols/private-brain
[ ] Push sanitized tree (no .brain, no env secrets)
[ ] Workflows already scaffolded under private-brain-codex/.github/workflows/
      ci.yml | windows-first-boot.yml | mac-first-boot.yml | dual-os-matrix.yml
[ ] Confirm Actions green on:
      [ ] ubuntu-latest
      [ ] windows-latest
      [ ] macos-latest
[ ] Tag v0.1.0 → Release with WINDOWS-READY.zip + MAC-READY.zip
[ ] README points to Release assets + Day-1 checklist
[ ] Optional: private sibling for Corporate fixtures later
```

### Mac runner notes

| Job | Runner | Proves |
|-----|--------|--------|
| `ci.yml` → nuclear | `macos-latest` | Scripts compile + nuclear on Mac Python |
| `mac-first-boot.yml` | `macos-latest` | Extract MAC-READY → `START.command` → hooks/profile |
| `dual-os-matrix.yml` | `macos-latest` | Nightly parity with Windows/Ubuntu |
| GodsEye GL FPS | Hosted Mac is flaky | Soft / continue-on-error; optional self-hosted Mac later |

**Parity law:** Windows and Mac READY smokes must both stay green — same product, different launcher.

---

## 9. Honest limits

| Want | Reality |
|------|---------|
| Free Windows CI forever | **Public** standard runners: free; private: quota |
| Test real Corporate Neo4j in public CI | **No** — synthetic Neo4j service or private repo |
| GodsEye FPS on free Windows runner | **Unreliable** (no real GL stack) — static + optional self-hosted |
| “Spin infinite agents” | Possible but **against your product law** — CI should assert **results**, not agent count |

---

## 10. Suggested first PR after create

1. Import engine + installers from freeze (sanitized)  
2. Root README = Day-1 checklist (already written)  
3. Workflows as above  
4. Issue #1: “Windows first-boot must stay green”  
5. Issue #2: “Neo4j intelligent ingest (optional plane)”  
6. Issue #3: “PDF plan KEEP/FLAG/REJECT”  

---

## Bottom line

| Question | Answer |
|----------|--------|
| Public repo on github.com/KRNichols? | **Yes — great idea** |
| Pipelines? | **GitHub Actions** |
| Windows runner? | **`runs-on: windows-latest`** — free on **public** repos |
| Sky’s the limit? | Matrix CI, releases, Neo4j service tests, Pages, scorecard — **phase it** |
| Your bar (real results)? | Windows job must prove: extract → START headless → hooks + danger profile exist — not badge spam |

**Next step when you say go:** create `KRNichols/private-brain`, push sanitized tree, land `ci.yml` + `windows-first-boot.yml`, cut `v0.1.0` with the READY zip.
