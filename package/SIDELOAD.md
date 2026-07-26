# Private Brain = Codex sideload (not a second CLI)

Codex owns the product. Private Brain is **wired into** `~/.codex` via hooks + profiles.
You never “run Private Brain instead of Codex.”

## User commands (arguments turn features on)

| What you want | Command |
|---------------|---------|
| Beast mode, **no GUI** (default) | `beastMode`  or  `codex -p beast` |
| Beast + **GodsEye live GUI** | `beastMode -GodsEye`  or  `beastMode --godseye` |
| Beast + **32-agent shared-graph swarm** | `beastMode --swarm 32` |
| GUI **and** swarm | `beastMode -GodsEye --swarm 32` |
| Nuclear approvals bypass | `beastMode --nuclear`  or  `codex --dangerously-bypass-approvals-and-sandbox -p beast` |
| Inside Codex chat | `/prompts:beastMode`  ·  `/prompts:beastModeGodsEye` |

`beastMode` is only a thin wrapper that **parses feature flags, sets env, optionally starts GUI, then `exec`s codex**. It is not a separate product.

### Feature flags (args → env)

| Argument | Env set | Effect |
|----------|---------|--------|
| `-GodsEye` / `--godseye` | `PB_GODSEYE=1` | Start live command-center GUI; profile `beast-godseye` |
| `--no-gui` | `PB_GODSEYE=0` | Force headless |
| `--swarm N` | `PB_SWARM_AGENTS=N` | Fan-out N agents on shared topology before concert |
| `--nuclear` | (codex flag) | Extra danger-full-access bypass |

You can also set env yourself and call pure codex:

```bash
export PB_GODSEYE=1
export PB_SWARM_AGENTS=16
codex --dangerously-bypass-hook-trust -p beast-godseye
```

### GodsEye close behavior

Closing the GUI marks **dismissed** — concert/boot will **not** force-reopen it.
Passing `-GodsEye` again (or `python scripts/godseye.py start`) is an explicit reopen.

## What gets sideloaded into Codex

| Path | Role |
|------|------|
| `~/.codex/hooks.json` | SessionStart / UserPromptSubmit / Stop → RAG-DAG |
| `~/.codex/beast.config.toml` | Headless beast profile |
| `~/.codex/beast-godseye.config.toml` | GodsEye profile name |
| `~/.codex/private-brain/` | Engine (scripts, hooks, visualizer) |
| `~/bin/beastMode` | Arg-driven thin launcher → codex |

## Install / uninstall

| Action | How |
|--------|-----|
| Install | Double-click `SETUP.command` (Mac) / `SETUP.cmd` (Windows) |
| Uninstall | Double-click `UNINSTALL.command` / `UNINSTALL.cmd` |
| Or | `python -m private_brain sideload` / `python -m private_brain uninstall` |

## Not a product CLI

These are **maintainer helpers only** (not end-user surface):

```text
python -m private_brain doctor
python -m private_brain sideload
python -m private_brain uninstall
python scripts/agent_swarm.py sweep --agents 32   # same as beastMode --swarm 32 under the hood
```

End user always: **`codex`** or **`beastMode [args]`**.
