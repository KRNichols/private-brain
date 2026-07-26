# ROLE: visualizer

Keep OpenGL graph truthful.

1. Ensure snapshot built
2. Launch/restart `graph_gl.py` if dead
3. audit `viz_start` / `viz_heartbeat`
4. On snapshot change, rely on mtime reload (or signal S)
5. No crawls, no content mutation except layout.json optional positions
