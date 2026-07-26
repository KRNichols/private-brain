# Private Brain — what this sideload is

**One picture. Two readers.**

| You are… | Read |
|----------|------|
| **Anyone** | The fat boxes + the one-liner |
| **Senior engineer** | Everything including the thin layer under the floor |

---

## The one-liner

```text
  INSTALL ONCE  →  OPEN CODEX  →  TALK
       │                │            │
       │                │            └─ answers with proof (or refuses)
       │                └─ hooks wake the brain automatically
       └─ wires Codex so it is not empty-headed about YOUR work
```

**Why it matters:** stock Codex only knows the chat and what it can reach online.  
This sideload makes Codex remember **your** tickets, code, sessions, and wiki — **on this laptop** — and **block** answers that invent sources.

---

## Layer A · Anyone (super simple)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOU (human)                                     │
│              open Codex · talk · optionally stop beast mode             │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CODEX  (the product you already use)                                   │
│  Private Brain is SIDELOADED — not a second app to learn                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ hooks (automatic)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PRIVATE BRAIN  (the memory + rules under the floor)                    │
│                                                                         │
│   REMEMBERS          ANSWERS              SHOWS                         │
│   your work on disk  only with proof      GodsEye map (optional)        │
│   sessions·tickets   or says "I don't                                   │
│   wiki·code          know"                                              │
└─────────────────────────────────────────────────────────────────────────┘

Daily: open Codex. Talk.
Pause RAG: say "stop beast mode"  →  this session only
Reopen Codex: beast turns back ON automatically
Corporate map: drop golden_join.json when you have it (no secrets in the file)
```

### Why this is important (anyone)

| Without sideload | With Private Brain |
|------------------|--------------------|
| Model freestyles | Model must **cite** graph nodes or get **blocked** |
| Yesterday’s chat is gone | Sessions **ingest** into a local brain |
| You babysit flags | You **talk** — fire drill, heal, GodsEye by name |
| Pretty notes rot | Graph must **link** or it is a warehouse |

---

## Layer B · Senior engineers (what is actually running)

```text
┌─ CODEX SURFACE ──────────────────────────────────────────────────────────┐
│  Chat · tools · hooks.json (SessionStart · UserPromptSubmit · Stop)      │
│  conversation_mode: beast (default each open) | normal (user pause)      │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  ABILITIES    │         │  INTELLIGENCE   │         │  NON-HALLUC.    │
│  hooks boot   │         │  RAG-DAG concert│         │  cite-or-block  │
│  organism     │         │  retrieve→…→emit│         │  critic stage   │
│  sessions     │         │  local vectors  │         │  stop_validate  │
│  GodsEye GL   │         │  US sovereign   │         │  quarantine     │
└───────┬───────┘         └────────┬────────┘         └────────┬────────┘
        │                          │                           │
        └──────────────────────────┼───────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  .brain/  nodes · edges · content · index · state  (NEVER in the zip)    │
│  ship gate: pilot_ops / quarantine · audit chain · secrets store         │
└──────────────────────────────────────────────────────────────────────────┘

 tools/ folder maps 1:1 to these planes (see tools/README.md)
```

### Concert DAG (hallucination wall)

```text
boot → retrieve → validate → synthesize → critic → rate → emit
                 │              │            │
                 │              │            └─ FAIL empty/uncited → re-route
                 │              └─ bullets must carry `node_id` cites
                 └─ no evidence → pass_for_answer=false
Stop hook: enterprise answer without graph cites → decision block
```

### Why this is important (senior)

1. **Sideload, not CLI product** — Codex owns UX; we own memory + gates.  
2. **Local zero-fail first** — missing Corporate Library/AWS/Jira is soft; laptop still works.  
3. **US sovereign path** — gpt-5.1 edge · GSS 120B · gov-region-1 when live.  
4. **Cite-or-block is law** in beast — not a suggestion.  
5. **Mac ≡ Windows** until Corporate `golden_join.json` arrives (no invented hosts).  
6. **Zip = code only** — corpus grows after START under `~/.codex/private-brain/.brain`.

---

## Folder you are looking at

```text
README.md     ← how to use (anyone + senior)
DIAGRAM.md    ← this file
tools/        ← broken out by job (skills · abilities · intelligence · …)
```

Nothing else at the root on purpose.
