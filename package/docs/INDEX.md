# Documentation index

**Start:** [`../START_HERE.md`](../START_HERE.md)

| Doc | Anyone | Senior | Purpose |
|-----|:------:|:------:|---------|
| [START_HERE.md](../START_HERE.md) | ✓ | ✓ | Entry · how to use |
| [DIAGRAM.md](DIAGRAM.md) | ✓ | ✓ | One picture (Layer A + B) |
| [DIAGRAM.txt](DIAGRAM.txt) | ✓ | | Notepad-only diagram |
| [GODSEYE_HELP.md](GODSEYE_HELP.md) | ✓ | ✓ | Map UI help |
| [LOOP_GRAPH_SOVEREIGN.md](LOOP_GRAPH_SOVEREIGN.md) | | ✓ | Loop + graph + models |
| [MERMAID.md](MERMAID.md) | | ✓ | Full mermaid set |
| [KINGDOM_KEYS.md](KINGDOM_KEYS.md) | | ✓ | Integrations keys |
| [../installers/windows/README.md](../installers/windows/README.md) | ✓ | ✓ | Windows install |
| [../MISSION_MONDAY.md](../MISSION_MONDAY.md) | | ✓ | Monday mission |
| [../READY.md](../READY.md) | | ✓ | Enterprise ready |
| [../SIDELOAD.md](../SIDELOAD.md) | | ✓ | Sideload model |

## Windows zip root (what they open)

```text
DIAGRAM.md      ← picture first
DIAGRAM.txt
README.md       ← install
START.ps1
package/docs/   ← GODSEYE_HELP + DIAGRAM copies
```

## Quality commands

```bash
python scripts/brutal_suite.py
python scripts/fire_drill.py
ruff check scripts visualizer
```
