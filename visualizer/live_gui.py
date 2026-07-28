#!/usr/bin/env python3
"""
Private Brain LIVE OPS — knowledge graph + concert pipeline dashboard.

Sideload visualizer (GodsEye). Not a separate product.

Capacity (approx, laptop):
  Sample hold:  SNAPSHOT_VIZ_MAX = 10k nodes kept after smart sample
  Draw:         DRAW_NODES / DRAW_EDGES (matched to sample so 10k is visible)
  Layout:       force-sim still samples LAYOUT_MAX only (keeps settle cheap)
  Note:         pure CPU pygame — large draws can lower FPS; layout still samples LAYOUT_MAX

  hover   tooltips / flyouts on nodes & stages
  H       help / color legend (traffic lights)
  drag    pan graph · wheel zoom
  click   select node
  R       reshuffle islands (keeps continuous live motion)
  Space   pause ↔ resume live layout (default is always moving)
  S       reload snapshot · Q quit
  Layout is LIVE by default — always doing something unless you pause.
  GodsEye is a CPU pygame dashboard (not GPU; does not accelerate RAG/memory).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

try:
    import pygame
except ImportError:
    raise SystemExit("pip install pygame  (in private-brain venv)")


# ── Viz capacity caps ────────────────────────────────────────────────────────
LAYOUT_MAX = 400          # light polish only (islands are structured, not a force-box)
LAYOUT_PAIR_K = 12
LAYOUT_SETTLE_TICKS = 35  # brief polish then freeze — no square fill
DRAW_NODES = 10000
DRAW_EDGES = 12000
SNAPSHOT_VIZ_MAX = 10000

# Types treated as low-priority "chunk-like" for sampling (prefer non-chunk)
_CHUNK_TYPES = frozenset({
    "Comment", "MRComment", "SessionTurn", "BrainChunk",
    "Pipeline", "SwarmCrumb", "Chunk",
})
_TIER_RANK = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}

# Edge relations that usually mean "this came from / belongs to" when walked inbound
_ORIGIN_RELS = frozenset({
    "HAS_ISSUE", "HAS_MR", "HAS_COMMENT", "HAS_PIPELINE", "HAS_RELEASE",
    "CONTAINS", "PARENT_OF", "HAS_TURN", "HAS_AGENT", "CONTAINS_FILE",
    "HAS_TREE", "HAS_BRANCH", "HAS_PAGE", "HAS_WIKI", "REFERENCES",
    "SWARM_TAGGED", "HAS_CHUNK", "NEXT_CHUNK",
})


def _node_sample_key(n: dict) -> tuple:
    """Sort key for viz sampling — lower is preferred.

    Prefer non-chunk, then high tier (T0–T2), stable by id.
    """
    is_chunk = 1 if (n.get("type") or "") in _CHUNK_TYPES else 0
    tier = _TIER_RANK.get(str(n.get("tier") or "T3"), 4)
    return (is_chunk, tier, str(n.get("id") or ""))


def sample_nodes_for_viz(raw_nodes: list[dict], max_n: int) -> list[dict]:
    """Pick up to max_n nodes: non-chunk + T0–T2 first, diverse sources.

    Round-robin across sources so one noisy source cannot dominate.
    Within each source, nodes are ordered by _node_sample_key.
    """
    if len(raw_nodes) <= max_n:
        return list(raw_nodes)
    by_source: dict[str, list[dict]] = defaultdict(list)
    for n in raw_nodes:
        by_source[str(n.get("source") or "unknown")].append(n)
    for bucket in by_source.values():
        bucket.sort(key=_node_sample_key)
    sources = sorted(by_source.keys())
    selected: list[dict] = []
    ptr = {s: 0 for s in sources}
    while len(selected) < max_n:
        progressed = False
        for src in sources:
            if len(selected) >= max_n:
                break
            i = ptr[src]
            bucket = by_source[src]
            if i < len(bucket):
                selected.append(bucket[i])
                ptr[src] = i + 1
                progressed = True
        if not progressed:
            break
    return selected


# ── Traffic-light palette (stop lights, not neon HUD) ────────────────────────
BG = (14, 16, 20)
PANEL = (22, 24, 30)
PANEL_2 = (28, 30, 38)
BORDER = (48, 52, 64)
BORDER_SOFT = (36, 40, 50)
TEXT = (230, 232, 238)
TEXT_DIM = (150, 156, 170)
TEXT_MUTED = (100, 106, 120)
ACCENT = (90, 140, 255)
# Stop lights
GREEN = (46, 204, 113)      # GO / ok / healthy
YELLOW = (241, 196, 15)     # CAUTION / running / warn
RED = (231, 76, 60)         # STOP / fail
GRAY = (100, 104, 118)      # pending / skip
CYAN = (80, 190, 210)

TIER_COLOR = {
    "T0": GREEN,           # highest trust wiki/docs
    "T1": (52, 152, 219),  # issues / plans
    "T2": YELLOW,          # projects / MRs
    "T3": GRAY,            # comments / crumbs
}
SOURCE_COLOR = {
    "gitlab": (230, 126, 34),
    "jira": (41, 128, 185),
    "confluence": (52, 152, 219),
    "codex_session": (155, 89, 182),
    "metrics": (26, 188, 156),
    "brain": (142, 68, 173),
}
STAGE_ORDER = [
    "boot", "swarm", "cost", "security", "retrieve", "crawl_gap",
    "validate", "metrics", "synthesize", "critic", "rate", "optimize", "emit",
]
STAGE_LABEL = {
    "boot": "Boot brain + snapshot",
    "swarm": "Multi-agent shared-graph sweep",
    "cost": "Budget / rate limits",
    "security": "Audit chain + secret scan",
    "retrieve": "Hybrid search (vector + lexical)",
    "crawl_gap": "Fill thin evidence (crawl)",
    "validate": "Evidence + chain gate",
    "metrics": "KPIs / signals / planning",
    "synthesize": "Bullets with citations",
    "critic": "Peer-review synthesis",
    "rate": "Concert quality band",
    "optimize": "Graph hygiene / reindex",
    "emit": "Pack context for Codex",
}
# Hover encyclopedia: what / why / when (config filled live from env + last_dag)
STAGE_EXPLAIN: dict[str, dict[str, str]] = {
    "boot": {
        "what": "Load graph snapshot, flags, and concert run_id.",
        "why": "Every concert needs a consistent brain root before agents touch the graph.",
        "when": "Always — first stage of every concert / dag_turn.",
    },
    "swarm": {
        "what": "N agents write/read one shared topology (no job queue).",
        "why": "Fan-out retrieval, tagging, linking, and gap-finding in parallel.",
        "when": "When PB_SWARM_AGENTS>0 (product default 16). Set 0 to skip.",
    },
    "cost": {
        "what": "Budget + crawl rate-limit checks before expensive work.",
        "why": "Stops unbounded crawl/API spend; enterprise cost law.",
        "when": "Always early in the concert (after boot/swarm).",
    },
    "security": {
        "what": "Verify append-only audit chain + secret scan posture.",
        "why": "Fail-closed enterprise: broken chain must not go silent.",
        "when": "Always before emit; may seal/retry on chain break.",
    },
    "retrieve": {
        "what": "Hybrid graph retrieve (lexical + vectors) into evidence.",
        "why": "Ground synthesis in real nodes (cite-or-block).",
        "when": "Always. Thin/empty evidence can re-route to crawl_gap.",
    },
    "crawl_gap": {
        "what": "Bounded crawl/ingest to fill thin evidence.",
        "why": "Recovery path when retrieve gap=true or empty evidence.",
        "when": "Only if retrieve is thin AND crawl allowed; else skip (cooldown/budget).",
    },
    "validate": {
        "what": "Gate evidence quality and concert structure.",
        "why": "Blocks garbage evidence from becoming confident answers.",
        "when": "Always after retrieve (+ optional crawl re-retrieve).",
    },
    "metrics": {
        "what": "KPIs, signals, planning metrics snapshot.",
        "why": "Feeds rate band + GodsEye metrics panel.",
        "when": "Always (parallel with validate).",
    },
    "synthesize": {
        "what": "Build cited bullets from evidence only.",
        "why": "Human-facing answer material with node_id cites.",
        "when": "Always after validate when evidence path runs.",
    },
    "critic": {
        "what": "Peer-review synthesis for hallucinations / weak cites.",
        "why": "Second mind before rate/emit; can demote score.",
        "when": "Always after synthesize in full concert.",
    },
    "rate": {
        "what": "Score concert quality → band (e.g. SAP_SHIP / PASS / FAIL).",
        "why": "Decides whether optimize is needed; operator dashboard.",
        "when": "Always after critic.",
    },
    "optimize": {
        "what": "Graph hygiene / reindex / no-relearn polish.",
        "why": "Repair weak concerts; avoid churn when already green.",
        "when": "Only if FAIL/weak score/critic FAIL or PB_ALWAYS_OPTIMIZE=1.",
    },
    "emit": {
        "what": "Pack final context for Codex (hooks inject).",
        "why": "Hand the model only recovered, cited graph context.",
        "when": "Always at end of concert when final_ok path completes.",
    },
}
STAGE_COLOR = {
    "pending": GRAY,
    "running": YELLOW,
    "ok": GREEN,
    "fail": RED,
    "skip": (80, 84, 96),
}

HELP_LINES = [
    "COLOR LEGEND (traffic lights)",
    "  GREEN  = GO     stage ok / system healthy / T0 tier",
    "  YELLOW = CAUTION stage running or soft warn / T2 tier",
    "  RED    = STOP   stage failed / critical issue",
    "  GRAY   = idle   pending or skipped / T3 tier",
    "",
    "TOP STATUS",
    "  Healthy = no concert stages in FAIL right now",
    "  Caution = some stages running (yellow)",
    "  Unhealthy = one or more stages FAIL (red)",
    "  Pipeline line names which stages are live (running)",
    "",
    "GRAPH DOTS",
    "  Fill color = knowledge tier (T0 best … T3 low)",
    "  Ring color = source (gitlab / jira / confluence / …)",
    "  Hover a dot for title, id, type, source, tier",
    "",
    "PIPELINE",
    "  Hover a stage for full description + last detail",
    "  Click a stage to pin its flyout",
    "",
    "KEYS  H help · 1 graph · 2 pipeline · 3 metrics",
    "      Space pause/resume live layout · R reshuffle · S reload · Q quit",
    "      drag pan · wheel zoom · × Close · layout is LIVE by default",
    "",
    "ORIGIN CRAWL (click a node)",
    "  Builds a trail: parent_id chain + graph edges (HAS_*, CONTAINS, …)",
    "  [ ] keys walk root ← → leaf. Enter loads on-disk content snippet.",
    "  Trail neighbors highlight on the graph so you can see lineage.",
]


def brain_home() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser()
    codex = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(codex) / "private-brain"


def brain_dir() -> Path:
    return brain_home() / ".brain"


class LiveState:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.pos: dict[str, list[float]] = {}
        self.vel: dict[str, list[float]] = {}
        self.snap_mtime = 0.0
        self.dag_mtime = 0.0
        self.events_offset = 0
        self.stage_status: dict[str, str] = {s: "pending" for s in STAGE_ORDER}
        self.stage_detail: dict[str, str] = {}
        self.last_run_id = ""
        self.final_ok: bool | None = None
        self.metrics: dict[str, Any] = {}
        self.vector_stats: dict[str, Any] = {}
        self.event_log: deque[str] = deque(maxlen=80)
        self.brain_stats: dict[str, Any] = {}
        self.selected: str | None = None
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.focus = 0
        self.tick = 0
        self.show_help = False
        self.activity_scroll = 0
        self.pinned_stage: str | None = None
        self.hover_node: str | None = None
        self.hover_stage: str | None = None
        # Snapshot capacity bookkeeping (full vs held for viz)
        self.snapshot_node_total = 0
        self.snapshot_edge_total = 0
        self.viz_capped = False
        # Layout is LIVE by default (continuous motion). Space pauses.
        self.layout_frozen = False
        self.layout_ticks = 0
        self.layout_energy = 0.0
        self.layout_w = 800.0
        self.layout_h = 600.0
        self._settle_then_freeze = False  # unused: product law is continuous live
        # Origin crawl: adjacency + trail from leaf → root
        # adj[nid] = list of (other_id, rel, "in"|"out")
        self.adj: dict[str, list[tuple[str, str, str]]] = {}
        self.trail: list[str] = []          # [selected, …, root]
        self.trail_rels: list[str] = []     # edge label into each step (trail[0] = "")
        self.trail_focus: int = 0           # index in trail (0 = clicked leaf)
        self.trail_snippet: str = ""
        self.trail_neighbors: list[tuple[str, str, str]] = []  # (id, rel, dir)
        # Neuron pathway (lit when a question's concert retrieve fires)
        self.lit_nodes: dict[str, float] = {}   # id → intensity 0..1 (decays)
        self.lit_edges: set[tuple[str, str]] = set()  # unordered pairs
        self.pathway_prompt: str = ""
        self.color_mode: str = "source"  # source | tier — source avoids mono-yellow blobs
        self.event_run_id: str = ""
        self._last_dag_data: dict[str, Any] | None = None

    def stage_counts(self) -> dict[str, int]:
        c = {"ok": 0, "fail": 0, "running": 0, "pending": 0, "skip": 0}
        for s in STAGE_ORDER:
            st = self.stage_status.get(s, "pending")
            c[st] = c.get(st, 0) + 1
        return c

    def running_stages(self) -> list[str]:
        return [s for s in STAGE_ORDER if self.stage_status.get(s) == "running"]

    def failed_stages(self) -> list[str]:
        return [s for s in STAGE_ORDER if self.stage_status.get(s) == "fail"]

    def health(self) -> tuple[str, tuple, str]:
        """(label, color, explanation)"""
        c = self.stage_counts()
        if c["fail"]:
            names = ", ".join(self.failed_stages()[:4])
            return (
                "UNHEALTHY",
                RED,
                f"{c['fail']} stage(s) FAILED: {names}. Red = stop / needs attention.",
            )
        if c["running"]:
            names = ", ".join(self.running_stages()[:5])
            return (
                "CAUTION",
                YELLOW,
                f"{c['running']} stage(s) RUNNING now: {names}. Yellow = in progress.",
            )
        if c["ok"] == 0 and c["pending"] == len(STAGE_ORDER):
            return (
                "IDLE",
                GRAY,
                "No concert has run yet this session. Open Codex with beastMode or wait for a prompt.",
            )
        return (
            "HEALTHY",
            GREEN,
            f"No failed stages. {c['ok']} of {len(STAGE_ORDER)} stages OK (green). Pipeline ready.",
        )

    def reload_snapshot(self, path: Path, w: int, h: int) -> None:
        if not path.exists():
            return
        m = path.stat().st_mtime
        if m == self.snap_mtime:
            return
        self.snap_mtime = m
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_nodes = list(data.get("nodes") or [])
        raw_edges = list(data.get("edges") or [])
        self.snapshot_node_total = len(raw_nodes)
        self.snapshot_edge_total = len(raw_edges)

        if len(raw_nodes) > SNAPSHOT_VIZ_MAX:
            picked = sample_nodes_for_viz(raw_nodes, SNAPSHOT_VIZ_MAX)
            keep = {n["id"] for n in picked if n.get("id")}
            self.nodes = {n["id"]: n for n in picked if n.get("id")}
            self.edges = [
                e for e in raw_edges
                if e.get("src") in keep and e.get("dst") in keep
            ]
            self.viz_capped = True
        else:
            self.nodes = {n["id"]: n for n in raw_nodes if n.get("id")}
            self.edges = raw_edges
            self.viz_capped = False

        self.brain_stats = data.get("stats") or {
            "viz_nodes": self.snapshot_node_total,
            "viz_edges": self.snapshot_edge_total,
        }
        # Prefer full-graph counts from snapshot stats when present
        if "viz_nodes" not in self.brain_stats:
            self.brain_stats["viz_nodes"] = self.snapshot_node_total
        if "viz_edges" not in self.brain_stats:
            self.brain_stats["viz_edges"] = self.snapshot_edge_total

        self.layout_w = float(max(200, w))
        self.layout_h = float(max(200, h))
        # Full reseed when node set changes a lot, else only missing ids
        need_seed = [nid for nid in self.nodes if nid not in self.pos]
        if need_seed:
            self._seed_island_positions(need_seed, self.layout_w, self.layout_h)
            # Keep LIVE motion after seed — never lock frozen on reload
            self.layout_frozen = False
            self.layout_ticks = 0
            for v in self.vel.values():
                # small kick so new islands start moving immediately
                v[0] = (random.random() - 0.5) * 0.4
                v[1] = (random.random() - 0.5) * 0.4
        for nid in list(self.pos.keys()):
            if nid not in self.nodes:
                del self.pos[nid]
                self.vel.pop(nid, None)
        self._rebuild_adjacency()
        # Keep selection if still present; refresh trail
        if self.selected and self.selected in self.nodes:
            self.select_node(self.selected)
        elif self.selected:
            self.clear_selection()
        cap_note = f"  (capped of {self.snapshot_node_total})" if self.viz_capped else ""
        self.event_log.appendleft(
            f"graph reload  nodes={len(self.nodes)}  edges={len(self.edges)}{cap_note}"
        )

    def _rebuild_adjacency(self) -> None:
        adj: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for e in self.edges:
            s, d = e.get("src"), e.get("dst")
            rel = str(e.get("rel") or "RELATED")
            if not s or not d:
                continue
            adj[s].append((d, rel, "out"))
            adj[d].append((s, rel, "in"))
        self.adj = dict(adj)

    def clear_selection(self) -> None:
        self.selected = None
        self.trail = []
        self.trail_rels = []
        self.trail_focus = 0
        self.trail_snippet = ""
        self.trail_neighbors = []

    def select_node(self, nid: str | None) -> None:
        """Select a node and build origin trail (crawl toward how it originated)."""
        if not nid or nid not in self.nodes:
            self.clear_selection()
            return
        self.selected = nid
        self.trail, self.trail_rels = self._build_origin_trail(nid)
        self.trail_focus = 0
        self.trail_neighbors = list(self.adj.get(nid) or [])[:24]
        self.trail_snippet = self._load_snippet(nid)
        self.event_log.appendleft(f"select  {nid[:48]}  trail={len(self.trail)}")

    def _build_origin_trail(self, nid: str) -> tuple[list[str], list[str]]:
        """Walk leaf → root via parent_id then inbound origin edges."""
        trail = [nid]
        rels = [""]  # rel into trail[i] from trail[i-1]
        seen = {nid}
        cur = nid
        for _ in range(16):
            n = self.nodes.get(cur) or {}
            # 1) explicit parent_id on node
            p = n.get("parent_id")
            if p and p not in seen:
                # parent might be outside viz sample — still record if in nodes or invent stub
                trail.append(str(p))
                rels.append("parent_id")
                seen.add(str(p))
                if str(p) not in self.nodes:
                    break
                cur = str(p)
                continue
            # 2) inbound graph edges that look like containment/origin
            inbound = [
                (o, r) for o, r, d in (self.adj.get(cur) or [])
                if d == "in" and o not in seen
            ]
            prefer = [(o, r) for o, r in inbound if r in _ORIGIN_RELS]
            cand = prefer or inbound
            if not cand:
                break
            # Prefer project/repo/session-like over comments
            def _rank(item: tuple[str, str]) -> tuple:
                o, r = item
                on = self.nodes.get(o) or {}
                t = str(on.get("type") or "")
                # lower is better
                type_pen = 0
                if "Comment" in t or "Chunk" in t or "Crumb" in t:
                    type_pen = 5
                elif "Session" in t or "Turn" in t:
                    type_pen = 1
                elif "Project" in t or "Repo" in t or "Group" in t:
                    type_pen = 0
                else:
                    type_pen = 2
                return (type_pen, 0 if r in _ORIGIN_RELS else 1, o)

            o, r = sorted(cand, key=_rank)[0]
            trail.append(o)
            rels.append(r)
            seen.add(o)
            cur = o
        return trail, rels

    def walk_trail(self, delta: int) -> None:
        if not self.trail:
            return
        self.trail_focus = max(0, min(len(self.trail) - 1, self.trail_focus + delta))
        nid = self.trail[self.trail_focus]
        if nid in self.nodes:
            self.selected = nid
            self.trail_neighbors = list(self.adj.get(nid) or [])[:24]
        self.trail_snippet = self._load_snippet(nid)

    def _load_snippet(self, nid: str, max_chars: int = 480) -> str:
        """Load on-disk content for a node if present (how text was captured)."""
        n = self.nodes.get(nid) or {}
        # Prefer content file conventions used by brain_lib
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", nid)[:180]
        candidates = [
            brain_dir() / "content" / f"{safe}.md",
            brain_dir() / "content" / f"{nid.replace(':', '_')}.md",
        ]
        cpath = n.get("content_path")
        if cpath:
            candidates.insert(0, brain_dir() / str(cpath))
        for p in candidates:
            try:
                if p.exists():
                    text = p.read_text(encoding="utf-8", errors="ignore").strip()
                    if text:
                        return text[:max_chars] + ("…" if len(text) > max_chars else "")
            except OSError:
                continue
        # Fall back to title + tags
        title = n.get("title") or nid
        tags = ", ".join((n.get("tags") or [])[:8])
        return f"{title}\n(source={n.get('source')} type={n.get('type')} tier={n.get('tier')})\ntags: {tags or '—'}\n(no content file on disk)"

    def _seed_island_positions(self, nids: list[str], w: float, h: float) -> None:
        """Constellation of source islands with empty space between — never a filled square.

        Each source (gitlab/jira/…) gets its own island center on a loose grid.
        Nodes pack inside that island via a golden-angle disk. Gaps between islands
        stay empty so the graph reads as structure, not a carpet of dots.
        """
        by_src: dict[str, list[str]] = defaultdict(list)
        for nid in nids:
            n = self.nodes.get(nid) or {}
            src = str(n.get("source") or "unknown")
            # Split huge sources into sub-islands so one source can't become a slab
            by_src[src].append(nid)

        # Build island list: split any source with many nodes into chunks
        islands: list[tuple[str, list[str]]] = []
        MAX_PER_ISLAND = 420
        for src, members in sorted(by_src.items()):
            members = list(members)
            # stable order: tier then id
            members.sort(
                key=lambda i: (
                    _TIER_RANK.get(str((self.nodes.get(i) or {}).get("tier") or "T3"), 9),
                    i,
                )
            )
            if len(members) <= MAX_PER_ISLAND:
                islands.append((src, members))
            else:
                parts = max(2, (len(members) + MAX_PER_ISLAND - 1) // MAX_PER_ISLAND)
                chunk = (len(members) + parts - 1) // parts
                for p in range(parts):
                    islands.append((f"{src}·{p+1}", members[p * chunk : (p + 1) * chunk]))

        n_islands = max(1, len(islands))
        # Grid of island centers with padding — empty gutters between cells
        aspect = w / max(h, 1.0)
        cols = max(1, int(math.ceil(math.sqrt(n_islands * aspect))))
        rows = max(1, int(math.ceil(n_islands / cols)))
        pad_x, pad_y = w * 0.06, h * 0.07
        cell_w = (w - 2 * pad_x) / cols
        cell_h = (h - 2 * pad_y) / rows
        # Island radius leaves ~35% gutter empty between neighbors
        island_r = 0.33 * min(cell_w, cell_h)
        golden = math.pi * (3.0 - math.sqrt(5.0))

        for ii, (_label, members) in enumerate(islands):
            if not members:
                continue
            col = ii % cols
            row = ii // cols
            icx = pad_x + cell_w * (col + 0.5)
            icy = pad_y + cell_h * (row + 0.5)
            n = len(members)
            for j, nid in enumerate(members):
                # Fibonacci disk inside island — density falls toward rim
                r = island_r * math.sqrt((j + 0.5) / n)
                a = j * golden
                # Tiny tier offset: T0 slightly inward, T3 slightly out
                tier = str((self.nodes.get(nid) or {}).get("tier") or "T3")
                r *= 0.88 + 0.04 * _TIER_RANK.get(tier, 3)
                self.pos[nid] = [icx + r * math.cos(a), icy + r * math.sin(a)]
                self.vel[nid] = [0.0, 0.0]

    def reload_dag(self, path: Path) -> None:
        if not path.exists():
            return
        m = path.stat().st_mtime
        if m == self.dag_mtime and self.last_run_id:
            return
        self.dag_mtime = m
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        rid = data.get("run_id") or ""
        if rid != self.last_run_id:
            self.last_run_id = rid
            self.stage_status = {s: "pending" for s in STAGE_ORDER}
            self.stage_detail = {}
            self.event_log.appendleft(f"concert  {rid[:28]}")
        self.final_ok = data.get("final_ok")
        self._last_dag_data = data
        self._apply_dag_stages(data)
        self.event_log.appendleft(
            f"dag update  final_ok={data.get('final_ok')}  critic={(data.get('critic') or {}).get('verdict')}"
        )

    def _apply_dag_stages(self, data: dict[str, Any]) -> None:
        """Authoritative stage lights from last_dag.json (wins over sticky 'running' events)."""

        def mark(name: str, blob: Any) -> None:
            if blob is None:
                # leave pending / prior unless final_ok forces idle
                return
            if not isinstance(blob, dict):
                return
            if blob.get("skipped"):
                self.stage_status[name] = "skip"
            elif blob.get("ok") is True:
                self.stage_status[name] = "ok"
            elif blob.get("ok") is False:
                self.stage_status[name] = "fail"
            else:
                self.stage_status[name] = "ok"
            detail = blob.get("detail") or blob.get("reason") or blob.get("band") or ""
            if name == "retrieve":
                detail = f"hits={blob.get('hit_count')}"
            if name == "metrics":
                # Compact one-line — never dump the whole signals dict into the panel
                sigs = blob.get("signals") or {}
                if isinstance(sigs, dict) and sigs:
                    bad = [k for k, v in sigs.items() if str(v).lower() not in ("green", "ok", "pass")]
                    detail = f"{len(sigs) - len(bad)}/{len(sigs)} green" + (f" · {bad[0]}" if bad else "")
                elif blob.get("kpis_head"):
                    kh = blob["kpis_head"]
                    detail = f"avg={kh.get('avg_knowledge_worth')} n={kh.get('knowledge_nodes')}"
            if name == "rate":
                detail = f"{blob.get('band')} {blob.get('concert_score')}/{blob.get('max')}"
            if name == "critic":
                detail = f"{blob.get('verdict')} {blob.get('score')}/{blob.get('max')}"
            if name == "optimize":
                if blob.get("skipped"):
                    detail = "skip"
                elif blob.get("ok") is True:
                    detail = "ok"
                else:
                    detail = str(blob.get("detail") or blob.get("reason") or "")[:28]
            if name == "swarm":
                n = blob.get("n_agents") or blob.get("agents") or ""
                w = blob.get("writes") or blob.get("write_count") or ""
                if n or w:
                    detail = f"×{n}" + (f" writes={w}" if w != "" else "")
                else:
                    detail = "skip" if blob.get("skipped") else "ok"
            if name == "crawl_gap" and blob.get("reason"):
                detail = str(blob.get("reason"))[:28]
            if name == "boot":
                rec = blob.get("recovery") or {}
                ms = rec.get("elapsed_ms")
                sc = blob.get("session_crawl") or {}
                if ms is not None:
                    detail = f"{ms}ms" + (f" +{sc.get('ingested', 0)} sess" if sc else "")
                elif sc:
                    detail = f"sess +{sc.get('ingested', 0)}"
            # hard cap — panel ellipsizes further by pixel width
            self.stage_detail[name] = str(detail).replace("\n", " ")[:40]

        for k, key in [
            ("boot", "boot"), ("swarm", "swarm"), ("cost", "cost"), ("security", "security"),
            ("retrieve", "retrieve"), ("crawl_gap", "crawl"), ("validate", "validate"),
            ("metrics", "metrics"), ("synthesize", "synthesize"), ("critic", "critic"),
            ("rate", "rate"), ("optimize", "optimize"),
        ]:
            mark(k, data.get(key))
        if data.get("context") or data.get("final_ok") is not None:
            self.stage_status["emit"] = "ok" if data.get("final_ok") is not False else "fail"
            self.stage_detail["emit"] = "context packed"
        # Optional stages: null in last_dag means intentionally not run — show skip, not offline
        if data.get("final_ok") is not None:
            if data.get("swarm") is None and self.stage_status.get("swarm") in ("pending", "running", None):
                self.stage_status["swarm"] = "skip"
                if not self.stage_detail.get("swarm"):
                    self.stage_detail["swarm"] = "off (PB_SWARM_AGENTS=0)"
            if data.get("optimize") is None and self.stage_status.get("optimize") in ("pending", "running", None):
                self.stage_status["optimize"] = "skip"
                if not self.stage_detail.get("optimize"):
                    self.stage_detail["optimize"] = "skip (pass band; set PB_ALWAYS_OPTIMIZE=1)"
            for s in STAGE_ORDER:
                if self.stage_status.get(s) == "running":
                    self.stage_status[s] = "ok"

    def fire_pathway(self, ids: list[str], edges: list[dict] | None = None, prompt: str = "") -> None:
        """Light nodes/edges for a retrieve hit set (neuron activation)."""
        now = time.time()
        for nid in ids:
            if nid:
                self.lit_nodes[str(nid)] = 1.0
        for e in edges or []:
            s, d = e.get("src"), e.get("dst")
            if s and d:
                a, b = (s, d) if s <= d else (d, s)
                self.lit_edges.add((a, b))
                # also light endpoints
                self.lit_nodes[str(s)] = max(self.lit_nodes.get(str(s), 0), 0.85)
                self.lit_nodes[str(d)] = max(self.lit_nodes.get(str(d), 0), 0.85)
        if prompt:
            self.pathway_prompt = prompt[:80]
        self.event_log.appendleft(f"pathway fire  nodes={len(ids)} edges={len(self.lit_edges)}")
        # keep decay clock
        self._pathway_t0 = now  # type: ignore[attr-defined]

    def decay_pathway(self, dt: float = 0.016) -> None:
        if not self.lit_nodes:
            return
        dead = []
        for nid, inten in self.lit_nodes.items():
            n = inten - dt * 0.12  # ~8s fade
            if n <= 0.05:
                dead.append(nid)
            else:
                self.lit_nodes[nid] = n
        for nid in dead:
            del self.lit_nodes[nid]
        if not self.lit_nodes:
            self.lit_edges.clear()

    def poll_events(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return
        lines = raw.splitlines()
        if len(lines) < self.events_offset:
            self.events_offset = 0
        if len(lines) <= self.events_offset:
            # still re-assert finished concert so sticky running dies
            if self._last_dag_data and self._last_dag_data.get("final_ok") is not None:
                self._apply_dag_stages(self._last_dag_data)
            return
        for line in lines[self.events_offset :]:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = ev.get("run_id") or ""
            if rid and rid != self.event_run_id:
                self.event_run_id = str(rid)
                # new concert stream — reset lights until events/dag fill in
                self.stage_status = {s: "pending" for s in STAGE_ORDER}
            stage = ev.get("stage") or ev.get("action") or "event"
            status = ev.get("status") or ev.get("result") or "running"
            props = ev.get("props") if isinstance(ev.get("props"), dict) else {}
            # Neuron pathway payload (retrieve ok)
            ids = ev.get("ids") or props.get("ids") or []
            edges = ev.get("edges") or props.get("edges") or []
            if (ev.get("pathway") or props.get("pathway") or stage == "retrieve") and status in (
                "ok",
                "success",
            ) and ids:
                self.fire_pathway(
                    [str(i) for i in ids if i],
                    edges if isinstance(edges, list) else [],
                    prompt=str(ev.get("detail") or ""),
                )
            if stage in self.stage_status:
                if status in ("start", "running"):
                    # do not downgrade ok/fail → running (sticky bug)
                    if self.stage_status.get(stage) not in ("ok", "fail", "skip"):
                        self.stage_status[stage] = "running"
                elif status in ("ok", "success"):
                    self.stage_status[stage] = "ok"
                elif status in ("fail", "error"):
                    self.stage_status[stage] = "fail"
                elif status in ("skip", "skipped"):
                    self.stage_status[stage] = "skip"
            det = str(ev.get("detail") or "")
            if det:
                self.stage_detail[stage] = det[:36]
            self.event_log.appendleft(f"{stage}:{status}  {det[:50]}")
        self.events_offset = len(lines)
        # Authoritative finish state from last_dag wins after live ticks
        if self._last_dag_data and self._last_dag_data.get("final_ok") is not None:
            if self._last_dag_data.get("run_id") == self.event_run_id or not self.event_run_id:
                self._apply_dag_stages(self._last_dag_data)

    def reload_metrics(self, metrics_dir: Path) -> None:
        p = metrics_dir / "current.json"
        if not p.exists():
            p = metrics_dir / "full.json"
        if not p.exists():
            return
        try:
            self.metrics = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    def reload_vectors(self, emb_dir: Path) -> None:
        if not emb_dir.is_dir():
            self.vector_stats = {"vectors": 0}
            return
        n = len([p for p in emb_dir.glob("*.json") if not p.name.startswith("_")])
        terms = 0
        vocab = emb_dir / "_vocab.json"
        if vocab.exists():
            try:
                v = json.loads(vocab.read_text(encoding="utf-8"))
                terms = len(v.get("df") or {})
            except json.JSONDecodeError:
                pass
        self.vector_stats = {"vectors": n, "vocab_terms": terms, "algo": "tfidf-l2-v1"}

    def request_relayout(self) -> None:
        """User pressed R — rebuild constellation islands; stay LIVE."""
        self.pos.clear()
        self.vel.clear()
        self.layout_energy = 0.0
        self.snap_mtime = 0  # force reload + reseed
        self.layout_frozen = False
        self.layout_ticks = 0
        self._settle_then_freeze = False
        self.event_log.appendleft("layout  live reshuffle")

    def begin_settle(self) -> None:
        """Resume continuous live layout (used after pause / reshuffle)."""
        self.layout_frozen = False
        self.layout_ticks = 0
        self._settle_then_freeze = False
        self.event_log.appendleft("layout  live")

    def toggle_layout_pause(self) -> None:
        """Space: pause ↔ resume continuous motion."""
        if self.layout_frozen:
            self.layout_frozen = False
            self.layout_ticks = 0
            self._settle_then_freeze = False
            self.event_log.appendleft("layout  live")
        else:
            self.layout_frozen = True
            for v in self.vel.values():
                v[0] = 0.0
                v[1] = 0.0
            self.event_log.appendleft("layout  paused")

    def step_layout(self) -> None:
        # Continuous live layout unless user paused (Space).
        if self.layout_frozen:
            return
        try:
            self._step_layout_inner()
        except Exception:
            for nid, p in list(self.pos.items())[:50]:
                if not (isinstance(p, (list, tuple)) and len(p) >= 2 and math.isfinite(p[0]) and math.isfinite(p[1])):
                    self.pos[nid] = [400.0 + random.random() * 40, 300.0 + random.random() * 40]
                self.vel[nid] = [(random.random() - 0.5) * 0.2, (random.random() - 0.5) * 0.2]
            # Stay live after recovery — never lock frozen on error
            self.layout_frozen = False
            self._settle_then_freeze = False
            return
        self.layout_ticks += 1
        # Never auto-freeze — continuous live is the product law

    def _step_layout_inner(self) -> None:
        """Very light local polish only — never expand-to-fill or wall-pack a square."""
        ids = [i for i in self.nodes.keys() if i in self.pos]
        if not ids:
            return
        for nid in ids:
            p = self.pos.get(nid)
            if not p or not (math.isfinite(p[0]) and math.isfinite(p[1])):
                self.pos[nid] = [self.layout_w * 0.5, self.layout_h * 0.5]
                self.vel[nid] = [0.0, 0.0]
            elif nid not in self.vel:
                self.vel[nid] = [0.0, 0.0]
        if len(ids) > LAYOUT_MAX:
            ids = random.sample(ids, LAYOUT_MAX)

        # Short-range repulsion only (de-overlap inside islands)
        for i, a in enumerate(ids):
            for b in ids[i + 1 : i + 1 + LAYOUT_PAIR_K]:
                if a not in self.pos or b not in self.pos:
                    continue
                if b not in self.vel:
                    self.vel[b] = [0.0, 0.0]
                ax, ay = self.pos[a]
                bx, by = self.pos[b]
                dx, dy = ax - bx, ay - by
                dist2 = dx * dx + dy * dy + 0.01
                dist = math.sqrt(dist2)
                if dist > 48:  # only separate near-overlaps
                    continue
                force = min(12.0, 800.0 / dist2)
                ux, uy = dx / dist, dy / dist
                self.vel[a][0] += force * ux
                self.vel[a][1] += force * uy
                self.vel[b][0] -= force * ux
                self.vel[b][1] -= force * uy

        energy = 0.0
        for nid in ids:
            if nid not in self.vel or nid not in self.pos:
                continue
            vx = self.vel[nid][0] * 0.7
            vy = self.vel[nid][1] * 0.7
            self.vel[nid][0] = max(-8.0, min(8.0, vx))
            self.vel[nid][1] = max(-8.0, min(8.0, vy))
            self.pos[nid][0] += self.vel[nid][0]
            self.pos[nid][1] += self.vel[nid][1]
            energy += abs(self.vel[nid][0]) + abs(self.vel[nid][1])
        self.layout_energy = energy


def font_try(names: list[str], size: int, bold: bool = False):
    for n in names:
        try:
            f = pygame.font.SysFont(n, size, bold=bold)
            if f:
                return f
        except Exception:
            continue
    return pygame.font.SysFont(None, size, bold=bold)


def draw_text(screen, font, text, x, y, color=TEXT):
    screen.blit(font.render(str(text), True, color), (x, y))


def ellipsize(font, text: str, max_w: int) -> str:
    """Truncate with … so rendered text fits max_w pixels."""
    t = str(text or "")
    if max_w <= 8:
        return ""
    if font.size(t)[0] <= max_w:
        return t
    while t and font.size(t + "…")[0] > max_w:
        t = t[:-1]
    return (t + "…") if t else "…"


def wrap_text(font, text: str, max_w: int, max_lines: int = 4) -> list[str]:
    """Word-wrap text to max_w; hard-ellipsize last line if needed."""
    t = str(text or "").strip()
    if not t or max_w < 20:
        return []
    words = t.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w if font.size(w)[0] <= max_w else ellipsize(font, w, max_w)
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines:
        lines[-1] = ellipsize(font, lines[-1], max_w)
    return lines


def rounded_panel(screen, rect: pygame.Rect, fill=PANEL, border=BORDER, radius=10):
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect, 1, border_radius=radius)


def flyout(
    screen,
    font,
    font_xs,
    lines: list[str],
    mx: int,
    my: int,
    W: int,
    H: int,
    title: str = "",
    *,
    max_line: int = 96,
    max_width: int = 420,
) -> None:
    """Draw a floating info card near the cursor (clamped to screen)."""
    pad = 10
    rows = ([title] if title else []) + lines
    if not rows:
        return
    # Soft wrap long lines for stage encyclopedia
    wrapped: list[tuple[str, bool]] = []  # (text, is_title)
    for i, row in enumerate(rows):
        is_title = i == 0 and bool(title)
        f = font if is_title else font_xs
        text = (row or "").replace("\n", " ").strip()
        if not text:
            continue
        # greedy wrap by character budget
        while text:
            chunk = text[:max_line]
            if len(text) > max_line:
                # break on space if possible
                sp = chunk.rfind(" ")
                if sp > 40:
                    chunk = chunk[:sp]
            wrapped.append((chunk, is_title))
            text = text[len(chunk) :].lstrip()
            is_title = False
    if not wrapped:
        return
    widths = [
        (font if is_t else font_xs).size(r)[0] for r, is_t in wrapped
    ]
    tw = min(max_width, max(widths) + pad * 2)
    th = pad * 2 + sum(
        (font.get_height() + 4) if is_t else (font_xs.get_height() + 3) for _, is_t in wrapped
    )
    x = mx + 16
    y = my + 16
    if x + tw > W - 8:
        x = mx - tw - 12
    if y + th > H - 8:
        y = H - th - 8
    x = max(x, 8)
    y = max(y, 8)
    rect = pygame.Rect(x, y, tw, th)
    # shadow
    sh = rect.move(3, 3)
    pygame.draw.rect(screen, (0, 0, 0), sh, border_radius=8)
    rounded_panel(screen, rect, PANEL_2, ACCENT, 8)
    cy = y + pad
    for row, is_t in wrapped:
        if is_t:
            draw_text(screen, font, row[: max_line + 10], x + pad, cy, TEXT)
            cy += font.get_height() + 4
        else:
            draw_text(screen, font_xs, row[: max_line + 10], x + pad, cy, TEXT_DIM)
            cy += font_xs.get_height() + 3


def _stage_config_lines(state: "AppState", stg: str) -> list[str]:
    """Live configuration + last_dag facts for a stage hover."""
    env = os.environ
    dag = state._last_dag_data if isinstance(getattr(state, "_last_dag_data", None), dict) else {}
    blob = dag.get(stg) if isinstance(dag.get(stg), dict) else None
    # crawl stored as "crawl" in last_dag sometimes
    if stg == "crawl_gap" and blob is None and isinstance(dag.get("crawl"), dict):
        blob = dag.get("crawl")
    lines: list[str] = []
    if stg == "swarm":
        raw = (env.get("PB_SWARM_AGENTS") or "16").strip()
        lines.append(f"config: PB_SWARM_AGENTS={raw} (default 16, max 64, 0=off)")
        if blob:
            lines.append(
                f"last run: n={blob.get('n_agents') or blob.get('expected') or '—'} "
                f"ok={blob.get('ok_count') or blob.get('ok')} skipped={blob.get('skipped')} "
                f"reason={blob.get('reason') or '—'}"
            )
        else:
            lines.append("last run: (no swarm blob in last_dag yet)")
    elif stg == "crawl_gap":
        lines.append("config: allow_crawl on full concert; UPS hooks often allow_crawl=False")
        lines.append("config: min_crawl_interval_sec≈300 (cooldown); cost budget can block")
        lines.append(f"config: PB_GITLAB_PRESET={env.get('PB_GITLAB_PRESET') or '—'} GITLAB_URL set={bool(env.get('GITLAB_URL'))}")
        if blob:
            lines.append(
                f"last run: skipped={blob.get('skipped')} reason={blob.get('reason') or blob.get('error') or '—'}"
            )
    elif stg == "optimize":
        lines.append("config: runs if band=FAIL or score<6 or critic=FAIL")
        lines.append(f"config: PB_ALWAYS_OPTIMIZE={env.get('PB_ALWAYS_OPTIMIZE') or '0'}")
        rate = dag.get("rate") if isinstance(dag.get("rate"), dict) else {}
        lines.append(
            f"last rate: band={rate.get('band') or '—'} score={rate.get('concert_score') or '—'}"
        )
        if blob:
            lines.append(
                f"last run: skipped={blob.get('skipped')} reason={blob.get('reason') or '—'} ok={blob.get('ok')}"
            )
    elif stg == "retrieve":
        lines.append("config: hybrid lexical+vector; enterprise demotes public/swarm noise")
        if blob:
            lines.append(f"last run: hits={blob.get('hit_count')} gap={blob.get('gap')} ok={blob.get('ok')}")
    elif stg == "security":
        lines.append("config: audit_verify chain; seal-on-break recovery policy")
        if blob:
            lines.append(
                f"last run: chain_ok={blob.get('chain_ok')} events={blob.get('events_checked')} ok={blob.get('ok')}"
            )
    elif stg == "cost":
        lines.append("config: cost state under .brain/state; min crawl interval + budget_ok")
        if blob:
            lines.append(f"last run: budget_ok={blob.get('budget_ok')} ok={blob.get('ok')}")
    elif stg == "boot":
        lines.append(f"config: PRIVATE_BRAIN_HOME={env.get('PRIVATE_BRAIN_HOME') or 'default ~/.codex/private-brain'}")
        if blob:
            lines.append(f"last run: nodes={blob.get('nodes') or (blob.get('boot') or {}).get('nodes')} ok={blob.get('ok')}")
    elif stg == "rate":
        if blob:
            lines.append(f"last run: band={blob.get('band')} score={blob.get('concert_score')} ok={blob.get('ok')}")
        lines.append("config: folds critic verdict into notes / score demotion")
    elif stg == "emit":
        lines.append(f"config: final_ok={dag.get('final_ok')} run_id={dag.get('run_id') or '—'}")
    elif stg == "validate":
        if blob:
            lines.append(f"last run: ok={blob.get('ok')} detail={str(blob.get('reason') or blob.get('error') or '—')[:60]}")
    elif stg == "critic":
        if blob:
            lines.append(f"last run: verdict={blob.get('verdict')} ok={blob.get('ok')}")
    elif stg == "synthesize":
        if blob:
            lines.append(f"last run: ok={blob.get('ok')} bullets/context present={bool(blob)}")
    elif stg == "metrics":
        if blob:
            lines.append(f"last run: ok={blob.get('ok')}")
    # Always surface last_dag detail string if present
    det = (state.stage_detail.get(stg) or "").strip()
    if det:
        lines.append(f"detail: {det}")
    return lines


def stage_hover_lines(state: "AppState", stg: str) -> list[str]:
    """Full stage encyclopedia for hover/pin flyout."""
    exp = STAGE_EXPLAIN.get(stg) or {}
    st = state.stage_status.get(stg, "pending")
    col_name = {
        "ok": "GREEN / GO",
        "running": "YELLOW / RUNNING",
        "fail": "RED / STOP",
        "pending": "GRAY / IDLE",
        "skip": "GRAY / SKIP (intentional)",
    }.get(st, st)
    lines = [
        f"What: {exp.get('what') or STAGE_LABEL.get(stg, stg)}",
        f"Why:  {exp.get('why') or '—'}",
        f"When: {exp.get('when') or '—'}",
        f"Status now: {col_name}",
    ]
    lines.extend(_stage_config_lines(state, stg))
    lines.append("Click stage to pin this card")
    return lines


def help_overlay(screen, font, font_sm, font_xs, W: int, H: int) -> None:
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    box = pygame.Rect(W // 2 - 340, 40, 680, min(H - 80, 560))
    rounded_panel(screen, box, PANEL, GREEN, 12)
    draw_text(screen, font, "HELP · what the colors mean", box.x + 20, box.y + 16, TEXT)
    # mini traffic lights
    lx = box.x + 20
    ly = box.y + 48
    for lab, col, meaning in [
        ("GREEN", GREEN, "GO — ok / healthy / done"),
        ("YELLOW", YELLOW, "CAUTION — running / soft warn"),
        ("RED", RED, "STOP — failed / critical"),
        ("GRAY", GRAY, "IDLE — pending or skipped"),
    ]:
        pygame.draw.circle(screen, col, (lx + 8, ly + 7), 7)
        draw_text(screen, font_sm, f"{lab}: {meaning}", lx + 24, ly, TEXT)
        ly += 22
    ly += 8
    for line in HELP_LINES[6:]:
        draw_text(screen, font_xs, line, box.x + 20, ly, TEXT_DIM if line else TEXT_MUTED)
        ly += 16
        if ly > box.bottom - 30:
            break
    draw_text(screen, font_xs, "Press H again to close", box.x + 20, box.bottom - 28, TEXT_MUTED)


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain live ops dashboard (GodsEye)")
    ap.add_argument("--width", type=int, default=0, help="0 = fit display")
    ap.add_argument("--height", type=int, default=0)
    args = ap.parse_args()

    root = brain_dir()
    snap_path = root / "graph" / "snapshot.json"
    dag_path = root / "state" / "last_dag.json"
    events_path = root / "state" / "gui_events.jsonl"
    metrics_dir = root / "state" / "metrics"
    emb_dir = root / "index" / "embeddings"

    pygame.init()
    pygame.display.set_caption("Private Brain · Live Ops (GodsEye)")
    info = pygame.display.Info()
    W = args.width or max(1100, min(info.current_w - 40, 1600))
    H = args.height or max(700, min(info.current_h - 80, 1000))
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    mono = ["menlo", "sf mono", "consolas", "dejavu sans mono", "courier new", "monospace"]
    sans = ["sf pro text", "helvetica neue", "segoe ui", "arial", "sans-serif"]
    font_sm = font_try(mono, 12)
    font_xs = font_try(mono, 11)
    font_title = font_try(sans, 18, bold=True)
    font_kpi = font_try(sans, 20, bold=True)

    state = LiveState()
    dragging = False
    drag_last = (0, 0)
    last_poll = 0.0
    stage_hitboxes: list[tuple[pygame.Rect, str]] = []

    def layout_rects():
        # Single clean top band: brand | KPIs | status | close — no stacked collisions
        TOP, BOT, RIGHT = 64, 36, min(380, max(300, W // 3))
        graph = pygame.Rect(12, TOP + 8, max(200, W - RIGHT - 28), max(120, H - TOP - BOT - 20))
        right_x = W - RIGHT - 8
        return TOP, BOT, RIGHT, graph, right_x

    close_btn = pygame.Rect(0, 0, 72, 28)  # updated each frame
    running = True
    while running:
        TOP, BOT, RIGHT, graph_rect, right_x = layout_rects()
        # Close button — top-right, always visible, always clickable
        close_btn = pygame.Rect(W - 84, 10, 72, 28)
        now = time.time()
        if now - last_poll > 0.4:
            try:
                state.reload_snapshot(snap_path, graph_rect.w, graph_rect.h)
                state.reload_dag(dag_path)
                state.poll_events(events_path)
                state.reload_metrics(metrics_dir)
                state.reload_vectors(emb_dir)
            except Exception:
                pass
            last_poll = now

        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            # Mac red traffic-light close + generic quit
            if event.type == pygame.QUIT or hasattr(pygame, "WINDOWCLOSE") and event.type == pygame.WINDOWCLOSE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                W, H = max(900, event.w), max(600, event.h)
                screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                # Cmd/Ctrl+W or Q or Esc always closes (Esc first closes help)
                mods = pygame.key.get_mods()
                if event.key == pygame.K_w and (mods & (pygame.KMOD_META | pygame.KMOD_CTRL)) or event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    if state.show_help:
                        state.show_help = False
                    else:
                        running = False
                elif event.key == pygame.K_h:
                    state.show_help = not state.show_help
                elif event.key == pygame.K_r:
                    state.request_relayout()
                elif event.key == pygame.K_SPACE:
                    # Space = pause ↔ resume continuous live layout
                    state.toggle_layout_pause()
                elif event.key == pygame.K_s:
                    state.snap_mtime = state.dag_mtime = 0
                    state.events_offset = 0
                    state.pos.clear()
                    state.vel.clear()
                    state.layout_frozen = False
                    state._settle_then_freeze = False
                elif event.key == pygame.K_1:
                    state.focus = 0
                elif event.key == pygame.K_2:
                    state.focus = 1
                elif event.key == pygame.K_3:
                    state.focus = 2
                # Origin trail: [ toward root · ] toward leaf · Enter refresh snippet · Esc clears help first
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_LEFT):
                    state.walk_trail(+1)  # toward root (trail grows leaf→root)
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_RIGHT):
                    state.walk_trail(-1)  # back toward clicked leaf
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if state.selected:
                        state.trail_snippet = state._load_snippet(state.selected)
                        state.event_log.appendleft(f"snippet  {state.selected[:40]}")
                elif event.key == pygame.K_BACKSPACE:
                    state.clear_selection()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # × Close button (always works)
                    if close_btn.collidepoint(event.pos):
                        running = False
                        break
                    # stage pin
                    pinned = None
                    for rect, stg in stage_hitboxes:
                        if rect.collidepoint(event.pos):
                            pinned = stg
                            break
                    if pinned:
                        state.pinned_stage = None if state.pinned_stage == pinned else pinned
                    elif graph_rect.collidepoint(event.pos):
                        hit = None
                        best = 14
                        for nid in list(state.nodes.keys())[:DRAW_NODES]:
                            if nid not in state.pos:
                                continue
                            pt = _w2s(state, graph_rect, *state.pos[nid])
                            if not pt:
                                continue
                            d = math.hypot(event.pos[0] - pt[0], event.pos[1] - pt[1])
                            if d < best:
                                best = d
                                hit = nid
                        # Origin crawl: click builds leaf→root trail + neighbors
                        if hit:
                            state.select_node(hit)
                        else:
                            state.clear_selection()
                    dragging = True
                    drag_last = event.pos
                elif event.button == 4:
                    if right_x < event.pos[0]:
                        state.activity_scroll = max(0, state.activity_scroll - 1)
                    else:
                        state.zoom = min(3.0, state.zoom * 1.1)
                elif event.button == 5:
                    if right_x < event.pos[0]:
                        state.activity_scroll = min(40, state.activity_scroll + 1)
                    else:
                        state.zoom = max(0.25, state.zoom / 1.1)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                if graph_rect.collidepoint(drag_last):
                    dx = event.pos[0] - drag_last[0]
                    dy = event.pos[1] - drag_last[1]
                    state.pan[0] += dx / state.zoom
                    state.pan[1] += dy / state.zoom
                drag_last = event.pos
            elif event.type == pygame.MOUSEWHEEL:
                if mx >= right_x:
                    state.activity_scroll = max(0, min(40, state.activity_scroll - event.y))
                else:
                    state.zoom = min(3.0, state.zoom * 1.1) if event.y > 0 else max(0.25, state.zoom / 1.1)

        # hover detection
        state.hover_node = None
        state.hover_stage = None
        for rect, stg in stage_hitboxes:
            if rect.collidepoint(mx, my):
                state.hover_stage = stg
                break
        if graph_rect.collidepoint(mx, my) and not state.hover_stage:
            best = 12
            for nid in list(state.nodes.keys())[:DRAW_NODES]:
                if nid not in state.pos:
                    continue
                pt = _w2s(state, graph_rect, *state.pos[nid])
                if not pt:
                    continue
                d = math.hypot(mx - pt[0], my - pt[1])
                if d < best:
                    best = d
                    state.hover_node = nid

        state.step_layout()
        state.tick += 1
        screen.fill(BG)
        stage_hitboxes = []

        counts = state.stage_counts()
        health_lab, health_col, health_why = state.health()
        stats = state.brain_stats
        nodes_n = stats.get("viz_nodes", len(state.nodes))
        edges_n = stats.get("viz_edges", len(state.edges))
        vec_n = state.vector_stats.get("vectors", 0)

        # ── TOP BAR (fixed columns — never stack text over KPIs) ──
        # | brand (200) | KPIs | legend | status strip | × Close |
        pygame.draw.rect(screen, PANEL, (0, 0, W, TOP))
        pygame.draw.line(screen, BORDER, (0, TOP - 1), (W, TOP - 1), 1)

        close_btn = pygame.Rect(W - 84, 10, 72, 28)
        status_strip_w = min(300, max(200, W // 5))
        status_strip = pygame.Rect(close_btn.x - status_strip_w - 10, 8, status_strip_w, TOP - 16)

        BRAND_W = 188
        # Brand column (clipped)
        brand_rect = pygame.Rect(8, 4, BRAND_W, TOP - 8)
        prev = screen.get_clip()
        screen.set_clip(brand_rect)
        draw_text(screen, font_title, "Private Brain", 12, 8, TEXT)
        draw_text(screen, font_xs, "Live Ops · CPU view", 12, 32, TEXT_MUTED)
        motion = "layout: paused" if state.layout_frozen else "layout: LIVE"
        draw_text(screen, font_xs, motion, 12, 46, TEXT_MUTED if state.layout_frozen else YELLOW)
        screen.set_clip(prev)

        # KPIs — start after brand, stop before status strip
        kx = BRAND_W + 16
        kpi_max_x = status_strip.x - 8
        for label, val, col in [
            ("Graph nodes", nodes_n, ACCENT),
            ("Edges", edges_n, CYAN),
            ("Vectors", vec_n, GREEN),
        ]:
            if kx + 96 > kpi_max_x:
                break
            draw_text(screen, font_xs, label, kx, 10, TEXT_MUTED)
            draw_text(screen, font_kpi, str(val), kx, 28, col)
            kx += 108

        # Traffic legend if room
        if kx + 150 < status_strip.x:
            lx = kx + 4
            for col, lab in [(GREEN, "ok"), (YELLOW, "run"), (RED, "fail")]:
                pygame.draw.circle(screen, col, (lx + 5, 24), 5)
                draw_text(screen, font_xs, lab, lx + 14, 17, TEXT_MUTED)
                lx += 48
            draw_text(screen, font_xs, "H help · R re-layout · Space pause/live", lx + 4, 40, TEXT_MUTED)

        # Status strip (right, clipped)
        running_stages = state.running_stages()
        failed = state.failed_stages()
        ok_n = counts["ok"]
        total = len(STAGE_ORDER)
        rounded_panel(screen, status_strip, PANEL_2, health_col, 8)
        prev = screen.get_clip()
        screen.set_clip(status_strip.inflate(-4, -4))
        htxt = ellipsize(font_sm, f"● {health_lab}", status_strip.w - 16)
        draw_text(screen, font_sm, htxt, status_strip.x + 10, status_strip.y + 6, health_col)
        if running_stages:
            pipe_txt = f"Running: {', '.join(running_stages[:3])}"
            pcol = YELLOW
        elif failed:
            pipe_txt = f"Failed: {', '.join(failed[:3])}"
            pcol = RED
        else:
            pipe_txt = f"Ready · {ok_n}/{total} green"
            pcol = GREEN if ok_n else TEXT_MUTED
        draw_text(
            screen,
            font_xs,
            ellipsize(font_xs, pipe_txt, status_strip.w - 16),
            status_strip.x + 10,
            status_strip.y + 28,
            pcol,
        )
        screen.set_clip(prev)

        # × Close
        close_fill = RED if close_btn.collidepoint(mx, my) else PANEL_2
        pygame.draw.rect(screen, close_fill, close_btn, border_radius=6)
        pygame.draw.rect(screen, RED, close_btn, 1, border_radius=6)
        cx = close_btn.centerx - font_sm.size("× Close")[0] // 2
        draw_text(screen, font_sm, "× Close", cx, close_btn.y + 6, TEXT)

        # ── GRAPH ────────────────────────────────────────────────
        rounded_panel(screen, graph_rect, PANEL, BORDER if state.focus != 0 else ACCENT, 12)
        draw_text(screen, font_sm, "KNOWLEDGE GRAPH", graph_rect.x + 14, graph_rect.y + 10, TEXT_DIM)
        # Capacity subtitle: how many we hold / draw vs full snapshot
        shown_n = min(len(state.nodes), DRAW_NODES)
        total_n = state.snapshot_node_total or len(state.nodes)
        held_n = len(state.nodes)
        if state.viz_capped or held_n > DRAW_NODES or (total_n and held_n < total_n):
            cap_txt = f"showing {shown_n}/{total_n} (cap hold {SNAPSHOT_VIZ_MAX} draw {DRAW_NODES})"
            cap_col = YELLOW
        else:
            motion = "paused" if state.layout_frozen else "LIVE"
            cap_txt = f"{held_n} nodes · layout {motion} · R re-layout · Space pause · hover for detail"
            cap_col = TEXT_MUTED
        draw_text(
            screen,
            font_xs,
            ellipsize(font_xs, cap_txt, graph_rect.w - 28),
            graph_rect.x + 14,
            graph_rect.y + 28,
            cap_col,
        )

        clip = pygame.Rect(graph_rect.x + 4, graph_rect.y + 46, graph_rect.w - 8, graph_rect.h - 54)
        prev = screen.get_clip()
        screen.set_clip(clip)

        trail_set = set(state.trail)
        trail_pairs: set[tuple[str, str]] = set()
        for i in range(1, len(state.trail)):
            a, b = state.trail[i - 1], state.trail[i]
            trail_pairs.add((a, b) if a < b else (b, a))
        neigh_ids = {nid for nid, _rel, _d in state.trail_neighbors}

        # Edges: soft mesh only when no focus; trail + neuron pathways always bold
        for e in state.edges[:DRAW_EDGES]:
            s, d = e.get("src"), e.get("dst")
            if s not in state.pos or d not in state.pos:
                continue
            p1 = _w2s(state, graph_rect, *state.pos[s])
            p2 = _w2s(state, graph_rect, *state.pos[d])
            if not (p1 and p2):
                continue
            pair = (s, d) if s < d else (d, s)
            if pair in trail_pairs:
                pygame.draw.line(screen, GREEN, p1, p2, 2)
            elif pair in state.lit_edges:
                inten = max(
                    state.lit_nodes.get(s, 0.4),
                    state.lit_nodes.get(d, 0.4),
                )
                glow = tuple(min(255, int(c * (0.4 + 0.6 * inten))) for c in ACCENT)
                pygame.draw.line(screen, glow, p1, p2, 2)
            elif state.trail or state.lit_nodes:
                # When focused, mute background edges so lineage reads
                if s in trail_set or d in trail_set or s in neigh_ids or d in neigh_ids:
                    pygame.draw.aaline(screen, BORDER, p1, p2)
            else:
                pygame.draw.aaline(screen, BORDER_SOFT, p1, p2)

        # decay pathway glow each frame
        if state.lit_nodes and state.tick % 3 == 0:
            state.decay_pathway(0.04)

        for nid, n in list(state.nodes.items())[:DRAW_NODES]:
            if nid not in state.pos:
                continue
            pt = _w2s(state, graph_rect, *state.pos[nid])
            if not pt or not clip.collidepoint(pt):
                continue
            # Fill: prefer source color so islands aren't mono-yellow discs
            if state.color_mode == "source":
                col = SOURCE_COLOR.get(n.get("source") or "", TIER_COLOR.get(n.get("tier") or "T3", GRAY))
                ring = TIER_COLOR.get(n.get("tier") or "T3", BORDER)
            else:
                col = TIER_COLOR.get(n.get("tier") or "T3", GRAY)
                ring = SOURCE_COLOR.get(n.get("source") or "", BORDER)
            dense = len(state.nodes) > 2500
            chunky = n.get("type") in (
                "Comment", "MRComment", "SessionTurn", "BrainChunk", "Pipeline", "SwarmCrumb",
            )
            r = 3 if dense and chunky else (4 if dense else (4 if chunky else 6))
            on_trail = nid in trail_set
            is_focus = nid == state.selected or (
                state.trail and 0 <= state.trail_focus < len(state.trail) and nid == state.trail[state.trail_focus]
            )
            lit = state.lit_nodes.get(nid, 0.0)
            if is_focus:
                pygame.draw.circle(screen, GREEN, pt, r + 8, 2)
                r = max(r, 7)
            elif on_trail:
                pygame.draw.circle(screen, GREEN, pt, r + 5, 1)
                r = max(r, 6)
            elif lit > 0.05:
                glow = tuple(min(255, int(c * lit + 40)) for c in ACCENT)
                pygame.draw.circle(screen, glow, pt, r + 4 + int(3 * lit), 1)
                r = max(r, 5)
            elif nid in neigh_ids:
                pygame.draw.circle(screen, YELLOW, pt, r + 4, 1)
            if nid == state.hover_node or nid == state.selected:
                pygame.draw.circle(screen, TEXT, pt, r + 5, 1)
            pygame.draw.circle(screen, ring, pt, r + 2)
            pygame.draw.circle(screen, col, pt, r)

        screen.set_clip(prev)

        # Origin trail card — crawl lineage + content snippet
        if state.selected and state.selected in state.nodes:
            n = state.nodes[state.selected]
            has_trail = len(state.trail) > 1
            card_h = 118 if has_trail or state.trail_snippet else 64
            card = pygame.Rect(graph_rect.x + 10, graph_rect.bottom - card_h - 8, graph_rect.w - 20, card_h)
            rounded_panel(screen, card, PANEL_2, GREEN, 8)
            title = (n.get("title") or n.get("id") or "")[:68]
            draw_text(screen, font_sm, title, card.x + 12, card.y + 6, TEXT)
            meta = f"id={n.get('id')}  type={n.get('type')}  source={n.get('source')}  tier={n.get('tier')}"
            draw_text(screen, font_xs, ellipsize(font_xs, meta, card.w - 24), card.x + 12, card.y + 26, TEXT_DIM)
            # trail breadcrumb leaf → … → root
            if state.trail:
                parts = []
                for i, tid in enumerate(state.trail[:8]):
                    tn = state.nodes.get(tid) or {}
                    lab = (tn.get("type") or tid.split(":")[0] if ":" in tid else tid)[:18]
                    if i == state.trail_focus:
                        parts.append(f"[{lab}]")
                    else:
                        parts.append(lab)
                crumb = " ← ".join(parts)
                if len(state.trail) > 8:
                    crumb += " ← …"
                draw_text(
                    screen,
                    font_xs,
                    ellipsize(font_xs, f"origin {len(state.trail)}: {crumb}", card.w - 24),
                    card.x + 12,
                    card.y + 42,
                    GREEN,
                )
                draw_text(
                    screen,
                    font_xs,
                    "[ / ← root · ] / → leaf · Enter snippet · Backspace clear",
                    card.x + 12,
                    card.y + 56,
                    TEXT_MUTED,
                )
            if state.trail_snippet and card_h > 80:
                snip = state.trail_snippet.replace("\n", " ")[:140]
                draw_text(
                    screen,
                    font_xs,
                    ellipsize(font_xs, snip, card.w - 24),
                    card.x + 12,
                    card.y + 74,
                    TEXT_DIM,
                )
                if len(state.trail_snippet) > 140:
                    draw_text(
                        screen,
                        font_xs,
                        ellipsize(font_xs, state.trail_snippet.replace("\n", " ")[140:280], card.w - 24),
                        card.x + 12,
                        card.y + 90,
                        TEXT_MUTED,
                    )

        # ── RIGHT COLUMN ─────────────────────────────────────────
        y = TOP + 8
        RIGHT_W = W - right_x - 12

        # Health explainer card — height fits wrapped text, fully clipped
        title = ellipsize(font_sm, f"SYSTEM STATUS · {health_lab}", RIGHT_W - 24)
        why_lines = wrap_text(font_xs, health_why, RIGHT_W - 24, max_lines=4)
        hcard_h = 14 + font_sm.get_linesize() + 6 + len(why_lines) * font_xs.get_linesize() + 12
        hcard_h = max(64, min(120, hcard_h))
        hcard = pygame.Rect(right_x, y, RIGHT_W, hcard_h)
        rounded_panel(screen, hcard, PANEL, health_col, 10)
        prev_clip = screen.get_clip()
        screen.set_clip(hcard.inflate(-4, -4))
        draw_text(screen, font_sm, title, hcard.x + 12, hcard.y + 10, health_col)
        wy = hcard.y + 10 + font_sm.get_linesize() + 4
        for i, line in enumerate(why_lines):
            if wy + font_xs.get_linesize() > hcard.bottom - 6:
                break
            col = TEXT_DIM if i == 0 else TEXT_MUTED
            draw_text(screen, font_xs, line, hcard.x + 12, wy, col)
            wy += font_xs.get_linesize()
        screen.set_clip(prev_clip)
        y = hcard.bottom + 8

        # Pipeline
        row_h = 20
        pipe_h = 36 + len(STAGE_ORDER) * row_h + 8
        # fit: if too tall, shrink a bit by using smaller area and scroll conceptually
        max_pipe = H - BOT - y - 220
        pipe = pygame.Rect(right_x, y, RIGHT_W, min(pipe_h, max_pipe))
        rounded_panel(screen, pipe, PANEL, BORDER if state.focus != 1 else ACCENT, 10)
        draw_text(screen, font_sm, "CONCERT STAGES", pipe.x + 12, pipe.y + 8, TEXT_DIM)
        draw_text(screen, font_xs, "hover = what / why / when / config", pipe.x + 12, pipe.y + 24, TEXT_MUTED)
        py = pipe.y + 40
        pulse = 0.55 + 0.45 * math.sin(state.tick * 0.12)
        for stg in STAGE_ORDER:
            if py + row_h > pipe.bottom - 4:
                break
            st = state.stage_status.get(stg, "pending")
            col = STAGE_COLOR.get(st, GRAY)
            if st == "running":
                col = tuple(int(c * pulse + 40 * (1 - pulse)) for c in YELLOW)
            row = pygame.Rect(pipe.x + 6, py - 2, pipe.w - 12, row_h)
            if stg == state.hover_stage or stg == state.pinned_stage:
                pygame.draw.rect(screen, PANEL_2, row, border_radius=4)
            stage_hitboxes.append((row, stg))
            # Clip entire row so detail never escapes the panel
            prev_row = screen.get_clip()
            screen.set_clip(row)
            pygame.draw.circle(screen, col, (row.x + 12, py + 7), 5)
            light = {"ok": "GO", "running": "…", "fail": "STOP", "pending": "·", "skip": "skip"}.get(st, st)
            name_txt = f"{stg}  {light}"
            name_w = font_xs.size(name_txt)[0]
            draw_text(screen, font_xs, name_txt, row.x + 24, py, TEXT if st != "pending" else TEXT_MUTED)
            det = (state.stage_detail.get(stg, "") or "").replace("\n", " ").strip()
            if det:
                # detail sits to the right of the name, ellipsized into remaining width
                gap = 10
                det_x = row.x + 24 + name_w + gap
                det_max = max(24, row.right - det_x - 6)
                det_draw = ellipsize(font_xs, det, det_max)
                draw_text(screen, font_xs, det_draw, det_x, py, TEXT_MUTED)
            screen.set_clip(prev_row)
            py += row_h
        y = pipe.bottom + 8

        # Vectors
        vs = state.vector_stats
        vec = pygame.Rect(right_x, y, RIGHT_W, 88)
        rounded_panel(screen, vec, PANEL, BORDER, 10)
        draw_text(screen, font_sm, "VECTOR SEARCH INDEX", vec.x + 12, vec.y + 8, TEXT_DIM)
        draw_text(screen, font_kpi, str(vs.get("vectors", 0)), vec.x + 12, vec.y + 28, GREEN)
        draw_text(screen, font_xs, "embeddings on disk", vec.x + 12, vec.y + 54, TEXT_MUTED)
        draw_text(screen, font_xs, f"vocab terms {vs.get('vocab_terms', 0)}", vec.x + 140, vec.y + 34, TEXT)
        cov = min(1.0, float(vs.get("vectors") or 0) / max(1, nodes_n)) if nodes_n else 0
        pygame.draw.rect(screen, BORDER_SOFT, (vec.x + 12, vec.y + 72, vec.w - 24, 6), border_radius=3)
        pygame.draw.rect(screen, GREEN, (vec.x + 12, vec.y + 72, int((vec.w - 24) * cov), 6), border_radius=3)
        y = vec.bottom + 8

        # Signals traffic lights
        signals = {}
        if isinstance(state.metrics, dict):
            sb = state.metrics.get("scoreboard") or state.metrics
            signals = sb.get("signals") or state.metrics.get("signals") or {}
        sig_items = list(signals.items())[:6]
        met_h = 34 + max(1, len(sig_items)) * 18 + 8
        met = pygame.Rect(right_x, y, RIGHT_W, met_h)
        rounded_panel(screen, met, PANEL, BORDER, 10)
        draw_text(screen, font_sm, "METRICS (green/yellow/red)", met.x + 12, met.y + 8, TEXT_DIM)
        my = met.y + 30
        scmap = {"green": GREEN, "yellow": YELLOW, "red": RED}
        if not sig_items:
            draw_text(screen, font_xs, "No scoreboard yet — run a concert", met.x + 12, my, TEXT_MUTED)
        for sk, sv in sig_items:
            c = scmap.get(str(sv).lower(), GRAY)
            pygame.draw.circle(screen, c, (met.x + 18, my + 5), 5)
            draw_text(screen, font_xs, str(sk), met.x + 32, my, TEXT)
            draw_text(screen, font_xs, str(sv), met.x + met.w - 70, my, c)
            my += 18
        y = met.bottom + 8

        # Activity scroll
        rem = H - BOT - y - 10
        if rem > 60:
            evp = pygame.Rect(right_x, y, RIGHT_W, rem)
            rounded_panel(screen, evp, PANEL, BORDER, 10)
            draw_text(screen, font_sm, "ACTIVITY (scroll)", evp.x + 12, evp.y + 8, TEXT_DIM)
            ey = evp.y + 28
            lines = list(state.event_log)
            start = state.activity_scroll
            max_lines = max(2, (evp.height - 36) // 15)
            for line in lines[start : start + max_lines]:
                draw_text(screen, font_xs, line[:52], evp.x + 12, ey, TEXT_MUTED)
                ey += 15

        # ── BOTTOM ───────────────────────────────────────────────
        pygame.draw.rect(screen, PANEL, (0, H - BOT, W, BOT))
        pygame.draw.line(screen, BORDER, (0, H - BOT), (W, H - BOT), 1)
        rid = (state.last_run_id or "—")[:24]
        draw_text(
            screen,
            font_xs,
            f"H help   ·   Space pause/live   ·   R reshuffle   ·   final_ok={state.final_ok}   ·   "
            f"run={rid}   ·   Q quit",
            12,
            H - BOT + 12,
            TEXT_MUTED,
        )
        draw_text(screen, font_xs, time.strftime("%H:%M:%S"), W - 72, H - BOT + 12, TEXT_DIM)

        # Flyouts (after main UI so they sit on top)
        if state.hover_node and state.hover_node in state.nodes:
            n = state.nodes[state.hover_node]
            flyout(
                screen,
                font_sm,
                font_xs,
                [
                    f"type: {n.get('type')}",
                    f"source: {n.get('source')}",
                    f"tier: {n.get('tier')}  (T0=best … T3=low)",
                    f"id: {n.get('id')}",
                    f"tags: {', '.join((n.get('tags') or [])[:6]) or '—'}",
                ],
                mx,
                my,
                W,
                H,
                title=(n.get("title") or n.get("id") or "")[:60],
            )
        elif state.hover_stage or state.pinned_stage:
            stg = state.hover_stage or state.pinned_stage or ""
            flyout(
                screen,
                font_sm,
                font_xs,
                stage_hover_lines(state, stg),
                mx,
                my,
                W,
                H,
                title=f"Stage: {stg} — {STAGE_LABEL.get(stg, '')}",
                max_line=88,
                max_width=460,
            )
        # Hover status strip → full explanation (flyout stays on-screen)
        if status_strip.collidepoint(mx, my):
            flyout(
                screen,
                font_sm,
                font_xs,
                [
                    health_why,
                    f"ok={counts['ok']} run={counts['running']} fail={counts['fail']} pending={counts['pending']}",
                    "Click × Close or press Q / Esc to quit GodsEye",
                ],
                mx,
                my,
                W,
                H,
                title=f"Status: {health_lab}",
            )

        if state.show_help:
            help_overlay(screen, font_title, font_sm, font_xs, W, H)

        pygame.display.flip()
        clock.tick(30)

    # dismiss on close
    try:
        sys.path.insert(0, str(brain_home() / "scripts"))
        from godseye import mark_dismissed  # type: ignore

        mark_dismissed()
    except Exception:
        st = brain_dir() / "state"
        st.mkdir(parents=True, exist_ok=True)
        try:
            (st / "godseye.dismissed").write_text("1\n", encoding="utf-8")
        except Exception:
            pass
        for name in ("godseye.pid", "visualizer.pid"):
            p = st / name
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
    pygame.quit()
    return 0


def _w2s(state: LiveState, graph_rect: pygame.Rect, x: float, y: float):
    try:
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        sx = int((x + state.pan[0] - graph_rect.w / 2) * state.zoom + graph_rect.centerx)
        sy = int((y + state.pan[1] - graph_rect.h / 2) * state.zoom + graph_rect.centery)
        return sx, sy
    except (ValueError, OverflowError, TypeError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
