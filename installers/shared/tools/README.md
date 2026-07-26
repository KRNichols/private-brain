# tools/ — planes of the sideload

Each folder is a **job**. Open its `README.md`.  
Runnable code for install lives under **`engine/`** (and **`install/`** launchers).

| Folder | Job | Anyone | Senior |
|--------|-----|--------|--------|
| **[install/](./install/)** | Wire Codex once | Run START | SETUP paths · golden_join |
| **[skills/](./skills/)** | What agents know how to do | Swarm roles | agent cards · codex-agents |
| **[abilities/](./abilities/)** | What the organism can do | Sessions · GodsEye | hooks · organism · autopilot |
| **[intelligence/](./intelligence/)** | How it thinks | “remembers work” | RAG-DAG · concert · models |
| **[rulings/](./rulings/)** | Law / policy | Don’t invent hosts | golden · kingdom · judge policies |
| **[judging/](./judging/)** | Health & critique | fire drill / doctor (chat) | doctor · brutal · critic stage |
| **[non_hallucination/](./non_hallucination/)** | Truth wall | “must cite or refuse” | citation_gate · stop_validate · quarantine |
| **[metrics/](./metrics/)** | Pulse | Healthy pill | ops_metrics · purity · godseye_perf |
| **[engine/](./engine/)** | The code | ignore | scripts · hooks · visualizer · config |

```text
 Codex chat ──hooks──► abilities + intelligence
                            │
                            ▼
                     non_hallucination (wall)
                            │
                            ▼
                     .brain graph + metrics
                            │
                     rulings (golden / kingdom)
```

Root of this kit only exposes **README + DIAGRAM + tools/** on purpose.
