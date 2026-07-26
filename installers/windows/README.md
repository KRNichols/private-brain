# Private Brain — Windows

**Codex sideload.** One install. Then only talk. No flag dance.

**Mac ≡ Windows** until you drop Corporate `golden_join.json` next to START.

## Picture first (read this)

| File | Who |
|------|-----|
| **[`START_HERE.md`](./START_HERE.md)** | **Anyone** + **Senior** entry |
| **[`DIAGRAM.md`](./DIAGRAM.md)** | One picture · Layer A / Layer B |
| [`DIAGRAM.txt`](./DIAGRAM.txt) | Notepad-only / mermaid blocked |
| [`GODSEYE_HELP.md`](./GODSEYE_HELP.md) | GodsEye: simple + advanced help |
| [`golden_join.example.json`](./golden_join.example.json) | Empty shell — **await Corporate golden** |

```text
You talk → brain remembers → Codex answers with proof → GodsEye shows the map
```

## Install once

1. Quit Codex completely.  
2. Extract this **`windows\`** folder (or CORPORATE zip → open **`windows\`** only).  
3. PowerShell:

```powershell
cd X:\path\to\windows
Set-ExecutionPolicy -Scope Process Bypass
.\START.ps1
```

Answer the short map (packages · GitLab · Jira · Confluence · AWS) **or** drop real `golden_join.json` from the Corporate machine (no secrets) next to START — **skips re-interview**.

## Every day

**Open Codex.** Talk. That is the product.

Hooks are sideloaded at install — no daily shell command.

| Piece | Behavior |
|-------|----------|
| **Beast** | **On every Codex open** (session start) |
| **Stop beast** | Say `stop beast mode` / `normal mode` → RAG off **this session** |
| **Reopen Codex** | Beast **on again** automatically |
| **GodsEye** | Say `show GodsEye` if you want the map |
| **Sessions** | Harvested on session start |
| **Shell `beastMode`** | Optional power tool only — not required |

## GodsEye (simple)

| Key | Action |
|-----|--------|
| drag / scroll | pan / zoom |
| click | select (floating sheet) |
| **I** | Inspector (ops rail) |
| **H** | help (simple ↔ advanced) |
| **Esc** | close overlay → quit |
| **Q** | quit |

## Talk only (Codex chat)

| Say | Does |
|-----|------|
| normal work | RAG concert + cite-or-block (default) |
| `stop beast mode` / `normal mode` | RAG **off** this session |
| `beast mode` | RAG **on** again this session |
| reopen Codex | beast **auto on** |
| `fire drill` / `doctor` / `heal yourself` / `show metrics` | Forensics |
| `show golden config` / `add co-worker` | Map / join kit |
| `day brief` / `phase 2 handoff` | Air-gap MD for Grok |
| `show GodsEye` | Reopen HUD |

## Models (US sovereign / OpenAI enterprise only)

- Edge: **gpt-5.1** US sovereign (if account allows; else set `PB_EDGE_MODEL` once)  
- AWS: **enterprise-frontier-model** · **gov-region-1** when SHIM is up  
- **Do not invent Corporate endpoints** — wait for golden_join from work machine  

## Uninstall

```powershell
.\UNINSTALL.ps1
```

**Never email tokens.** Secrets → secrets store only.
