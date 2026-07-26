# GodsEye help

**In the app:** press **H** — toggles simple ↔ advanced help.  
**Esc** closes help. **I** opens the engineer Inspector.

---

## Anyone (simple)

### What you are looking at

A **map of your Private Brain**. Colored islands are groups of knowledge (sessions, tickets, wiki, code).

### What to do

| Action | Result |
|--------|--------|
| **Drag** | Move the map |
| **Scroll** | Zoom in / out |
| **Click** a dot | Short name card |
| **Double-click** | Zoom to that thing |
| **H** | This help (simple / advanced) |
| **I** | Engineer details (optional) |
| **Q** or **Esc** | Quit (Esc closes help first) |

### Status

- Green **Healthy** pill (top-left) = system good  
- You do **not** need metrics, stages, or FPS to work  

### If the window is confusing

1. Press **H** → read **SIMPLE** column  
2. Press **0** (zero) to fit the whole map  
3. Press **I** only if someone asked for ops numbers  
4. Chat in Codex still works if you close GodsEye  

---

## Senior engineers (advanced)

### Defaults (Apple-simple)

| Setting | Default | Toggle |
|---------|---------|--------|
| Full-bleed graph | on | — |
| Inspector ops rail | **off** | **I** |
| Minimap | **off** | **M** |
| Stages strip | compact (in Inspector) | **P** |
| Layout | LIVE micro-motion | **Space** freeze |
| Selection | floating sheet | click / Esc clear |

### Power keys

| Key | Action |
|-----|--------|
| **I** | Inspector: STATUS · STAGES · VECTOR · METRICS · EVIDENCE · ACTIVITY |
| **R** | Reseed constellation layout |
| **S** | Force reload snapshot + last DAG |
| **F** / **T** | Cycle source / tier filter |
| **1–4** / **5** | Tier T0–T3 / all |
| **E** | Evidence path autoplay (last concert) |
| **L** | Source legend with counts |
| **N** | Light 1-hop neighbors of selection |
| **[ ]** | Walk origin trail |
| **0** / **Home** | Camera fit |
| **M** | Minimap |
| **P** | Stages compact ↔ expanded (opens Inspector) |

### No window bleed

- Graph scissored to `graph_rect()`  
- Inspector scissored to right rail  
- Text via `TextCache` + `_clip_box` — nothing draws past window edges  

### Perf / telemetry

```text
.brain/state/godseye_perf.json      fps · lod · simple_mode · ultra
.brain/state/godseye_metrics.json   doctor/fire_drill facing
```

Target: **≥28 FPS** settled (prefer ~45–55 on Metal/NVIDIA). Caps: SNAPSHOT_VIZ_MAX / DRAW_* / adaptive LOD.

### GPU path

- Preferred: `apple_metal_gl+vbo` (Mac) / NVIDIA GL + VBO (Windows Corporate)  
- Fallback: CPU `live_gui.py` if GL packages missing  
- Headless route: GodsEye off — RAG still works  

### Dual-audience in code

Help panel shows **SIMPLE** and **ADVANCED** sections; **H** cycles focus.  
Docs ship in Windows zip: `DIAGRAM.md` + this file under `package/docs/`.
