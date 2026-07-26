# START HERE — Private Brain

**Two readers. One product.**

| You are… | Go to |
|----------|--------|
| **Anyone** (just use it) | [Section A](#a--anyone--just-use-it) |
| **Senior engineer** (own it) | [Section A](#a--anyone--just-use-it) then [Section B](#b--senior-engineers--own-it) |

Full picture: [`docs/DIAGRAM.md`](docs/DIAGRAM.md) · GodsEye: [`docs/GODSEYE_HELP.md`](docs/GODSEYE_HELP.md)

---

## A · Anyone — just use it

### What this is

A **memory for Codex on your laptop**. You talk. It remembers your work. Answers come with proof — or it says it doesn’t know.

### Three steps

```text
1. ONCE     →  START.ps1   (Windows)   or   START.command   (Mac)
2. EVERY DAY →  beastMode
3. WORK     →  talk in Codex
```

That’s the whole product.

### What you type in Codex

| Say | What happens |
|-----|----------------|
| normal work questions | Uses your local brain; cites or refuses |
| `show GodsEye` | Opens the map of your brain |
| `fire drill` / `doctor` / `heal yourself` | Health check |
| `day brief` | Writes a handoff file for offline Grok |

### GodsEye in 10 seconds

- **Dots** = things your brain knows  
- **Drag** = move · **Scroll** = zoom · **Click** = name card  
- Green **Healthy** pill = good  
- **H** = help (simple + advanced) · **I** = engineer panel · **Q** = quit  

Details: [`docs/GODSEYE_HELP.md`](docs/GODSEYE_HELP.md)

### If something’s wrong

| Problem | Fix |
|---------|-----|
| Don’t know where to start | This file · then `START` |
| Codex feels dumb | Run `beastMode` · talk again |
| No map window | Chat still works · try `show GodsEye` |
| Install asks packages | At Corporate pick **corporate-library** · offline pick **headless** |

### One-line truth

```text
You talk → brain remembers → Codex answers with proof → GodsEye shows the map
```

---

## B · Senior engineers — own it

### System shape

| Layer | Role |
|-------|------|
| **Surface** | Codex chat + conversation_router (no flag dance) |
| **Organism** | day1 map → local RAG-DAG → GodsEye → agents → AWS probe |
| **Concert** | retrieve → validate → synthesize → critic → emit (cite-or-block) |
| **Models** | **US sovereign only** · gpt-5.1 edge · enterprise-frontier-model · gov-region-1 |
| **Ship gate** | pilot_ops / quarantine — not “looks fine” theater |
| **Parent offline** | airgap_brief / PHASE2_HANDOFF MD for Grok |

Architecture canvas: [`docs/DIAGRAM.md`](docs/DIAGRAM.md) Layer B · loop/graph: [`docs/LOOP_GRAPH_SOVEREIGN.md`](docs/LOOP_GRAPH_SOVEREIGN.md)

### Live paths

```text
~/.codex/private-brain/          live sideload (Mac home)
%USERPROFILE%\.codex\private-brain\   live (Windows Corporate)

  scripts/     beastMode · organism · fire_drill · brutal_suite
  visualizer/  graph_gl.py   (GodsEye · simple default)
  hooks/       session_start · user_prompt_submit · stop_validate
  .brain/      corpus (never shipped in zip)
  docs/        dual-audience documentation
```

### Quality bar (run until green)

```bash
# from live install
python scripts/brutal_suite.py          # full attack packs
python scripts/fire_drill.py            # dual-OS static + live gates
ruff check scripts visualizer           # syntax / undefined
```

Windows ship: extract **`PrivateBrain-WINDOWS-READY.zip`** → open **`DIAGRAM.md`** → `START.ps1`.

### Non-negotiables

1. **Local zero-fail first** — missing Corporate Library/AWS/Jira is soft, not a hard crash  
2. **No public model path** on work — no Kimi / Opus  
3. **Cite-or-block** — refuse ungrounded answers  
4. **Secrets store only** — never paste tokens into chat or README  
5. **Zip = code only** — `.brain` grows after START  

### Doc map

| Doc | Audience | Purpose |
|-----|----------|---------|
| **START_HERE.md** (this) | both | entry |
| **docs/DIAGRAM.md** | both | one picture |
| **docs/GODSEYE_HELP.md** | both | map UI |
| **docs/LOOP_GRAPH_SOVEREIGN.md** | senior | loop + graph + models |
| **docs/MERMAID.md** | senior | full mermaid set |
| **docs/KINGDOM_KEYS.md** | senior | GitLab/Jira/Confluence/AWS |
| **installers/windows/README.md** | both | Windows install |
| **MISSION_MONDAY.md** | senior | Monday mission design |
| **READY.md** / **SIDELOAD.md** | senior | enterprise / sideload detail |

---

*If a doc fights this file, this file wins for “how to use.” Architecture truth lives in DIAGRAM Layer B.*
