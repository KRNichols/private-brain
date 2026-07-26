# abilities/

**Anyone:** what the sideload *can do* without you learning flags.  
**Senior:** hooks + organism water-pipe + optional GodsEye.

| Ability | Anyone | Engine |
|---------|--------|--------|
| Wake on Codex open | automatic | `engine/hooks/session_start.py` |
| Understand your prompt | automatic | `engine/hooks/user_prompt_submit.py` |
| Harvest sessions | automatic | smart_discover / session ingest |
| Local brain build | after START | `engine/scripts/organism.py` |
| GodsEye map | say `show GodsEye` | `engine/visualizer/graph_gl.py` |
| Autopilot / heal under floor | chat forensics | `engine/scripts/autopilot.py` · enterprise |

Daily ability surface is **conversation**, not a CLI menu.
