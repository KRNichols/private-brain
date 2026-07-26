# START HERE — Private Brain

**Mac and Windows are the same product.**  
Same water pipe. Same docs. Same GodsEye. Same talk-only Codex.

Corporate golden configuration is **not baked in**. Until you drop `golden_join.json` from the Corporate machine next to `START`, both OS installers run a **neutral map** (interview or headless). No invented hosts. No fake tokens.

| You are… | Go to |
|----------|--------|
| **Anyone** | [Section A](#a--anyone--just-use-it) |
| **Senior** | [Section A](#a--anyone--just-use-it) then [Section B](#b--senior-engineers--own-it) |

Picture: [`DIAGRAM.md`](./DIAGRAM.md) · GodsEye: [`GODSEYE_HELP.md`](./GODSEYE_HELP.md)

---

## A · Anyone — just use it

### Three steps (identical on both OS)

| When | Windows | Mac |
|------|---------|-----|
| **Once** | `.\START.ps1` | `./START.command` |
| **Every day** | **Open Codex** | **Open Codex** |
| **Work** | talk | talk |

```text
Install once → open Codex → talk.
You talk → brain remembers → Codex answers with proof → GodsEye shows the map
```

**You do not run a daily shell launcher.** After install, hooks are sideloaded into Codex.  
Beast is **on every time Codex opens**. Say **`stop beast mode`** (or `normal mode`) to pause RAG for that session. **Reopen Codex → beast on again.**

### When Corporate golden arrives

1. Copy **`golden_join.json`** (no secrets) from the Corporate machine.  
2. Place it **next to START** in either `windows/` or `mac/` (or both — same file).  
3. Run START again → **skips re-interview**, applies shared map, ingests **this machine’s** sessions.

Until then: answer the short map yourself, or use headless route.  
Example shell (empty): `golden_join.example.json`.

### GodsEye (same)

- **H** = help simple ↔ advanced · **I** = inspector · drag/scroll/click  
- Full help: [`GODSEYE_HELP.md`](./GODSEYE_HELP.md)

### Talk in Codex (product control surface)

| Say | Does |
|-----|------|
| normal work | RAG + cite-or-block (beast default) |
| `stop beast mode` / `normal mode` | RAG **off** this session |
| `beast mode` | RAG **on** again this session |
| reopen Codex | beast **auto on** again |
| `show GodsEye` | reopen map |
| `fire drill` / `doctor` / `heal yourself` | forensics |
| `day brief` | air-gap handoff MD |

Optional shell `beastMode` = power tool (forensics flags / force open Codex profile). **Not required daily.**

---

## B · Senior engineers — own it

### Parity rule

```text
mac/  ≡  windows/
  same package engine
  same dual-audience docs
  same organism water-pipe
  same enterprise profile defaults
  same US sovereign model intent (gpt-5.1 · GSS 120B · gov-region-1)
  golden_join only when YOU provide it from Corporate
```

### Layout after extract

```text
PrivateBrain-…/
  START_HERE.txt          ← pick OS
  mac/
    START.command
    README.md
    START_HERE.md · DIAGRAM.md · GODSEYE_HELP.md
    golden_join.example.json
    package/              ← engine (identical twin of windows/package)
  windows/
    START.ps1 · START.cmd
    README.md
    START_HERE.md · DIAGRAM.md · GODSEYE_HELP.md
    golden_join.example.json
    package/              ← same engine
```

Or use OS-only READY zips (`PrivateBrain-MAC-READY.zip` / `PrivateBrain-WINDOWS-READY.zip`) — still same docs + package.

### Live path after install

```text
Mac:     ~/.codex/private-brain/
Windows: %USERPROFILE%\.codex\private-brain\
```

### Quality

```bash
# either OS, from live install
python scripts/fire_drill.py
python scripts/brutal_suite.py
```

### Non-negotiables

1. Local zero-fail first — missing Corporate Library/AWS/Jira is soft  
2. US sovereign models only on work path  
3. Cite-or-block in beast/enterprise  
4. Secrets store only — never in golden_join  
5. Zip = code only · `.brain` grows after START  
6. **No Corporate hosts until golden_join from Corporate machine**

---

*If Mac docs ever say “lab only” or Windows docs say “Corporate only,” treat that as a bug — this file wins.*
