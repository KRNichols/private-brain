#!/usr/bin/env python3
"""
Private Brain GodsEye — TRUE OpenGL Live Ops

Apple-simple by default: full-bleed graph + one health pill.
Ops chrome (stages / vectors / metrics) lives behind the Inspector (I).
Layout stays LIVE by default (gentle continuous motion). Space freezes/unfreezes.

  PB_GODSEYE_BACKEND=gl   (default via godseye.py)
  PB_GODSEYE_BACKEND=cpu  → live_gui.py software fallback

Controls (simple):
  drag / wheel   pan / zoom
  click          select node (floating sheet)
  double-click   focus camera on node
  I              Inspector on/off (ops rail)
  H              help (cycles SIMPLE ↔ ADVANCED)
  Space          freeze ↔ live motion
  Q / Esc        close overlay → quit

Power (Inspector or help):
  R reseed · S reload · F/T filters · 1-5 tiers · E evidence path
  L legend · P stages compact · M minimap · N neighbors · [ ] trail
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

try:
    import pygame
    from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE
except ImportError:
    raise SystemExit("pip install pygame")

os.environ.setdefault("PYOPENGL_PLATFORM", os.environ.get("PYOPENGL_PLATFORM", ""))

try:
    from OpenGL.GL import (
        GL_ARRAY_BUFFER,
        GL_BLEND,
        GL_COLOR_ARRAY,
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_DYNAMIC_DRAW,
        GL_FLOAT,
        GL_LINES,
        GL_LINE_SMOOTH,
        GL_LINE_SMOOTH_HINT,
        GL_LINEAR,
        GL_MODELVIEW,
        GL_NICEST,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_POINTS,
        GL_POINT_SMOOTH,
        GL_POINT_SMOOTH_HINT,
        GL_PROJECTION,
        GL_QUADS,
        GL_RGBA,
        GL_SCISSOR_TEST,
        GL_SRC_ALPHA,
        GL_STATIC_DRAW,
        GL_TEXTURE_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_TRIANGLE_FAN,
        GL_UNSIGNED_BYTE,
        GL_VERTEX_ARRAY,
        glBegin,
        glBindBuffer,
        glBindTexture,
        glBlendFunc,
        glBufferData,
        glClear,
        glClearColor,
        glColor4f,
        glColorPointer,
        glDisable,
        glDisableClientState,
        glDrawArrays,
        glEnable,
        glEnableClientState,
        glEnd,
        glGenBuffers,
        glGenTextures,
        glHint,
        glLineWidth,
        glLoadIdentity,
        glMatrixMode,
        glOrtho,
        glPointSize,
        glScalef,
        glScissor,
        glTexCoord2f,
        glTexImage2D,
        glTexParameteri,
        glTranslatef,
        glVertex2f,
        glVertexPointer,
        glViewport,
    )
except ImportError:
    raise SystemExit("TRUE GL needs PyOpenGL — pip install PyOpenGL (or PB_GODSEYE_BACKEND=cpu)")

# Optional numpy for GPU-side float buffers (home free; Corporate Library optional)
try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore


# Hard caps — full corpus can be 10k–100k+; viz MUST subsample.
# Env overrides for load-test only: PB_GODSEYE_MAX_NODES / PB_GODSEYE_MAX_EDGES
def _env_int(name: str, default: int) -> int:
    try:
        return max(200, int(os.environ.get(name, default)))
    except Exception:
        return default


SNAPSHOT_VIZ_MAX = _env_int("PB_GODSEYE_MAX_NODES", 2800)
DRAW_NODES = _env_int("PB_GODSEYE_DRAW_NODES", 2800)
DRAW_EDGES = _env_int("PB_GODSEYE_DRAW_EDGES", 3200)
LAYOUT_NODES = _env_int("PB_GODSEYE_LAYOUT_NODES", 280)
LAYOUT_EDGE_SPRINGS = _env_int("PB_GODSEYE_LAYOUT_EDGES", 500)
# Adaptive LOD: if frame > this many ms, drop edges/nodes next frame
TARGET_FRAME_MS = float(os.environ.get("PB_GODSEYE_TARGET_MS", "22"))
RIGHT_W = 400
# Top bar is a FIXED 3-zone strip — never pack 4 lines into 56px
TOP_H = 64
BOT_H = 28
# Soft community palette for constellation hulls
_COMMUNITY_PALETTE = (
    (0.35, 0.55, 0.95),
    (0.95, 0.45, 0.25),
    (0.25, 0.80, 0.55),
    (0.75, 0.35, 0.85),
    (0.95, 0.75, 0.20),
    (0.30, 0.70, 0.90),
    (0.90, 0.30, 0.55),
    (0.55, 0.85, 0.40),
)

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

_CHUNK = frozenset({
    "Comment", "MRComment", "SessionTurn", "BrainChunk", "Pipeline", "SwarmCrumb", "Chunk",
})
_ORIGIN = frozenset({
    "HAS_ISSUE", "HAS_MR", "HAS_COMMENT", "HAS_PIPELINE", "HAS_RELEASE",
    "CONTAINS", "PARENT_OF", "HAS_TURN", "HAS_AGENT", "CONTAINS_FILE",
    "HAS_TREE", "HAS_BRANCH", "HAS_PAGE", "HAS_WIKI", "REFERENCES",
    "SWARM_TAGGED", "HAS_CHUNK", "NEXT_CHUNK",
})
_TIER_RANK = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}

TIER_RGB = {
    "T0": (0.18, 0.80, 0.44),
    "T1": (0.20, 0.60, 0.86),
    "T2": (0.95, 0.77, 0.06),
    "T3": (0.45, 0.47, 0.50),
}
SOURCE_RGB = {
    "gitlab": (0.90, 0.49, 0.13),
    "github": (0.95, 0.95, 0.97),
    "jira": (0.16, 0.50, 0.73),
    "confluence": (0.12, 0.40, 0.75),
    "brain": (0.56, 0.27, 0.68),
    "codex_session": (0.61, 0.35, 0.71),
    "metrics": (0.10, 0.74, 0.61),
    "local": (0.20, 0.80, 0.55),
    "brutal_suite": (0.75, 0.25, 0.35),
    "perf": (0.45, 0.45, 0.50),
    "codecommit": (0.95, 0.60, 0.20),
}
# Hub types get larger seeds (projects/repos = constellation anchors)
_HUB_TYPES = frozenset({
    "Project", "Repo", "Group", "Subgroup", "Space", "JiraProject",
    "SourceHub", "FamilyHub", "KnowledgeHub", "TypeHub", "Epic",
})


def brain_home() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser()
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "private-brain"


def brain_dir() -> Path:
    return brain_home() / ".brain"


def sample_nodes(raw: list[dict], max_n: int) -> list[dict]:
    if len(raw) <= max_n:
        return raw
    by: dict[str, list[dict]] = defaultdict(list)
    for n in raw:
        by[str(n.get("source") or "unknown")].append(n)
    for src in by:
        by[src].sort(
            key=lambda n: (
                1 if (n.get("type") or "") in _CHUNK else 0,
                _TIER_RANK.get(str(n.get("tier") or "T3"), 4),
                str(n.get("id") or ""),
            )
        )
    out: list[dict] = []
    srcs = sorted(by.keys())
    i = 0
    while len(out) < max_n and any(by[s] for s in srcs):
        s = srcs[i % len(srcs)]
        if by[s]:
            out.append(by[s].pop(0))
        i += 1
    return out


class TextCache:
    """GPU-textured glyphs with hard pixel clipping — text never escapes its box."""

    def __init__(self) -> None:
        self._cache: dict[tuple, int] = {}
        self._size: dict[int, tuple[int, int]] = {}
        self.screen_h = 900

    def set_screen(self, h: int) -> None:
        self.screen_h = max(1, int(h))

    @staticmethod
    def ellipsize(font: pygame.font.Font, text: str, max_px: int) -> str:
        """Fit text to max_px pixels; append … if truncated."""
        t = (text or "").replace("\n", " ").replace("\t", " ").strip()
        if max_px <= 10 or not t:
            return ""
        if font.size(t)[0] <= max_px:
            return t
        lo, hi = 0, len(t)
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = t[:mid].rstrip() + "…"
            if font.size(cand)[0] <= max_px:
                best = cand
                lo = mid + 1
            else:
                hi = mid - 1
        return best or "…"

    def texture(self, font: pygame.font.Font, text: str, color=(220, 225, 235)) -> tuple[int, int, int]:
        key = (id(font), text[:180], color)
        if key in self._cache:
            tid = self._cache[key]
            return tid, self._size[tid][0], self._size[tid][1]
        surf = font.render(text[:180], True, color)
        w, h = surf.get_size()
        tw = max(1, 1 << max(0, (w - 1).bit_length()))
        th = max(1, 1 << max(0, (h - 1).bit_length()))
        pad = pygame.Surface((tw, th), pygame.SRCALPHA)
        pad.blit(surf, (0, 0))
        data = pygame.image.tostring(pad, "RGBA", True)
        tid = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        self._cache[key] = tid
        self._size[tid] = (w, h)
        return tid, w, h

    def draw(
        self,
        font: pygame.font.Font,
        text: str,
        x: float,
        y: float,
        color=(220, 225, 235),
        max_w: int | None = None,
        *,
        clip: tuple[float, float, float, float] | None = None,
    ) -> float:
        """Draw text; return width used. clip=(cx,cy,cw,ch) hard-scissors to zone."""
        if not text:
            return 0.0
        t = text
        if max_w is not None and max_w > 0:
            t = self.ellipsize(font, t, max_w)
            if not t:
                return 0.0
        tid, w, h = self.texture(font, t, color)
        # Never draw outside clip box (prevents run-over into other zones)
        if clip is not None:
            cx, cy, cw, ch = clip
            if x >= cx + cw or y >= cy + ch or x + w <= cx or y + h <= cy:
                return 0.0
            # GL scissor uses bottom-left origin
            glEnable(GL_SCISSOR_TEST)
            glScissor(
                max(0, int(cx)),
                max(0, int(self.screen_h - (cy + ch))),
                max(1, int(cw)),
                max(1, int(ch)),
            )
        tw = max(1, 1 << max(0, (w - 1).bit_length()))
        th = max(1, 1 << max(0, (h - 1).bit_length()))
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tid)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1)
        glVertex2f(x, y)
        glTexCoord2f(w / tw, 1)
        glVertex2f(x + w, y)
        glTexCoord2f(w / tw, 1 - h / th)
        glVertex2f(x + w, y + h)
        glTexCoord2f(0, 1 - h / th)
        glVertex2f(x, y + h)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        if clip is not None:
            glDisable(GL_SCISSOR_TEST)
        return float(w)


def gl_rect(x: float, y: float, w: float, h: float, rgb: tuple[float, float, float], a: float = 1.0) -> None:
    glColor4f(rgb[0], rgb[1], rgb[2], a)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()


def gl_rect_border(x: float, y: float, w: float, h: float, rgb: tuple[float, float, float], a: float = 1.0) -> None:
    glColor4f(rgb[0], rgb[1], rgb[2], a)
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for x1, y1, x2, y2 in (
        (x, y, x + w, y),
        (x + w, y, x + w, y + h),
        (x + w, y + h, x, y + h),
        (x, y + h, x, y),
    ):
        glVertex2f(x1, y1)
        glVertex2f(x2, y2)
    glEnd()


class LiveGL:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.pos: dict[str, list[float]] = {}
        self.vel: dict[str, list[float]] = {}
        self.adj: dict[str, list[tuple[str, str, str]]] = {}
        self.zoom = 1.0
        self.pan = [0.0, 0.0]
        self.selected: str | None = None
        self.trail: list[str] = []
        self.trail_focus = 0
        self.lit_nodes: dict[str, float] = {}
        self.lit_edges: set[tuple[str, str]] = set()
        self.source_filter = "all"
        self.tier_filter = "all"
        # LIVE by default — continuous gentle motion
        self.layout_live = True
        self.snap_mtime = 0.0
        self.dag_mtime = 0.0
        self.events_offset = 0
        self.tick = 0
        self.show_help = False
        # Dual-audience help: "simple" (anyone) | "advanced" (senior) — H cycles
        self.help_mode: str = "simple"
        self.show_legend = False
        self.snapshot_total = 0
        self.event_log: deque[str] = deque(maxlen=60)
        self.texts = TextCache()
        self.stage_status: dict[str, str] = {s: "pending" for s in STAGE_ORDER}
        self.stage_detail: dict[str, str] = {}
        self.last_run_id = ""
        self.final_ok: bool | None = None
        self.vector_stats: dict[str, Any] = {}
        self.metrics: dict[str, Any] = {}
        # GraphRAG-style evidence path (from last concert retrieve)
        self.evidence_ids: list[str] = []
        self.evidence_blobs: list[dict[str, Any]] = []  # dual-pane snippets
        self.path_autoplay = False
        self._path_autoplay_t = 0.0
        self.community_centers: dict[str, tuple[float, float, float]] = {}  # src -> cx,cy,r
        self.rate_band: str = ""
        self.edge_count_total = 0
        self.brain_stats: dict[str, Any] = {}
        # Performance / adaptive LOD (suite-visible)
        self.frame_ms = 0.0
        self.fps = 0.0
        self.lod_scale = 1.0  # 1.0 full budget → drops toward 0.25 under load
        self.drawn_nodes = 0
        self.drawn_edges = 0
        self.perf_warn = ""
        self._frame_t0 = time.perf_counter()
        self._fps_ema = 60.0
        self._work_ms = 0.0
        # Ops metrics (purity / audit / embed) for METRICS panel + godseye_metrics.json
        self.purity: dict[str, Any] = {}
        self.audit_chain_ok: bool | None = None
        self.embed_backend: str = ""
        self._last_metrics_snap_t = 0.0
        self._last_ops_reload_t = 0.0
        # Ultra-app interaction state
        self.hover_id: str | None = None
        self.layout_energy = 1.0
        self.layout_settled = False
        self.cam_target: list[float] | None = None  # [pan_x, pan_y, zoom] smooth lerp
        # Apple-simple defaults: graph first; ops chrome only on demand
        self.show_inspector = False  # I toggles right ops rail
        self.show_minimap = False
        self.stages_compact = True  # compact stage strip (ultra HUD)
        self.mouse_xy = (0, 0)
        self.cloud_health: dict[str, Any] = {}
        # GPU path: vertex arrays / VBO (not immediate-mode glBegin spam)
        self._np = np
        self.gpu_path = "vertex_array" if np is not None else "immediate_fallback"
        self.gpu_vendor = ""
        self.gpu_renderer = ""
        self.gpu_version = ""
        self._vbo_edges = 0
        self._vbo_nodes = 0
        self._has_vbo = False
        self._stars: list[tuple[float, float, float]] = []  # x,y,bright background dust
        self._last_click_t = 0.0
        self._last_click_pos = (0, 0)
        self._last_click_nid: str | None = None
        self._hover_title_cache: dict[str, str] = {}
        try:
            # probe once after context exists (setup_gl / main sets strings)
            self._has_vbo = callable(glGenBuffers) and callable(glBindBuffer)
        except Exception:
            self._has_vbo = False

    def graph_rect(self) -> tuple[float, float, float, float]:
        """Full-bleed graph; reserve right rail only when Inspector is open."""
        if self.show_inspector:
            return 0.0, 0.0, max(200.0, float(self.w - RIGHT_W - 12)), float(self.h)
        return 0.0, 0.0, float(self.w), float(self.h)

    def _clip_box(
        self, x: float, y: float, w: float, h: float
    ) -> tuple[float, float, float, float]:
        """Clamp a clip rect to the window so nothing can bleed off-screen."""
        x = max(0.0, float(x))
        y = max(0.0, float(y))
        w = max(1.0, min(float(w), float(self.w) - x))
        h = max(1.0, min(float(h), float(self.h) - y))
        return x, y, w, h

    def visible(self, n: dict) -> bool:
        if self.source_filter != "all" and n.get("source") != self.source_filter:
            return False
        if self.tier_filter != "all" and n.get("tier") != self.tier_filter:
            return False
        return True

    def reload_snapshot(self, path: Path) -> None:
        if not path.exists():
            return
        m = path.stat().st_mtime
        if m == self.snap_mtime:
            return
        self.snap_mtime = m
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = list(data.get("nodes") or [])
        raw_e = list(data.get("edges") or [])
        self.snapshot_total = len(raw)
        # Always subsample when over viz budget — full 12k hairball freezes GL
        cap = SNAPSHOT_VIZ_MAX
        if len(raw) > cap:
            picked = sample_nodes(raw, cap)
        else:
            picked = raw
        self.nodes = {n["id"]: n for n in picked if n.get("id")}
        keep = set(self.nodes)
        # Prefer structural / same-island edges; hard-cap to DRAW_EDGES*1.2 stored
        edge_store_cap = max(DRAW_EDGES, int(DRAW_EDGES * 1.25))
        kept_e: list[dict] = []
        # pass 1: same-source edges
        for e in raw_e:
            if len(kept_e) >= edge_store_cap:
                break
            s, d = e.get("src"), e.get("dst")
            if s not in keep or d not in keep:
                continue
            sa = str((self.nodes.get(s) or {}).get("source") or "")
            sb = str((self.nodes.get(d) or {}).get("source") or "")
            if sa == sb:
                kept_e.append(e)
        # pass 2: cross-source (constellation bridges) if budget remains
        if len(kept_e) < edge_store_cap:
            for e in raw_e:
                if len(kept_e) >= edge_store_cap:
                    break
                s, d = e.get("src"), e.get("dst")
                if s not in keep or d not in keep:
                    continue
                sa = str((self.nodes.get(s) or {}).get("source") or "")
                sb = str((self.nodes.get(d) or {}).get("source") or "")
                if sa != sb:
                    kept_e.append(e)
        self.edges = kept_e
        self.edge_count_total = len(raw_e)
        self.brain_stats = data.get("stats") or {}
        # reset LOD so a new smaller graph can recover smoothness
        self.lod_scale = 1.0
        self.perf_warn = ""
        need = [i for i in self.nodes if i not in self.pos]
        full_reseed = False
        if need:
            self._seed_islands(need)
            self.layout_live = True
            full_reseed = len(need) > len(self.nodes) * 0.5
        for nid in list(self.pos):
            if nid not in self.nodes:
                del self.pos[nid]
                self.vel.pop(nid, None)
        self._rebuild_adj()
        if self.selected and self.selected in self.nodes:
            self.select_node(self.selected)
        # On big load, center camera on constellation centroid (world free, not box-fit)
        if full_reseed and self.pos:
            cx = sum(p[0] for p in self.pos.values()) / len(self.pos)
            cy = sum(p[1] for p in self.pos.values()) / len(self.pos)
            gx, gy, gw, gh = self.graph_rect()
            # pan so centroid sits in graph panel center
            self.pan[0] = (gx + gw / 2) - cx
            self.pan[1] = (gy + gh / 2) - cy
            self.zoom = 0.55  # start slightly zoomed out so islands read as constellations
        self.event_log.appendleft(f"graph  nodes={len(self.nodes)} edges={len(self.edges)} universe=free")

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
        rid = str(data.get("run_id") or "")
        if rid != self.last_run_id:
            self.last_run_id = rid
            self.stage_status = {s: "pending" for s in STAGE_ORDER}
            self.stage_detail = {}
            self.event_log.appendleft(f"concert  {rid[:28]}")
        self.final_ok = data.get("final_ok")
        rate = data.get("rate") or {}
        if isinstance(rate, dict):
            self.rate_band = str(rate.get("band") or "")
        # evidence node ids for path lighting (GraphRAG trail) + dual-pane snippets
        ev = (data.get("retrieve") or {}).get("evidence") or data.get("evidence") or []
        ids: list[str] = []
        blobs: list[dict[str, Any]] = []
        if isinstance(ev, list):
            for e in ev:
                if isinstance(e, dict) and e.get("id"):
                    ids.append(str(e["id"]))
                    blobs.append(
                        {
                            "id": str(e.get("id") or ""),
                            "title": str(e.get("title") or e.get("id") or "")[:120],
                            "tier": str(e.get("tier") or ""),
                            "source": str(e.get("source") or ""),
                            "snippet": str(
                                e.get("snippet") or e.get("content") or e.get("text") or e.get("summary") or ""
                            )[:420],
                        }
                    )
                elif isinstance(e, str):
                    ids.append(e)
                    blobs.append({"id": e, "title": e, "tier": "", "source": "", "snippet": ""})
        prev = list(self.evidence_ids)
        self.evidence_ids = ids[:24]
        self.evidence_blobs = blobs[:24]
        # autoplay path when new concert evidence arrives
        if self.evidence_ids and self.evidence_ids != prev:
            self.start_path_autoplay(self.evidence_ids)
        self._apply_dag_stages(data)

    def _apply_dag_stages(self, data: dict[str, Any]) -> None:
        def mark(name: str, blob: Any) -> None:
            if blob is None or not isinstance(blob, dict):
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
                sigs = blob.get("signals") or {}
                if isinstance(sigs, dict) and sigs:
                    bad = [k for k, v in sigs.items() if str(v).lower() not in ("green", "ok", "pass")]
                    detail = f"{len(sigs) - len(bad)}/{len(sigs)} green" + (f" · {bad[0]}" if bad else "")
            if name == "rate":
                detail = f"{blob.get('band')} {blob.get('concert_score')}/{blob.get('max')}"
            if name == "critic":
                detail = f"{blob.get('verdict')} {blob.get('score')}/{blob.get('max')}"
            if name == "optimize":
                detail = "skip" if blob.get("skipped") else ("ok" if blob.get("ok") else str(blob.get("reason") or "")[:24])
            if name == "swarm":
                n = blob.get("n_agents") or blob.get("agents") or ""
                w = blob.get("writes") or blob.get("total_writes") or ""
                detail = f"×{n}" + (f" w={w}" if w != "" else "") if (n or w) else ("skip" if blob.get("skipped") else "ok")
            if name == "crawl_gap" and blob.get("reason"):
                detail = str(blob.get("reason"))[:28]
            if name == "boot":
                rec = blob.get("recovery") or {}
                ms = rec.get("elapsed_ms")
                sc = blob.get("session_crawl") or {}
                if ms is not None:
                    detail = f"{ms}ms" + (f" +{sc.get('ingested', 0)}s" if sc else "")
            self.stage_detail[name] = str(detail).replace("\n", " ")[:36]

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
        if data.get("final_ok") is not None:
            if data.get("swarm") is None and self.stage_status.get("swarm") in ("pending", "running"):
                self.stage_status["swarm"] = "skip"
                self.stage_detail["swarm"] = "off (--swarm N)"
            if data.get("optimize") is None and self.stage_status.get("optimize") in ("pending", "running"):
                self.stage_status["optimize"] = "skip"
                self.stage_detail["optimize"] = "skip (pass band)"
            for s in STAGE_ORDER:
                if self.stage_status.get(s) == "running":
                    self.stage_status[s] = "ok"

    def poll_events(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return
        if len(lines) <= self.events_offset:
            return
        for line in lines[self.events_offset :]:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            stage = ev.get("stage") or ev.get("action") or ""
            status = ev.get("status") or ev.get("result") or "running"
            det = str(ev.get("detail") or "")
            ids = ev.get("ids") or (ev.get("props") or {}).get("ids") or []
            edges = ev.get("edges") or (ev.get("props") or {}).get("edges") or []
            if ids and status in ("ok", "success") and (ev.get("pathway") or stage == "retrieve"):
                for i in ids:
                    self.lit_nodes[str(i)] = 1.0
                for e in edges if isinstance(edges, list) else []:
                    a, b = e.get("src"), e.get("dst")
                    if a and b:
                        self.lit_edges.add((a, b) if a < b else (b, a))
                self.event_log.appendleft(f"pathway fire n={len(ids)}")
            if stage in self.stage_status:
                if status in ("start", "running"):
                    if self.stage_status.get(stage) not in ("ok", "fail", "skip"):
                        self.stage_status[stage] = "running"
                elif status in ("ok", "success"):
                    self.stage_status[stage] = "ok"
                elif status in ("fail", "error"):
                    self.stage_status[stage] = "fail"
                elif status in ("skip", "skipped"):
                    self.stage_status[stage] = "skip"
                # only compact details from live events — never stomp with novels
                if det and status in ("ok", "success", "skip", "fail", "running", "start"):
                    short = det.replace("\n", " ").strip()
                    # drop noise that bleeds UI (GodsEye dismiss noise, dict dumps)
                    if "GodsEye" in short and stage != "boot":
                        pass
                    elif short.startswith("{") or len(short) > 48:
                        self.stage_detail[stage] = short[:28] + "…"
                    else:
                        self.stage_detail[stage] = short[:32]
            self.event_log.appendleft(f"{stage}:{status}  {det[:36]}")
        self.events_offset = len(lines)

    def reload_vectors(self, emb_dir: Path) -> None:
        """Count vectors + backend without parsing the multi‑MB pack file."""
        if not emb_dir.is_dir():
            self.vector_stats = {"vectors": 0, "vocab_terms": 0, "embed_backend": self.embed_backend}
            return
        # Throttle: full glob of 20k+ files is fine occasionally, not every poll
        now = time.time()
        last = float(getattr(self, "_last_vec_reload_t", 0.0) or 0.0)
        cached_n = int((self.vector_stats or {}).get("vectors") or 0)
        if cached_n and (now - last) < 8.0:
            return
        self._last_vec_reload_t = now

        n = 0
        terms = int((self.vector_stats or {}).get("vocab_terms") or 0)
        backend = self.embed_backend or ""

        # Prefer lightweight pack *header* only (file can be 100MB+; never full json.loads)
        pack = emb_dir / "_vectors_pack.json"
        if pack.exists():
            try:
                with pack.open("r", encoding="utf-8") as fh:
                    head = fh.read(2048)
                m_n = re.search(r'"n"\s*:\s*(\d+)', head)
                if m_n:
                    n = int(m_n.group(1))
                m_b = re.search(r'"embed_backend"\s*:\s*"([^"]+)"', head)
                m_a = re.search(r'"algo"\s*:\s*"([^"]+)"', head)
                if m_b:
                    backend = m_b.group(1)
                elif m_a and not backend:
                    backend = m_a.group(1)
            except OSError:
                pass

        if not n:
            # Fallback: directory entry count (skip underscore meta files)
            try:
                n = sum(1 for p in emb_dir.glob("*.json") if not p.name.startswith("_"))
            except OSError:
                n = cached_n

        vocab = emb_dir / "_vocab.json"
        if vocab.exists():
            try:
                # vocab can be large — only re-read occasionally / first time
                if not terms or (now - last) >= 30.0 or not getattr(self, "_vocab_cached", False):
                    v = json.loads(vocab.read_text(encoding="utf-8"))
                    terms = len(v.get("df") or {})
                    backend = backend or str(v.get("embed_backend") or v.get("algo") or "")
                    self._vocab_cached = True
            except (json.JSONDecodeError, OSError):
                pass

        if not backend:
            backend = (
                os.environ.get("PB_EMBED_BACKEND")
                or os.environ.get("PB_EMBEDDING_BACKEND")
                or "tfidf"
            ).strip()
        self.embed_backend = backend
        self.vector_stats = {"vectors": n, "vocab_terms": terms, "embed_backend": backend}

    def reload_metrics(self, metrics_dir: Path) -> None:
        for name in ("current.json", "full.json"):
            p = metrics_dir / name
            if p.exists():
                try:
                    self.metrics = json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
                # Pull audit flag from engineering section when present
                eng = (self.metrics.get("engineering") or {}) if isinstance(self.metrics, dict) else {}
                if isinstance(eng, dict):
                    if "audit_chain_ok" in eng:
                        self.audit_chain_ok = bool(eng.get("audit_chain_ok"))
                    dev = eng.get("devsecops") or {}
                    if isinstance(dev, dict) and "audit_chain_ok" in dev:
                        self.audit_chain_ok = bool(dev.get("audit_chain_ok"))
                return

    def reload_purity(self) -> None:
        """Corpus purity ops flags from .brain/state/corpus_purity.json."""
        p = brain_dir() / "state" / "corpus_purity.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            self.purity = {
                "pilot_ready": bool(data.get("pilot_ready")),
                "pilot_ops_ready": bool(data.get("pilot_ops_ready")),
                "public_ratio": float(data.get("public_ratio") or 0.0),
                "public_ratio_pct": float(
                    data.get("public_ratio_pct")
                    or (float(data.get("public_ratio") or 0.0) * 100.0)
                ),
                "quarantine_cov": float(
                    data.get("quarantine_coverage")
                    or data.get("quarantine_cov")
                    or 0.0
                ),
                "total_nodes": int(data.get("total_nodes") or 0),
                "clean_nodes": int(data.get("clean_nodes") or 0),
            }
            g = data.get("graph") or {}
            if isinstance(g, dict) and g.get("edge_count") and not self.edge_count_total:
                try:
                    self.edge_count_total = int(g["edge_count"])
                except (TypeError, ValueError):
                    pass
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    def reload_audit_status(self) -> None:
        """Lightweight audit chain OK if readable from state (no full rewrite scan)."""
        # Already know? refresh slowly
        if self.audit_chain_ok is not None and (time.time() - getattr(self, "_last_audit_reload_t", 0.0)) < 12.0:
            return
        self._last_audit_reload_t = time.time()
        st = brain_dir() / "state"
        eng = (self.metrics.get("engineering") or {}) if isinstance(self.metrics, dict) else {}
        if isinstance(eng, dict):
            if "audit_chain_ok" in eng:
                self.audit_chain_ok = bool(eng.get("audit_chain_ok"))
                return
            dev = eng.get("devsecops") or {}
            if isinstance(dev, dict) and "audit_chain_ok" in dev:
                self.audit_chain_ok = bool(dev.get("audit_chain_ok"))
                return
        for name in ("audit_chain.json", "audit_status.json", "chain_status.json"):
            p = st / name
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "ok" in data:
                    self.audit_chain_ok = bool(data.get("ok"))
                    return
            except (json.JSONDecodeError, OSError):
                pass
        p = st / "fire_drill.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                stack = [data]
                while stack:
                    cur = stack.pop()
                    if isinstance(cur, dict):
                        nm = str(cur.get("name") or "")
                        if "audit_chain" in nm and "ok" in cur:
                            self.audit_chain_ok = bool(cur.get("ok"))
                            return
                        stack.extend(cur.values())
                    elif isinstance(cur, list):
                        stack.extend(cur)
            except (json.JSONDecodeError, OSError):
                pass
        try:
            audit = brain_dir() / "audit"
            newest = max(audit.glob("events-*.jsonl"), key=lambda x: x.stat().st_mtime, default=None)
            if newest is not None and newest.stat().st_size > 20:
                if self.audit_chain_ok is None:
                    self.audit_chain_ok = True
        except OSError:
            pass

    def reload_ops_state(self) -> None:
        """Throttle purity + audit reloads (not every poll)."""
        now = time.time()
        if now - self._last_ops_reload_t < 2.5 and self.purity:
            return
        self._last_ops_reload_t = now
        self.reload_purity()
        self.reload_audit_status()

    def reload_cloud_health(self) -> None:
        """Neptune / OpenSearch / SHIM health for ops panel (when endpoints set)."""
        neptune = bool(os.environ.get("PB_NEPTUNE_ENDPOINT"))
        opensearch = bool(os.environ.get("PB_OPENSEARCH_ENDPOINT"))
        llm_shim = bool(os.environ.get("PB_LLM_BASE_URL"))
        try:
            from infra_test import test_cloud  # type: ignore

            checks = test_cloud()
            # derive simple status strings for HUD
            def _status(key: str, configured: bool) -> str:
                if not configured:
                    return "off"
                for c in checks or []:
                    nm = str((c or {}).get("name") or "").lower()
                    if key in nm:
                        return "ok" if c.get("ok") else "fail"
                return "cfg"

            self.cloud_health = {
                "ts": time.time(),
                "checks": checks,
                "neptune": neptune,
                "opensearch": opensearch,
                "llm_shim": llm_shim,
                "neptune_status": _status("neptune", neptune),
                "opensearch_status": _status("opensearch", opensearch),
                "shim_status": _status("shim", llm_shim) if llm_shim else (
                    _status("llm", llm_shim) if llm_shim else "off"
                ),
            }
            if llm_shim and self.cloud_health["shim_status"] == "off":
                self.cloud_health["shim_status"] = "cfg"
        except Exception as e:
            self.cloud_health = {
                "error": str(e)[:120],
                "neptune": neptune,
                "opensearch": opensearch,
                "llm_shim": llm_shim,
                "neptune_status": "cfg" if neptune else "off",
                "opensearch_status": "cfg" if opensearch else "off",
                "shim_status": "cfg" if llm_shim else "off",
            }

    def build_metrics_snapshot(self) -> dict[str, Any]:
        """Doctor/fire_drill-facing snapshot (richer than godseye_perf)."""
        pur = self.purity or {}
        ch = self.cloud_health or {}
        vec_n = int(self.vector_stats.get("vectors") or 0)
        # optional ops scoreboard (written by beastMode --metrics / fire_drill)
        ops_score: dict[str, Any] = {}
        try:
            om = brain_dir() / "state" / "ops_metrics.json"
            if om.exists() and (time.time() - om.stat().st_mtime) < 600:
                blob = json.loads(om.read_text(encoding="utf-8"))
                ops_score = {
                    "band": (blob.get("score") or {}).get("band"),
                    "ops_100": (blob.get("score") or {}).get("ops_100"),
                    "age_s": round(time.time() - om.stat().st_mtime, 1),
                }
        except Exception:
            pass
        sessions_n = 0
        try:
            for _nid, n in (self.nodes or {}).items():
                if str((n or {}).get("source") or "") == "codex_session":
                    sessions_n += 1
            if not sessions_n and isinstance(self.source_counts, dict):
                sessions_n = int(self.source_counts.get("codex_session") or 0)
        except Exception:
            sessions_n = 0
        return {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ts_unix": time.time(),
            "fps": round(self.fps, 1),
            "frame_ms": round(self.frame_ms, 1),
            "work_ms": round(getattr(self, "_work_ms", 0.0), 1),
            "lod_scale": round(self.lod_scale, 3),
            "layout_settled": bool(self.layout_settled),
            "layout_energy": round(self.layout_energy, 4),
            "layout_live": bool(self.layout_live),
            "layout_mode": "LIVE" if self.layout_live else "FROZEN",
            "rate_band": self.rate_band or "",
            "graph": {
                "loaded_nodes": len(self.nodes),
                "loaded_edges": len(self.edges),
                "drawn_nodes": self.drawn_nodes,
                "drawn_edges": self.drawn_edges,
                "corpus_nodes": self.snapshot_total,
                "corpus_edges": self.edge_count_total,
            },
            "vectors": {
                "count": vec_n,
                "embed_backend": self.embed_backend
                or str(self.vector_stats.get("embed_backend") or ""),
                "vocab_terms": int(self.vector_stats.get("vocab_terms") or 0),
            },
            "sessions": sessions_n,
            "ops_score": ops_score,
            "purity": {
                "pilot_ready": pur.get("pilot_ready"),
                "pilot_ops_ready": pur.get("pilot_ops_ready"),
                "public_ratio": pur.get("public_ratio"),
                "public_ratio_pct": pur.get("public_ratio_pct"),
                "quarantine_cov": pur.get("quarantine_cov"),
            },
            "cloud": {
                "neptune": ch.get("neptune_status") or ("cfg" if ch.get("neptune") else "off"),
                "opensearch": ch.get("opensearch_status") or ("cfg" if ch.get("opensearch") else "off"),
                "shim": ch.get("shim_status") or ("cfg" if ch.get("llm_shim") else "off"),
            },
            "audit_chain_ok": self.audit_chain_ok,
            "gpu_path": self.gpu_path,
            "perf_warn": self.perf_warn,
            "simple_mode": not bool(self.show_inspector),
            "inspector": bool(self.show_inspector),
            "minimap": bool(self.show_minimap),
            "ok": self.fps >= 28 or self.tick < 45,
        }

    def write_metrics_snapshot(self, force: bool = False) -> None:
        """Write .brain/state/godseye_metrics.json about every 2s for fire_drill/doctor."""
        now = time.time()
        if not force and (now - self._last_metrics_snap_t) < 2.0:
            return
        self._last_metrics_snap_t = now
        try:
            path = brain_dir() / "state" / "godseye_metrics.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.build_metrics_snapshot()), encoding="utf-8")
        except Exception:
            pass

    def _panel_card(
        self,
        rx: float,
        y: float,
        panel_inner_w: float,
        h: float,
        *,
        border: tuple[float, float, float] = (0.19, 0.20, 0.25),
    ) -> tuple[float, float, float, float]:
        """Draw a right-panel card with consistent padding; return scissor clip box."""
        pad = 8.0
        gl_rect(rx + pad, y, panel_inner_w, h, (0.11, 0.12, 0.15), 1.0)
        gl_rect_border(rx + pad, y, panel_inner_w, h, border, 1.0)
        # clip inset so text never bleeds past card edges
        return (rx + pad + 4.0, y + 4.0, float(panel_inner_w - 8.0), float(h - 8.0))

    def _seed_islands(self, nids: list[str]) -> None:
        """Hierarchical constellations: source galaxy → type rings → hub cores.

        Avoids the filled-disc look. Hubs (Project/Repo) sit near ring center;
        crumbs/comments sit outer. World coords free-float; pan/zoom explores.
        """
        by_src: dict[str, list[str]] = defaultdict(list)
        for nid in nids:
            by_src[str((self.nodes.get(nid) or {}).get("source") or "unknown")].append(nid)
        islands = sorted(by_src.items(), key=lambda x: -len(x[1]))
        n_is = max(1, len(islands))
        ring = 520.0 + 110.0 * math.sqrt(n_is)
        for i, (_src, members) in enumerate(islands):
            a_i = i * 2.399963
            r_i = ring * math.sqrt((i + 0.5) / n_is)
            icx = r_i * math.cos(a_i)
            icy = r_i * math.sin(a_i)
            # type sub-rings inside each source galaxy
            by_type: dict[str, list[str]] = defaultdict(list)
            for nid in members:
                typ = str((self.nodes.get(nid) or {}).get("type") or "Node")
                by_type[typ].append(nid)
            types = sorted(by_type.items(), key=lambda x: -len(x[1]))
            n_t = max(1, len(types))
            for ti, (typ, tmem) in enumerate(types):
                ta = ti * (2.0 * math.pi / n_t) + a_i * 0.15
                # hubs closer to galaxy core
                is_hub = typ in _HUB_TYPES
                tr = (40.0 if is_hub else 95.0) + 55.0 * math.sqrt(ti + 1)
                tcx = icx + tr * math.cos(ta)
                tcy = icy + tr * math.sin(ta)
                # sort: hubs first so they seed inner
                tmem_sorted = sorted(
                    tmem,
                    key=lambda nid: (
                        0 if str((self.nodes.get(nid) or {}).get("type") or "") in _HUB_TYPES else 1,
                        str((self.nodes.get(nid) or {}).get("tier") or "T3"),
                    ),
                )
                for j, nid in enumerate(tmem_sorted):
                    ang = j * 2.399963
                    # inner core for hubs, open spiral for leaves
                    if str((self.nodes.get(nid) or {}).get("type") or "") in _HUB_TYPES:
                        rr = 6.0 + math.sqrt(j) * 4.5
                    else:
                        rr = 18.0 + math.sqrt(j) * 6.8
                    self.pos[nid] = [tcx + rr * math.cos(ang), tcy + rr * math.sin(ang)]
                    self.vel[nid] = [0.0, 0.0]
        self.layout_energy = 1.0
        self.layout_settled = False

    def _rebuild_adj(self) -> None:
        adj: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for e in self.edges:
            s, d, rel = e.get("src"), e.get("dst"), str(e.get("rel") or "RELATED")
            if s and d:
                adj[s].append((d, rel, "out"))
                adj[d].append((s, rel, "in"))
        self.adj = dict(adj)

    def select_node(self, nid: str | None, *, focus: bool = False) -> None:
        if not nid or nid not in self.nodes:
            self.selected = None
            self.trail = []
            return
        self.selected = nid
        self.trail = self._origin_trail(nid)
        self.trail_focus = 0
        self.event_log.appendleft(f"select {nid[:42]} trail={len(self.trail)}")
        if focus:
            self.focus_camera(nid, zoom=max(self.zoom, 1.55))
            self.layout_settled = False  # wake physics near selection

    def _origin_trail(self, nid: str) -> list[str]:
        trail = [nid]
        seen = {nid}
        cur = nid
        for _ in range(16):
            n = self.nodes.get(cur) or {}
            p = n.get("parent_id")
            if p and str(p) not in seen:
                trail.append(str(p))
                seen.add(str(p))
                if str(p) not in self.nodes:
                    break
                cur = str(p)
                continue
            inbound = [(o, r) for o, r, d in (self.adj.get(cur) or []) if d == "in" and o not in seen]
            prefer = [(o, r) for o, r in inbound if r in _ORIGIN] or inbound
            if not prefer:
                break
            o = prefer[0][0]
            trail.append(o)
            seen.add(o)
            cur = o
        return trail

    def walk_trail(self, delta: int) -> None:
        if not self.trail:
            return
        self.trail_focus = max(0, min(len(self.trail) - 1, self.trail_focus + delta))
        nid = self.trail[self.trail_focus]
        if nid in self.nodes:
            self.selected = nid
            self.focus_camera(nid, zoom=max(self.zoom, 1.2))

    def start_path_autoplay(self, ids: list[str] | None = None) -> None:
        """Animate evidence / trail path (GraphRAG show-the-path)."""
        path = [i for i in (ids or self.evidence_ids or self.trail) if i in self.nodes]
        if not path:
            self.path_autoplay = False
            return
        self.trail = path
        self.trail_focus = 0
        self.path_autoplay = True
        self._path_autoplay_t = time.time()
        self.lit_nodes.clear()
        self.lit_edges.clear()
        for i, eid in enumerate(path):
            self.lit_nodes[eid] = 1.0 - i * 0.04
        for a, b in zip(path, path[1:]):
            self.lit_edges.add((a, b) if a < b else (b, a))
        if path[0] in self.nodes:
            self.select_node(path[0], focus=True)
        self.event_log.appendleft(f"path autoplay n={len(path)}")

    def tick_path_autoplay(self) -> None:
        if not self.path_autoplay or not self.trail:
            return
        now = time.time()
        if now - self._path_autoplay_t < 0.85:
            return
        self._path_autoplay_t = now
        if self.trail_focus >= len(self.trail) - 1:
            self.path_autoplay = False
            self.event_log.appendleft("path autoplay done")
            return
        self.walk_trail(+1)

    def _community_color(self, src: str) -> tuple[float, float, float]:
        if src in SOURCE_RGB:
            return SOURCE_RGB[src]
        h = abs(hash(src)) % len(_COMMUNITY_PALETTE)
        return _COMMUNITY_PALETTE[h]

    def _rebuild_community_centers(self) -> None:
        """Soft constellation hulls by source (community look without expensive clustering)."""
        by_src: dict[str, list[str]] = defaultdict(list)
        for nid, n in self.nodes.items():
            if nid not in self.pos:
                continue
            by_src[str(n.get("source") or "unknown")].append(nid)
        centers: dict[str, tuple[float, float, float]] = {}
        for src, members in by_src.items():
            if len(members) < 3:
                continue
            xs = [self.pos[m][0] for m in members if m in self.pos]
            ys = [self.pos[m][1] for m in members if m in self.pos]
            if not xs:
                continue
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            # radius = 85th percentile distance
            dists = sorted(math.hypot(self.pos[m][0] - cx, self.pos[m][1] - cy) for m in members if m in self.pos)
            r = dists[int(len(dists) * 0.85)] if dists else 80.0
            centers[src] = (cx, cy, max(60.0, min(420.0, r * 1.15)))
        self.community_centers = centers

    def _layout_budget(self) -> int:
        """How many nodes to integrate this frame (LOD-scaled)."""
        base = LAYOUT_NODES
        # under load, cut layout hard so draw stays responsive
        return max(80, int(base * self.lod_scale))

    def step_layout(self) -> None:
        """Physics in free world space — settles to idle so CPU is not pegged at 100%.

        Phase A (high energy): full force layout (budgeted).
        Phase B (settled): only micro-breathe + selected neighborhood — ultra-smooth HUD.
        """
        if not self.layout_live:
            return
        # skip frames under load
        if self.lod_scale < 0.55 and (self.tick % 2):
            return
        # settled: sparse micro-breathe only (every 6th frame) — frees CPU for HUD
        if self.layout_settled and (self.tick % 6):
            return

        all_ids = [i for i, n in self.nodes.items() if self.visible(n) and i in self.pos]
        budget = self._layout_budget()
        if self.layout_settled:
            budget = min(budget, 48)
            # Prefer selected neighborhood when settled
            if self.selected and self.selected in self.pos:
                neigh_ids = [self.selected]
                for a, b, _ in (self.adj.get(self.selected) or [])[:24]:
                    other = b if a == self.selected else a
                    if other in self.pos:
                        neigh_ids.append(other)
                ids = neigh_ids[:budget]
            else:
                # tiny rotating sample — breathe, don't thrash
                start = (self.tick * 12) % max(1, len(all_ids))
                ids = all_ids[start : start + budget]
        elif len(all_ids) > budget:
            start = (self.tick * (budget // 2)) % max(1, len(all_ids))
            ids = all_ids[start : start + budget]
            if len(ids) < budget:
                ids = ids + all_ids[: budget - len(ids)]
        else:
            ids = all_ids

        energy = 0.0
        neigh = 3 if self.layout_settled else (8 if self.lod_scale > 0.7 else 5)
        for i, a in enumerate(ids):
            sa = str((self.nodes.get(a) or {}).get("source") or "")
            for b in ids[i + 1 : i + 1 + neigh]:
                ax, ay = self.pos[a]
                bx, by = self.pos[b]
                dx, dy = ax - bx, ay - by
                dist2 = dx * dx + dy * dy + 0.01
                dist = math.sqrt(dist2)
                sb = str((self.nodes.get(b) or {}).get("source") or "")
                k = 380.0 if sa != sb else 120.0
                force = k / dist2
                self.vel[a][0] += force * dx / dist
                self.vel[a][1] += force * dy / dist
                self.vel[b][0] -= force * dx / dist
                self.vel[b][1] -= force * dy / dist

        spring_n = max(20, int(LAYOUT_EDGE_SPRINGS * self.lod_scale * (0.18 if self.layout_settled else 1.0)))
        id_set = set(ids)
        springs = 0
        for e in self.edges:
            if springs >= spring_n:
                break
            s, d = e.get("src"), e.get("dst")
            if s not in self.pos or d not in self.pos:
                continue
            if s not in id_set and d not in id_set:
                continue
            ax, ay = self.pos[s]
            bx, by = self.pos[d]
            dx, dy = bx - ax, by - ay
            dist = math.sqrt(dx * dx + dy * dy) + 0.01
            sa = str((self.nodes.get(s) or {}).get("source") or "")
            sb = str((self.nodes.get(d) or {}).get("source") or "")
            # same-type springs tighter than just same-source
            ta = str((self.nodes.get(s) or {}).get("type") or "")
            tb = str((self.nodes.get(d) or {}).get("type") or "")
            if sa == sb and ta == tb:
                ideal, strength = 36.0, 0.016
            elif sa == sb:
                ideal, strength = 52.0, 0.011
            else:
                ideal, strength = 170.0, 0.0018
            force = (dist - ideal) * strength
            self.vel[s][0] += force * dx / dist
            self.vel[s][1] += force * dy / dist
            self.vel[d][0] -= force * dx / dist
            self.vel[d][1] -= force * dy / dist
            springs += 1

        t = self.tick * 0.01
        breath = 0.0022 if self.layout_settled else 0.012
        damp = 0.86 if not self.layout_settled else 0.82
        for nid in ids:
            px, py = self.pos[nid]
            # soft gravity only during active settle
            if not self.layout_settled:
                self.vel[nid][0] += -px * 0.00012
                self.vel[nid][1] += -py * 0.00012
            self.vel[nid][0] *= damp
            self.vel[nid][1] *= damp
            self.vel[nid][0] += breath * math.sin(t + (hash(nid) % 97))
            self.vel[nid][1] += breath * math.cos(t * 0.9 + (hash(nid) % 53))
            self.pos[nid][0] += self.vel[nid][0]
            self.pos[nid][1] += self.vel[nid][1]
            energy += abs(self.vel[nid][0]) + abs(self.vel[nid][1])

        # EMA energy → auto-settle (ultra apps idle their physics)
        n_e = max(1, len(ids))
        inst = energy / n_e
        prev_e = self.layout_energy
        self.layout_energy = 0.9 * self.layout_energy + 0.1 * inst
        # Peak-relative settle: after warm-up, if energy is low OR has plateaued
        if not hasattr(self, "_layout_peak"):
            self._layout_peak = 1.0
            self._settle_stable = 0
        if self.layout_energy > self._layout_peak:
            self._layout_peak = self.layout_energy
        delta = abs(self.layout_energy - prev_e)
        if not self.layout_settled and self.tick > 100:
            low = self.layout_energy < 0.35
            cooled = self.layout_energy < max(0.4, 0.25 * self._layout_peak)
            plateau = delta < 0.012 and self.layout_energy < 0.8
            if low or cooled or plateau:
                self._settle_stable += 1
            else:
                self._settle_stable = max(0, self._settle_stable - 1)
            if self._settle_stable > 25 or (self.tick > 360 and self.layout_energy < 1.2):
                self.layout_settled = True
                self._settle_stable = 0
                self.event_log.appendleft("layout settled · micro-breathe")
        elif self.layout_settled:
            # re-awaken only on real disturbance (selection/reseed already set False)
            if self.layout_energy > max(1.2, 0.55 * self._layout_peak):
                self.layout_settled = False
                self._layout_peak = max(self._layout_peak, self.layout_energy)

    def note_frame(self) -> None:
        """Record frame time and auto-degrade draw/layout budget when lagging."""
        now = time.perf_counter()
        dt = max(0.0001, now - self._frame_t0)
        self._frame_t0 = now
        self.frame_ms = dt * 1000.0
        # Exclude vsync/sleep from stutter detection: clock.tick pads to 60fps (~16ms).
        # Use work-only estimate via previous draw+layout window when available.
        inst_fps = 1.0 / dt
        self._fps_ema = 0.88 * self._fps_ema + 0.12 * inst_fps
        self.fps = self._fps_ema
        # Adaptive LOD uses work ms if set, else frame_ms. Recover when smooth.
        work_ms = getattr(self, "_work_ms", self.frame_ms)
        if work_ms > TARGET_FRAME_MS * 1.8:
            self.lod_scale = max(0.30, self.lod_scale * 0.88)
            self.perf_warn = f"LOD↓ work={work_ms:.0f}ms fps={self.fps:.0f}"
        elif work_ms > TARGET_FRAME_MS * 1.15:
            self.lod_scale = max(0.40, self.lod_scale * 0.96)
            self.perf_warn = f"LOD throttle work={work_ms:.0f}ms"
        elif work_ms < TARGET_FRAME_MS * 0.85 and self.lod_scale < 1.0:
            # recover toward full budget when work is comfortable
            self.lod_scale = min(1.0, self.lod_scale + 0.04)
            self.perf_warn = ""
        else:
            if self.fps >= 40 and work_ms <= TARGET_FRAME_MS:
                self.perf_warn = ""
        # hard tripwire for error suite / ops (true stutter, not vsync pad)
        if self.fps < 22 and self.tick > 45 and work_ms > 40:
            self.perf_warn = f"STUTTER fps={self.fps:.0f} work={work_ms:.0f}ms n={len(self.nodes)}"

    def draw_budgets(self) -> tuple[int, int]:
        """Per-frame node/edge draw caps under LOD."""
        n_cap = max(400, int(DRAW_NODES * self.lod_scale))
        e_cap = max(300, int(DRAW_EDGES * self.lod_scale))
        # zoomed far out → fewer edges (hairball becomes solid gray sludge)
        if self.zoom < 0.4:
            e_cap = min(e_cap, 800)
            n_cap = min(n_cap, 2000)
        elif self.zoom < 0.7:
            e_cap = min(e_cap, 2200)
        return n_cap, e_cap

    def decay_lit(self) -> None:
        dead = [k for k, v in self.lit_nodes.items() if v * 0.97 < 0.04]
        for k in list(self.lit_nodes):
            self.lit_nodes[k] *= 0.97
        for k in dead:
            del self.lit_nodes[k]
        if not self.lit_nodes:
            self.lit_edges.clear()

    def health(self) -> tuple[str, tuple[float, float, float], str]:
        fails = sum(1 for s in STAGE_ORDER if self.stage_status.get(s) == "fail")
        runs = sum(1 for s in STAGE_ORDER if self.stage_status.get(s) == "running")
        oks = sum(1 for s in STAGE_ORDER if self.stage_status.get(s) == "ok")
        if fails:
            return "UNHEALTHY", (0.90, 0.30, 0.24), f"{fails} stage(s) FAIL"
        if runs:
            return "CAUTION", (0.95, 0.77, 0.06), f"{runs} stage(s) running"
        if oks:
            return "HEALTHY", (0.18, 0.80, 0.44), f"{oks}/{len(STAGE_ORDER)} stages OK"
        return "IDLE", (0.45, 0.47, 0.50), "No concert yet — ask a question"

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        gx, gy, gw, gh = self.graph_rect()
        cx, cy = gx + gw / 2, gy + gh / 2
        wx = (sx - cx) / self.zoom + cx - self.pan[0]
        wy = (sy - cy) / self.zoom + cy - self.pan[1]
        return wx, wy

    def hit_test(self, sx: int, sy: int) -> str | None:
        """Hit-test ALL loaded (visible) nodes — not just the draw-cap subset."""
        gx, gy, gw, gh = self.graph_rect()
        if not (gx <= sx <= gx + gw and gy <= sy <= gy + gh):
            return None
        wx, wy = self.screen_to_world(sx, sy)
        # hit radius grows when zoomed out so sparse clicks still land
        best, best_d = None, max(10.0, 14.0 / max(0.25, self.zoom))
        for nid, n in self.nodes.items():
            if not self.visible(n) or nid not in self.pos:
                continue
            px, py = self.pos[nid]
            d = math.hypot(px - wx, py - wy)
            if d < best_d:
                best, best_d = nid, d
        return best

    def node_label(self, nid: str, max_chars: int = 36) -> str:
        cached = self._hover_title_cache.get(nid)
        if cached is not None and max_chars >= 36:
            return cached[:max_chars]
        n = self.nodes.get(nid) or {}
        title = str(n.get("title") or n.get("name") or n.get("id") or nid).replace("\n", " ")
        title = title.strip() or str(nid)
        if len(title) > max_chars:
            title = title[: max_chars - 1] + "…"
        if max_chars >= 36:
            self._hover_title_cache[nid] = title
        return title

    def focus_camera(self, nid: str | None = None, zoom: float | None = None) -> None:
        """Smooth-pan camera to node (or graph centroid)."""
        gx, gy, gw, gh = self.graph_rect()
        if nid and nid in self.pos:
            cx, cy = self.pos[nid]
            z = zoom if zoom is not None else max(self.zoom, 1.35)
        elif self.pos:
            xs = [p[0] for p in self.pos.values()]
            ys = [p[1] for p in self.pos.values()]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            span = max(max(xs) - min(xs), max(ys) - min(ys), 200.0)
            z = zoom if zoom is not None else max(0.12, min(1.8, 0.75 * min(gw, gh) / span))
        else:
            return
        self.cam_target = [
            (gx + gw / 2) - cx,
            (gy + gh / 2) - cy,
            float(z),
        ]

    def update_camera(self) -> None:
        if not self.cam_target:
            return
        tx, ty, tz = self.cam_target
        self.pan[0] += (tx - self.pan[0]) * 0.16
        self.pan[1] += (ty - self.pan[1]) * 0.16
        self.zoom += (tz - self.zoom) * 0.14
        if abs(self.pan[0] - tx) < 0.4 and abs(self.pan[1] - ty) < 0.4 and abs(self.zoom - tz) < 0.008:
            self.pan[0], self.pan[1] = tx, ty
            self.zoom = tz
            self.cam_target = None

    def ensure_starfield(self, n: int = 180) -> None:
        """Subtle dust behind the constellation (panel-local NDC-ish)."""
        if len(self._stars) >= n:
            return
        rng = random.Random(0xC0DE5EED)
        self._stars = [
            (rng.random(), rng.random(), 0.22 + 0.58 * rng.random())
            for _ in range(n)
        ]

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        gx, gy, gw, gh = self.graph_rect()
        cx, cy = gx + gw / 2, gy + gh / 2
        sx = (wx - (cx - self.pan[0])) * self.zoom + cx
        sy = (wy - (cy - self.pan[1])) * self.zoom + cy
        return sx, sy

    def setup_gl(self) -> None:
        glViewport(0, 0, self.w, self.h)
        # deep slate — premium ops dark (not pure black)
        glClearColor(0.035, 0.040, 0.055, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_POINT_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glHint(GL_POINT_SMOOTH_HINT, GL_NICEST)
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.w, self.h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        self.texts.set_screen(self.h)
        # Capture real GPU identity (Apple Metal / NVIDIA / Intel)
        if not self.gpu_renderer:
            try:
                from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER, GL_VERSION

                def _dec(v: Any) -> str:
                    if v is None:
                        return ""
                    return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)

                self.gpu_vendor = _dec(glGetString(GL_VENDOR))
                self.gpu_renderer = _dec(glGetString(GL_RENDERER))
                self.gpu_version = _dec(glGetString(GL_VERSION))
                # Classify path for HUD
                rlow = (self.gpu_renderer + " " + self.gpu_vendor).lower()
                if "nvidia" in rlow:
                    self.gpu_path = "nvidia_gl" + ("+vbo" if self._has_vbo else "+va")
                elif "apple" in rlow or "metal" in rlow:
                    self.gpu_path = "apple_metal_gl" + ("+vbo" if self._has_vbo else "+va")
                elif "amd" in rlow or "ati" in rlow:
                    self.gpu_path = "amd_gl+va"
                elif "intel" in rlow:
                    self.gpu_path = "intel_gl+va"
                else:
                    self.gpu_path = "gl+va"
                if self._np is None:
                    self.gpu_path += "+no_numpy"
            except Exception:
                pass

    def resize(self, w: int, h: int) -> None:
        self.w, self.h = max(960, w), max(640, h)
        self.setup_gl()

    def _draw_arrays_lines(self, verts: Any, colors: Any, n_verts: int, width: float) -> None:
        """GPU batch lines via client vertex arrays → glDrawArrays (not glBegin spam).

        On Apple M1 this hits Metal. On Corporate NVIDIA laptops this hits the NVIDIA GL driver.
        CUDA is separate (compute) — visualization uses OpenGL/DirectX, not CUDA kernels.
        """
        if n_verts < 2 or self._np is None:
            return
        v = self._np.ascontiguousarray(verts, dtype=self._np.float32).reshape(-1)
        c = self._np.ascontiguousarray(colors, dtype=self._np.float32).reshape(-1)
        glLineWidth(width)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        try:
            glVertexPointer(2, GL_FLOAT, 0, v)
            glColorPointer(4, GL_FLOAT, 0, c)
            glDrawArrays(GL_LINES, 0, int(n_verts))
        finally:
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)

    def _draw_arrays_points(self, verts: Any, colors: Any, n_verts: int, size: float) -> None:
        if n_verts < 1 or self._np is None:
            return
        v = self._np.ascontiguousarray(verts, dtype=self._np.float32).reshape(-1)
        c = self._np.ascontiguousarray(colors, dtype=self._np.float32).reshape(-1)
        glPointSize(float(size))
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        try:
            glVertexPointer(2, GL_FLOAT, 0, v)
            glColorPointer(4, GL_FLOAT, 0, c)
            glDrawArrays(GL_POINTS, 0, int(n_verts))
        finally:
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)

    def _draw_vignette(self, gx: float, gy: float, gw: float, gh: float) -> None:
        """Soft edge darken so the constellation reads as a stage, not a flat slab."""
        # four edge fades
        fade = 0.22
        gl_rect(gx, gy, gw, 28, (0.02, 0.025, 0.04), fade)
        gl_rect(gx, gy + gh - 28, gw, 28, (0.02, 0.025, 0.04), fade)
        gl_rect(gx, gy, 36, gh, (0.02, 0.025, 0.04), fade * 0.85)
        gl_rect(gx + gw - 36, gy, 36, gh, (0.02, 0.025, 0.04), fade * 0.85)

    def _draw_soft_disc(
        self,
        cx: float,
        cy: float,
        radius: float,
        rgb: tuple[float, float, float],
        alpha: float,
        *,
        segments: int = 28,
    ) -> None:
        """Filled circle (not a square) — soft community glow without box artifacts."""
        if radius < 1.0 or alpha <= 0.0:
            return
        glColor4f(rgb[0], rgb[1], rgb[2], alpha)
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(cx, cy)
        for i in range(segments + 1):
            a = (i / segments) * math.tau
            glVertex2f(cx + math.cos(a) * radius, cy + math.sin(a) * radius)
        glEnd()

    def _draw_community_hulls(self, gx: float, gy: float, gw: float, gh: float) -> None:
        """Soft translucent discs under source islands — galaxy constellation look."""
        if not self.community_centers or self.lod_scale < 0.4:
            return
        # world → screen
        for src, (cx, cy, r) in list(self.community_centers.items())[:12]:
            sx = gx + gw / 2 + (cx + self.pan[0]) * self.zoom
            sy = gy + gh / 2 + (cy + self.pan[1]) * self.zoom
            sr = max(12.0, r * self.zoom)
            if sx + sr < gx or sx - sr > gx + gw or sy + sr < gy or sy - sr > gy + gh:
                continue
            rgb = self._community_color(src)
            # concentric soft discs (never axis-aligned squares)
            for scale, alpha in ((1.0, 0.05), (0.72, 0.07), (0.45, 0.10)):
                self._draw_soft_disc(sx, sy, sr * scale, rgb, alpha)

    def _draw_starfield(self, gx: float, gy: float, gw: float, gh: float) -> None:
        """Subtle star dust inside the graph panel (screen space, pre-world transform)."""
        self.ensure_starfield(180)
        # slow drift + soft twinkle so the stage feels alive without cost
        drift = (self.tick * 0.00035) % 1.0
        tw = 0.5 + 0.5 * math.sin(self.tick * 0.035)
        verts: list[float] = []
        cols: list[float] = []
        for i, (ux, uy, br) in enumerate(self._stars):
            x = gx + ((ux + drift * 0.08) % 1.0) * gw
            y = gy + ((uy + drift * 0.04) % 1.0) * gh
            phase = 0.85 + 0.15 * math.sin(self.tick * 0.05 + i * 0.37)
            a = (0.08 + 0.26 * br) * (0.75 + 0.25 * tw * phase)
            verts.extend((x, y))
            cols.extend((0.55 + 0.25 * br, 0.62 + 0.2 * br, 0.80, a))
        if self._np is not None and verts:
            self._draw_arrays_points(verts, cols, len(self._stars), 1.55)
        else:
            glPointSize(1.5)
            glBegin(GL_POINTS)
            for i in range(0, len(verts), 2):
                c = i * 2
                glColor4f(cols[c], cols[c + 1], cols[c + 2], cols[c + 3])
                glVertex2f(verts[i], verts[i + 1])
            glEnd()

    def _draw_minimap(self, gx: float, gy: float, gw: float, gh: float) -> None:
        """Bottom-left constellation overview with camera frustum."""
        if not self.show_minimap or not self.pos:
            return
        mw, mh = 148.0, 108.0
        mx = gx + 10.0
        my = gy + gh - mh - 14.0
        # panel glass
        gl_rect(mx, my, mw, mh, (0.04, 0.05, 0.07), 0.82)
        gl_rect_border(mx, my, mw, mh, (0.28, 0.40, 0.55), 0.75)
        # world bounds from loaded positions
        xs = [p[0] for p in self.pos.values()]
        ys = [p[1] for p in self.pos.values()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        span = max(maxx - minx, maxy - miny, 80.0)
        pad = span * 0.08
        minx -= pad
        miny -= pad
        span = max(maxx - minx + pad, maxy - miny + pad, 80.0)
        # subsample points for cheap minimap
        step = max(1, len(self.pos) // 420)
        verts: list[float] = []
        cols: list[float] = []
        i = 0
        for nid, p in self.pos.items():
            i += 1
            if i % step:
                continue
            n = self.nodes.get(nid) or {}
            if not self.visible(n):
                continue
            u = (p[0] - minx) / span
            v = (p[1] - miny) / span
            if u < 0 or u > 1 or v < 0 or v > 1:
                continue
            px = mx + 4 + u * (mw - 8)
            py = my + 4 + v * (mh - 8)
            verts.extend((px, py))
            rgb = SOURCE_RGB.get(
                str(n.get("source") or ""),
                (0.45, 0.48, 0.55),
            )
            cols.extend((rgb[0], rgb[1], rgb[2], 0.85))
        if verts and self._np is not None:
            self._draw_arrays_points(verts, cols, len(verts) // 2, 2.0)
        # camera viewport rect in world → minimap
        corners = [
            self.screen_to_world(gx, gy),
            self.screen_to_world(gx + gw, gy),
            self.screen_to_world(gx + gw, gy + gh),
            self.screen_to_world(gx, gy + gh),
        ]
        mpts = []
        for wx, wy in corners:
            u = (wx - minx) / span
            v = (wy - miny) / span
            mpts.append((mx + 4 + u * (mw - 8), my + 4 + v * (mh - 8)))
        glColor4f(0.35, 0.85, 1.0, 0.55)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for a, b in zip(mpts, mpts[1:] + mpts[:1]):
            glVertex2f(a[0], a[1])
            glVertex2f(b[0], b[1])
        glEnd()
        # selected pin
        if self.selected and self.selected in self.pos:
            p = self.pos[self.selected]
            u = (p[0] - minx) / span
            v = (p[1] - miny) / span
            if 0 <= u <= 1 and 0 <= v <= 1:
                self._draw_arrays_points(
                    [mx + 4 + u * (mw - 8), my + 4 + v * (mh - 8)],
                    [0.2, 1.0, 0.5, 1.0],
                    1,
                    5.0,
                )

    def _label_candidates(self) -> list[str]:
        """Selected + hover + trail + neighbors + hubs when zoomed in."""
        if self.zoom < 0.95:
            return []
        out: list[str] = []
        seen: set[str] = set()

        def add(nid: str | None) -> None:
            if not nid or nid in seen or nid not in self.pos:
                return
            n = self.nodes.get(nid)
            if not n or not self.visible(n):
                return
            seen.add(nid)
            out.append(nid)

        add(self.selected)
        add(self.hover_id)
        for nid in self.trail[:8]:
            add(nid)
        if self.selected:
            for a, b, _ in (self.adj.get(self.selected) or [])[:14]:
                other = b if a == self.selected else a
                add(other)
        # hubs when reasonably zoomed
        if self.zoom >= 1.15:
            hub_n = 0
            for nid, n in self.nodes.items():
                if hub_n >= 18:
                    break
                if str(n.get("type") or "") in _HUB_TYPES:
                    add(nid)
                    hub_n += 1
        return out[:36]

    def _draw_node_labels(self, font_sm, gx: float, gy: float, gw: float, gh: float) -> None:
        """Screen-space labels for selected / neighbors / hubs when zoomed in."""
        ids = self._label_candidates()
        if not ids:
            return
        gclip = (gx + 2, gy + 2, gw - 4, gh - 4)
        for nid in ids:
            px, py = self.pos[nid]
            sx, sy = self.world_to_screen(px, py)
            if sx < gx or sx > gx + gw or sy < gy or sy > gy + gh:
                continue
            label = self.node_label(nid, 28 if nid != self.selected else 40)
            if not label:
                continue
            col = (230, 245, 255) if nid == self.selected else (170, 185, 205)
            # soft plate behind label so stars don't fight glyphs
            tw_est = min(int(gw * 0.35), max(40, len(label) * 7 + 8))
            lx = sx + 8
            ly = sy - 6
            if lx + tw_est > gx + gw - 4:
                lx = sx - tw_est - 4
            gl_rect(lx - 2, ly - 1, tw_est, 14, (0.05, 0.06, 0.09), 0.72)
            self.texts.draw(font_sm, label, lx, ly, col, max_w=tw_est - 2, clip=gclip)

    def _draw_hover_tooltip(self, font, font_sm, gx: float, gy: float, gw: float, gh: float) -> None:
        """Cursor-following node identity card (never leaves graph panel)."""
        hid = self.hover_id
        if not hid or hid not in self.nodes:
            return
        n = self.nodes[hid]
        mx, my = self.mouse_xy
        # keep tooltip inside graph panel
        tw, th = min(320.0, gw - 20), 52.0
        tx = min(max(gx + 8, mx + 14), gx + gw - tw - 8)
        ty = min(max(gy + 8, my + 16), gy + gh - th - 8)
        gl_rect(tx, ty, tw, th, (0.08, 0.09, 0.12), 0.94)
        gl_rect_border(tx, ty, tw, th, (0.35, 0.55, 0.85), 0.9)
        tclip = (tx + 4, ty + 2, tw - 8, th - 4)
        title = self.node_label(hid, 42)
        self.texts.draw(font, title, tx + 10, ty + 8, (230, 235, 245), max_w=int(tw - 20), clip=tclip)
        meta = f"{n.get('type') or '?'} · {n.get('source') or '?'} · {n.get('tier') or '?'}"
        self.texts.draw(font_sm, meta, tx + 10, ty + 30, (140, 155, 175), max_w=int(tw - 20), clip=tclip)

    def _node_point_size(self, n: dict[str, Any], lit: float, selected: bool) -> float:
        """Tier-aware sizes: T0/T1 bigger, crumbs smaller — reduces snowstorm."""
        typ = str(n.get("type") or "")
        tier = str(n.get("tier") or "T3")
        base = 4.2
        if typ in _CHUNK or typ.endswith("Crumb") or typ.endswith("Tag"):
            base = 2.6
        elif tier == "T0":
            base = 7.5
        elif tier == "T1":
            base = 6.2
        elif tier == "T2":
            base = 4.8
        if selected:
            base *= 1.55
        elif lit > 0.05:
            base *= 1.0 + 0.35 * lit
        return max(2.0, base * min(2.2, self.zoom * 0.9 + 0.35))

    def draw(self, font, font_sm, font_title) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        gx, gy, gw, gh = self.graph_rect()
        # Hard-scissor entire graph surface so nothing bleeds into Inspector / window edge
        glEnable(GL_SCISSOR_TEST)
        glScissor(
            max(0, int(gx)),
            max(0, int(self.h - (gy + gh))),
            max(1, int(gw)),
            max(1, int(gh)),
        )
        # Full-bleed canvas (no nested "graph box")
        gl_rect(gx, gy, gw, gh, (0.04, 0.045, 0.06), 1.0)
        self._draw_starfield(gx, gy, gw, gh)
        if self.layout_settled or (self.tick % 45 == 0) or not self.community_centers:
            try:
                self._rebuild_community_centers()
            except Exception:
                pass
        try:
            self._draw_community_hulls(gx, gy, gw, gh)
        except Exception:
            pass
        self._draw_vignette(gx, gy, gw, gh)

        # ── GL graph (world transform) ──
        cx, cy = gx + gw / 2, gy + gh / 2
        glTranslatef(cx, cy, 0)
        glScalef(self.zoom, self.zoom, 1)
        glTranslatef(-cx + self.pan[0], -cy + self.pan[1], 0)

        trail_set = set(self.trail)
        trail_pairs: set[tuple[str, str]] = set()
        for i in range(1, len(self.trail)):
            a, b = self.trail[i - 1], self.trail[i]
            trail_pairs.add((a, b) if a < b else (b, a))

        n_cap, e_cap = self.draw_budgets()

        # ── GPU-batched edges (vertex arrays — not glBegin per edge) ──
        def _collect_edges(only_hot: bool, cap: int) -> tuple[list[float], list[float], int]:
            verts: list[float] = []
            cols: list[float] = []
            drawn = 0
            for e in self.edges:
                if drawn >= cap:
                    break
                s, d = e.get("src"), e.get("dst")
                if s not in self.pos or d not in self.pos:
                    continue
                if s not in self.nodes or d not in self.nodes:
                    continue
                if not self.visible(self.nodes[s]) or not self.visible(self.nodes[d]):
                    continue
                pair = (s, d) if s < d else (d, s)
                hot = pair in trail_pairs or pair in self.lit_edges
                if only_hot and not hot:
                    continue
                if not only_hot and hot:
                    continue
                sa = str((self.nodes.get(s) or {}).get("source") or "")
                sb = str((self.nodes.get(d) or {}).get("source") or "")
                cross = sa != sb
                if not only_hot and cross and self.lod_scale < 0.7:
                    continue
                if pair in trail_pairs:
                    rgba = (0.25, 0.95, 0.55, 0.90)
                elif pair in self.lit_edges:
                    rgba = (0.35, 0.78, 1.0, 0.88)
                elif cross:
                    rgba = (0.16, 0.18, 0.24, 0.10)
                elif self.trail or self.lit_nodes:
                    rgba = (0.20, 0.23, 0.30, 0.16)
                else:
                    rgba = (0.24, 0.30, 0.40, 0.20)
                px, py = self.pos[s]
                qx, qy = self.pos[d]
                verts.extend((px, py, qx, qy))
                cols.extend((*rgba, *rgba))
                drawn += 1
            return verts, cols, drawn

        hot_v, hot_c, hot_n = _collect_edges(True, min(400, e_cap))
        if hot_n:
            self._draw_arrays_lines(hot_v, hot_c, hot_n * 2, 2.5)
        base_v, base_c, base_n = _collect_edges(False, e_cap)
        if base_n:
            self._draw_arrays_lines(base_v, base_c, base_n * 2, 1.0)
        self.drawn_edges = hot_n + base_n

        # ── GPU-batched nodes by size bucket ──
        cold_bins: list[list[tuple[str, dict, float]]] = [[], [], []]
        hot_nodes: list[tuple[str, dict, float, float, bool]] = []
        n_scanned = 0
        for nid, n in self.nodes.items():
            if n_scanned >= n_cap:
                break
            if not self.visible(n) or nid not in self.pos:
                continue
            n_scanned += 1
            lit = self.lit_nodes.get(nid, 0.0)
            sel = nid == self.selected or (bool(self.trail) and self.trail[self.trail_focus] == nid)
            sz = self._node_point_size(n, lit, sel)
            if sel or lit > 0.05 or nid in trail_set:
                hot_nodes.append((nid, n, sz, lit, sel))
            else:
                if sz < 3.5:
                    cold_bins[0].append((nid, n, sz))
                elif sz < 6.0:
                    cold_bins[1].append((nid, n, sz))
                else:
                    cold_bins[2].append((nid, n, sz))

        for b in cold_bins:
            if not b:
                continue
            avg_sz = sum(x[2] for x in b) / len(b)
            verts: list[float] = []
            cols: list[float] = []
            for nid, n, _sz in b:
                px, py = self.pos[nid]
                verts.extend((px, py))
                rgb = SOURCE_RGB.get(
                    str(n.get("source") or ""),
                    TIER_RGB.get(str(n.get("tier") or "T3"), (0.55, 0.58, 0.62)),
                )
                cols.extend((rgb[0], rgb[1], rgb[2], 0.92))
            self._draw_arrays_points(verts, cols, len(b), avg_sz)

        # hot / selected still small N — VA batch glow then core
        if hot_nodes:
            g_verts: list[float] = []
            g_cols: list[float] = []
            c_verts: list[float] = []
            c_cols: list[float] = []
            avg_glow = 0.0
            avg_core = 0.0
            for nid, n, sz, lit, sel in hot_nodes:
                px, py = self.pos[nid]
                g_verts.extend((px, py))
                c_verts.extend((px, py))
                avg_glow += sz * 2.0
                avg_core += sz
                if sel:
                    g_cols.extend((0.2, 1.0, 0.5, 0.22))
                    c_cols.extend((0.35, 1.0, 0.55, 1.0))
                elif nid in trail_set:
                    g_cols.extend((0.3, 0.9, 0.5, 0.18))
                    c_cols.extend((0.40, 0.95, 0.60, 0.95))
                else:
                    g_cols.extend((0.3, 0.7, 1.0, 0.16 * lit))
                    c_cols.extend((0.35 + 0.45 * lit, 0.75 + 0.2 * lit, 1.0, 0.96))
            n_hot = len(hot_nodes)
            self._draw_arrays_points(g_verts, g_cols, n_hot, max(4.0, avg_glow / n_hot))
            self._draw_arrays_points(c_verts, c_cols, n_hot, max(3.0, avg_core / n_hot))

        self.drawn_nodes = sum(len(b) for b in cold_bins) + len(hot_nodes)

        if self.selected and self.selected in self.pos:
            px, py = self.pos[self.selected]
            self._draw_arrays_points([px, py], [1, 1, 1, 0.35], 1, 18.0)
            self._draw_arrays_points([px, py], [1, 1, 1, 0.95], 1, 9.0)
        if self.hover_id and self.hover_id in self.pos and self.hover_id != self.selected:
            hx, hy = self.pos[self.hover_id]
            self._draw_arrays_points([hx, hy], [0.55, 0.75, 1.0, 0.28], 1, 14.0)
            self._draw_arrays_points([hx, hy], [0.75, 0.88, 1.0, 0.9], 1, 7.0)

        # ── HUD screen space ──
        glLoadIdentity()
        self.texts.set_screen(self.h)
        lab, hcol, why = self.health()
        if self.layout_live and self.layout_settled:
            motion = "SETTLED"
        elif self.layout_live:
            motion = "LIVE"
        else:
            motion = "FROZEN"
        vec_n = self.vector_stats.get("vectors", 0)

        # Labels / tooltip / minimap stay inside graph scissor (no bleed into Inspector)
        self._draw_node_labels(font_sm, gx, gy, gw, gh)
        self._draw_hover_tooltip(font, font_sm, gx, gy, gw, gh)
        if self.show_minimap:
            self._draw_minimap(gx, gy, gw, gh)

        # Selection: one floating sheet (Apple card), not a permanent full-width bar
        if self.selected and self.selected in self.nodes:
            n = self.nodes[self.selected]
            sheet_w = min(420.0, max(220.0, gw * 0.42))
            sheet_h = 58.0
            sheet_x = gx + (gw - sheet_w) / 2.0
            sheet_y = gy + gh - sheet_h - 20.0
            # keep clear of minimap corner
            if self.show_minimap and sheet_x < gx + 170:
                sheet_x = gx + 170
                sheet_w = min(sheet_w, gx + gw - sheet_x - 12)
            sheet_x, sheet_y, sheet_w, sheet_h = self._clip_box(sheet_x, sheet_y, sheet_w, sheet_h)
            gl_rect(sheet_x, sheet_y, sheet_w, sheet_h, (0.09, 0.10, 0.13), 0.94)
            gl_rect_border(sheet_x, sheet_y, sheet_w, sheet_h, (0.22, 0.78, 0.48), 0.95)
            sclip = self._clip_box(sheet_x + 6, sheet_y + 4, sheet_w - 12, sheet_h - 8)
            title = str(n.get("title") or n.get("id") or "")
            self.texts.draw(
                font,
                title,
                sheet_x + 12,
                sheet_y + 10,
                (236, 240, 248),
                max_w=int(sheet_w - 24),
                clip=sclip,
            )
            meta = f"{n.get('type') or '—'} · {n.get('source') or '—'} · {n.get('tier') or '—'}"
            self.texts.draw(
                font_sm,
                meta,
                sheet_x + 12,
                sheet_y + 34,
                (150, 156, 170),
                max_w=int(sheet_w - 24),
                clip=sclip,
            )

        glDisable(GL_SCISSOR_TEST)

        # ── SIMPLE CHROME: health pill + quiet hint (no dashboard boxes) ──
        pill_w = 148.0
        pill_h = 30.0
        pill_x, pill_y = 14.0, 14.0
        pill_x, pill_y, pill_w, pill_h = self._clip_box(pill_x, pill_y, pill_w, pill_h)
        gl_rect(pill_x, pill_y, pill_w, pill_h, (0.07, 0.08, 0.11), 0.88)
        gl_rect_border(pill_x, pill_y, pill_w, pill_h, hcol, 0.9)
        # status dot
        gl_rect(pill_x + 10, pill_y + 10, 10, 10, hcol, 1.0)
        pclip = self._clip_box(pill_x + 28, pill_y + 2, pill_w - 36, pill_h - 4)
        self.texts.draw(
            font,
            lab.title() if lab else "Ready",
            pill_x + 28,
            pill_y + 7,
            tuple(int(c * 255) for c in hcol),
            max_w=int(pill_w - 40),
            clip=pclip,
        )

        # Quiet top-right affordance (Inspector)
        hint = "I details" if not self.show_inspector else "I close"
        hint_w = 88.0
        hint_x = (gx + gw - hint_w - 14.0) if not self.show_inspector else (self.w - RIGHT_W - hint_w - 20.0)
        if self.show_inspector:
            hint_x = max(14.0, float(self.w - RIGHT_W - 12) - hint_w - 8.0)
        hint_x, hint_y, hint_w, hint_h = self._clip_box(hint_x, 18.0, hint_w, 22.0)
        hclip_hint = self._clip_box(hint_x, hint_y, hint_w, hint_h)
        self.texts.draw(
            font_sm,
            hint,
            hint_x,
            hint_y + 4,
            (110, 120, 140),
            max_w=int(hint_w),
            clip=hclip_hint,
        )

        # Perf warn only (no always-on metric soup)
        if self.perf_warn:
            wclip = self._clip_box(14.0, 50.0, min(400.0, gw - 28), 20.0)
            self.texts.draw(
                font_sm,
                f"⚠ {self.perf_warn}",
                16,
                52,
                (230, 140, 90),
                max_w=int(wclip[2]),
                clip=wclip,
            )

        # ── INSPECTOR (I) — full ops rail; hard-scissored; never bleeds ──
        if self.show_inspector:
            rx = float(self.w - RIGHT_W)
            ry = 0.0
            rh = float(self.h)
            panel_inner_w = RIGHT_W - 16
            text_left = rx + 16
            text_max = int(panel_inner_w - 20)
            # clamp to window
            rx, ry, rpw, rh = self._clip_box(rx, ry, float(RIGHT_W), rh)
            gl_rect(rx, ry, rpw, rh, (0.086, 0.094, 0.118), 1.0)
            gl_rect_border(rx, ry, rpw, rh, (0.19, 0.20, 0.25), 1.0)
            glEnable(GL_SCISSOR_TEST)
            glScissor(
                max(0, int(rx)),
                max(0, int(self.h - (ry + rh))),
                max(1, int(rpw)),
                max(1, int(rh)),
            )

            y = ry + 12.0
            card_gap = 8
            # health card
            hclip = self._panel_card(rx, y, panel_inner_w, 52, border=hcol)
            self.texts.draw(
                font,
                f"STATUS · {lab}",
                text_left,
                y + 8,
                tuple(int(c * 255) for c in hcol),
                max_w=text_max,
                clip=hclip,
            )
            self.texts.draw(font_sm, why, text_left, y + 30, (150, 156, 170), max_w=text_max, clip=hclip)
            y += 52 + card_gap

            # inspector sub-header KPIs (was the old top bar)
            kclip = self._panel_card(rx, y, panel_inner_w, 54)
            fps_col = (80, 200, 120) if self.fps >= 45 else ((230, 180, 80) if self.fps >= 28 else (230, 80, 70))
            band = self.rate_band or "—"
            self.texts.draw(
                font_sm,
                f"{motion} · nodes {self.drawn_nodes}/{self.snapshot_total}",
                text_left,
                y + 8,
                (200, 205, 215),
                max_w=text_max,
                clip=kclip,
            )
            self.texts.draw(
                font_sm,
                f"vec {vec_n} · {band} · fps {self.fps:.0f}",
                text_left,
                y + 28,
                fps_col,
                max_w=text_max,
                clip=kclip,
            )
            y += 54 + card_gap

            # CONCERT STAGES — compact LED strip (P expands full list)
            pulse = 0.55 + 0.45 * math.sin(self.tick * 0.12)

            def _stage_col(st: str) -> tuple[float, float, float]:
                if st == "ok":
                    return (0.18, 0.80, 0.44)
                if st == "running":
                    return (0.95 * pulse, 0.77 * pulse, 0.06)
                if st == "fail":
                    return (0.90, 0.30, 0.24)
                if st == "skip":
                    return (0.35, 0.36, 0.40)
                return (0.40, 0.41, 0.46)

            if self.stages_compact:
                pipe_h = 56
                sclip = self._panel_card(rx, y, panel_inner_w, pipe_h)
                self.texts.draw(
                    font, "STAGES  ·  P expand", text_left, y + 6, (150, 156, 170), max_w=text_max, clip=sclip
                )
                # LED row — fixed strip; metrics below never overlay these
                led_w = max(8.0, (panel_inner_w - 24) / max(1, len(STAGE_ORDER)))
                for i, stg in enumerate(STAGE_ORDER):
                    st = self.stage_status.get(stg, "pending")
                    col = _stage_col(st)
                    lx = rx + 14 + i * led_w
                    gl_rect(lx, y + 28, max(6.0, led_w - 3), 10, col, 1.0)
                go_n = sum(1 for s in STAGE_ORDER if self.stage_status.get(s) == "ok")
                self.texts.draw(
                    font_sm,
                    f"{go_n}/{len(STAGE_ORDER)} GO · {self.rate_band or '—'}",
                    text_left,
                    y + 40,
                    (100, 106, 120),
                    max_w=text_max,
                    clip=sclip,
                )
                y += pipe_h + card_gap
            else:
                stage_h = 17
                pipe_h = 36 + len(STAGE_ORDER) * stage_h + 8
                sclip = self._panel_card(rx, y, panel_inner_w, pipe_h)
                self.texts.draw(font, "STAGES  ·  P compact", text_left, y + 6, (150, 156, 170), max_w=text_max, clip=sclip)
                self.texts.draw(font_sm, "last_dag + gui_events", text_left, y + 22, (100, 106, 120), max_w=text_max, clip=sclip)
                py = y + 40
                name_col_w = 100
                for stg in STAGE_ORDER:
                    st = self.stage_status.get(stg, "pending")
                    col = _stage_col(st)
                    light = {"ok": "GO", "running": "…", "fail": "FAIL", "skip": "skip"}.get(st, "·")
                    gl_rect(rx + 14, py + 3, 7, 7, col, 1.0)
                    name_col = (230, 232, 238) if st != "pending" else (100, 106, 120)
                    self.texts.draw(font_sm, stg, rx + 26, py, name_col, max_w=name_col_w, clip=sclip)
                    self.texts.draw(
                        font_sm, light, rx + 26 + name_col_w, py,
                        tuple(int(x * 255) for x in col), max_w=36, clip=sclip,
                    )
                    det = (self.stage_detail.get(stg, "") or "").replace("\n", " ").strip()
                    if det:
                        det_x = rx + 26 + name_col_w + 40
                        det_max = int(rx + 8 + panel_inner_w - 8 - det_x)
                        if det_max > 20:
                            self.texts.draw(font_sm, det, det_x, py, (100, 106, 120), max_w=det_max, clip=sclip)
                    py += stage_h
                y += pipe_h + card_gap

            # VECTORS — count + embed backend
            emb = self.embed_backend or str(self.vector_stats.get("embed_backend") or "tfidf")
            vclip = self._panel_card(rx, y, panel_inner_w, 68)
            self.texts.draw(font, "VECTOR INDEX", text_left, y + 6, (150, 156, 170), max_w=text_max, clip=vclip)
            self.texts.draw(font_title, str(vec_n), text_left, y + 26, (80, 200, 120), max_w=text_max // 2, clip=vclip)
            self.texts.draw(
                font_sm,
                f"vocab {self.vector_stats.get('vocab_terms', 0)}",
                text_left + max(110, text_max // 2),
                y + 32,
                (200, 205, 215),
                max_w=text_max // 2,
                clip=vclip,
            )
            self.texts.draw(
                font_sm,
                f"backend {emb}",
                text_left,
                y + 50,
                (100, 106, 120),
                max_w=text_max,
                clip=vclip,
            )
            y += 68 + card_gap

            # METRICS — live ops (not just concert signals)
            signals: dict[str, Any] = {}
            if isinstance(self.metrics, dict):
                sb = self.metrics.get("scoreboard") or self.metrics
                if isinstance(sb, dict):
                    signals = sb.get("signals") or self.metrics.get("signals") or {}
                else:
                    signals = self.metrics.get("signals") or {}
            if not isinstance(signals, dict):
                signals = {}
            sig_items = list(signals.items())[:4]
            pur = self.purity or {}
            ch = self.cloud_health or {}
            # ops scoreboard snapshot (beastMode --metrics) for HUD
            ops_band = ""
            ops_100 = None
            try:
                om = brain_dir() / "state" / "ops_metrics.json"
                if om.exists() and (time.time() - om.stat().st_mtime) < 900:
                    obl = json.loads(om.read_text(encoding="utf-8"))
                    ops_band = str((obl.get("score") or {}).get("band") or "")
                    ops_100 = (obl.get("score") or {}).get("ops_100")
            except Exception:
                pass
            sess_n = 0
            try:
                if isinstance(getattr(self, "source_counts", None), dict):
                    sess_n = int(self.source_counts.get("codex_session") or 0)
            except Exception:
                sess_n = 0
            # fixed ops block height so stage LEDs never get clipped by overflow
            ops_lines = 10
            met_h = 28 + ops_lines * 14 + max(0, len(sig_items)) * 14 + 10
            # clamp so ACTIVITY still has room and stage strip above stays intact
            max_met = max(120.0, (ry + rh - y) - 90.0)
            met_h = int(min(met_h, max_met))
            mclip = self._panel_card(rx, y, panel_inner_w, float(met_h))
            self.texts.draw(font, "METRICS", text_left, y + 6, (150, 156, 170), max_w=text_max, clip=mclip)
            my = y + 24
            work_ms = float(getattr(self, "_work_ms", 0.0) or 0.0)
            fps_c = (80, 200, 120) if self.fps >= 45 else ((230, 180, 80) if self.fps >= 28 else (230, 80, 70))
            settled_s = "yes" if self.layout_settled else "no"
            mode_s = "LIVE" if self.layout_live else "FROZEN"
            ops_c = (
                (80, 200, 120)
                if ops_band == "HEALTHY"
                else ((230, 180, 80) if ops_band == "CAUTION" else ((230, 80, 70) if ops_band else (100, 106, 120)))
            )
            ops_rows = [
                (f"fps {self.fps:.0f}  work {work_ms:.0f}ms  lod {self.lod_scale:.2f}", fps_c),
                (
                    f"settled {settled_s}  E {self.layout_energy:.2f}  {mode_s}",
                    (180, 185, 195),
                ),
                (
                    f"graph load {len(self.nodes)}n/{len(self.edges)}e · draw {self.drawn_nodes}/{self.drawn_edges}",
                    (200, 205, 215),
                ),
                (
                    f"corpus {self.snapshot_total}n"
                    + (f"/{self.edge_count_total}e" if self.edge_count_total else "")
                    + (f" · sess {sess_n}" if sess_n else ""),
                    (150, 156, 170),
                ),
                (
                    f"vec {vec_n} · {emb}",
                    (80, 200, 120),
                ),
                (
                    "purity pilot={pr} ops={ops} pub={pub:.0f}% q={q:.2f}".format(
                        pr="Y" if pur.get("pilot_ready") else "N",
                        ops="Y" if pur.get("pilot_ops_ready") else "N",
                        pub=float(pur.get("public_ratio_pct") or (float(pur.get("public_ratio") or 0) * 100)),
                        q=float(pur.get("quarantine_cov") or 0.0),
                    )
                    if pur
                    else "purity —",
                    (180, 185, 195) if pur else (100, 106, 120),
                ),
                (
                    "cloud nep={n} os={o} shim={s}".format(
                        n=ch.get("neptune_status") or ("cfg" if ch.get("neptune") else "off"),
                        o=ch.get("opensearch_status") or ("cfg" if ch.get("opensearch") else "off"),
                        s=ch.get("shim_status") or ("cfg" if ch.get("llm_shim") else "off"),
                    ),
                    (80, 180, 140)
                    if (ch.get("neptune") or ch.get("opensearch") or ch.get("llm_shim"))
                    else (100, 106, 120),
                ),
                (
                    "audit chain "
                    + (
                        "ok"
                        if self.audit_chain_ok is True
                        else ("FAIL" if self.audit_chain_ok is False else "—")
                    ),
                    (80, 200, 120)
                    if self.audit_chain_ok is True
                    else ((230, 80, 70) if self.audit_chain_ok is False else (100, 106, 120)),
                ),
                (
                    f"ops {ops_band or '—'} {ops_100 if ops_100 is not None else ''}".strip(),
                    ops_c,
                ),
            ]
            for line, col in ops_rows:
                if my + 12 > y + met_h - 4:
                    break
                self.texts.draw(font_sm, line, text_left, my, col, max_w=text_max, clip=mclip)
                my += 14
            # concert signals (compact)
            scmap = {"green": (0.18, 0.80, 0.44), "yellow": (0.95, 0.77, 0.06), "red": (0.90, 0.30, 0.24)}
            if sig_items and my + 12 <= y + met_h - 4:
                for sk, sv in sig_items:
                    if my + 12 > y + met_h - 4:
                        break
                    c = scmap.get(str(sv).lower(), (0.45, 0.47, 0.50))
                    gl_rect(rx + 14, my + 3, 7, 7, c, 1.0)
                    self.texts.draw(
                        font_sm, str(sk), rx + 28, my, (200, 202, 210), max_w=text_max - 64, clip=mclip
                    )
                    self.texts.draw(
                        font_sm,
                        str(sv)[:10],
                        rx + 8 + panel_inner_w - 60,
                        my,
                        tuple(int(x * 255) for x in c),
                        max_w=48,
                        clip=mclip,
                    )
                    my += 14
            elif not sig_items and my + 12 <= y + met_h - 4:
                self.texts.draw(
                    font_sm, "signals —", text_left, my, (100, 106, 120), max_w=text_max, clip=mclip
                )
            y += met_h + card_gap

            # EVIDENCE dual-pane (selected node + concert snippet) then ACTIVITY
            rem = ry + rh - y - 8
            if rem > 50:
                ev_h = min(168.0, rem * 0.48) if (self.selected or self.evidence_blobs) else 0.0
                if ev_h >= 70:
                    eclip = self._panel_card(rx, y, panel_inner_w, ev_h, border=(0.18, 0.45, 0.55))
                    self.texts.draw(
                        font, "EVIDENCE", text_left, y + 6, (120, 190, 210), max_w=text_max, clip=eclip
                    )
                    n = self.nodes.get(self.selected or "") if self.selected else None
                    blob = None
                    if self.selected:
                        for b in self.evidence_blobs:
                            if b.get("id") == self.selected:
                                blob = b
                                break
                    title = ""
                    snip = ""
                    meta = ""
                    if n:
                        title = str(n.get("title") or n.get("id") or "")[:80]
                        snip = str(n.get("content") or n.get("text") or n.get("summary") or "")[:360]
                        meta = f"{n.get('type')} · {n.get('source')} · {n.get('tier')} · {str(n.get('id') or '')[:36]}"
                    elif blob:
                        title = blob.get("title") or blob.get("id") or ""
                        snip = blob.get("snippet") or ""
                        meta = f"{blob.get('source')} · {blob.get('tier')} · {str(blob.get('id') or '')[:36]}"
                    elif self.evidence_blobs:
                        blob = self.evidence_blobs[0]
                        title = blob.get("title") or ""
                        snip = blob.get("snippet") or "(run concert for snippets)"
                        meta = f"path {len(self.evidence_ids)} nodes · E autoplay"
                    else:
                        title = "select a node or press E"
                        snip = "Concert evidence + node body show here (dual-pane)."
                        meta = "GraphRAG explainability"
                    self.texts.draw(font_sm, title, text_left, y + 24, (220, 225, 235), max_w=text_max, clip=eclip)
                    self.texts.draw(font_sm, meta, text_left, y + 40, (120, 140, 160), max_w=text_max, clip=eclip)
                    # wrap snippet roughly
                    yy = y + 56
                    words = (snip or "—").split()
                    line = ""
                    for w in words:
                        trial = (line + " " + w).strip()
                        if len(trial) > 48:
                            self.texts.draw(
                                font_sm, line, text_left, yy, (170, 180, 195), max_w=text_max, clip=eclip
                            )
                            yy += 13
                            line = w
                            if yy > y + ev_h - 16:
                                break
                        else:
                            line = trial
                    if line and yy <= y + ev_h - 16:
                        self.texts.draw(
                            font_sm, line, text_left, yy, (170, 180, 195), max_w=text_max, clip=eclip
                        )
                    y += ev_h + card_gap
                    rem = ry + rh - y - 8
                if rem > 50:
                    aclip = self._panel_card(rx, y, panel_inner_w, rem)
                    self.texts.draw(font, "ACTIVITY", text_left, y + 6, (150, 156, 170), max_w=text_max, clip=aclip)
                    self.texts.draw(
                        font_sm,
                        f"GPU {self.gpu_path}",
                        text_left,
                        y + 24,
                        (100, 140, 180),
                        max_w=text_max,
                        clip=aclip,
                    )
                    ey = y + 40
                    for line in list(self.event_log)[: max(1, int((rem - 48) / 14))]:
                        self.texts.draw(font_sm, line, text_left, ey, (100, 106, 120), max_w=text_max, clip=aclip)
                        ey += 14

            glDisable(GL_SCISSOR_TEST)

        if self.show_legend:
            counts: dict[str, int] = defaultdict(int)
            for n in self.nodes.values():
                counts[str(n.get("source") or "unknown")] += 1
            rows = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
            lh = 28 + len(rows) * 16
            lx, ly = gx + 14.0, gy + 52.0
            lw = 200.0
            # never bleed into inspector or off window
            max_x = gx + gw - 12
            if lx + lw > max_x:
                lx = max(gx + 8, max_x - lw)
            lx, ly, lw, lh = self._clip_box(lx, ly, lw, float(lh))
            gl_rect(lx, ly, lw, lh, (0.08, 0.09, 0.12), 0.92)
            gl_rect_border(lx, ly, lw, lh, (0.25, 0.28, 0.35), 1.0)
            lclip = self._clip_box(lx + 4, ly + 2, lw - 8, lh - 4)
            self.texts.draw(font_sm, "SOURCES (L)", lx + 8, ly + 6, (200, 205, 215), max_w=int(lw - 16), clip=lclip)
            yy = ly + 24
            for src, c in rows:
                if yy + 14 > ly + lh - 4:
                    break
                rgb = SOURCE_RGB.get(src, (0.5, 0.5, 0.55))
                gl_rect(lx + 8, yy + 2, 10, 10, rgb, 1.0)
                self.texts.draw(
                    font_sm, f"{src}  {c}", lx + 24, yy, (180, 185, 195), max_w=int(lw - 40), clip=lclip
                )
                yy += 16

        if self.show_help:
            # Dual-audience help panel — SIMPLE (anyone) vs ADVANCED (senior)
            # Hard-clipped to window; never bleeds.
            hw = min(560.0, float(self.w) - 48.0)
            hh = min(320.0, float(self.h) - 80.0)
            hx = max(16.0, (float(self.w) - hw) / 2.0)
            hy = max(32.0, float(self.h) * 0.08)
            hx, hy, hw, hh = self._clip_box(hx, hy, hw, hh)
            gl_rect(hx, hy, hw, hh, (0.07, 0.08, 0.11), 0.97)
            border = (0.30, 0.75, 0.45) if self.help_mode == "simple" else (0.35, 0.55, 1.0)
            gl_rect_border(hx, hy, hw, hh, border, 1.0)
            hclip2 = self._clip_box(hx + 10, hy + 8, hw - 20, hh - 16)
            mode = (self.help_mode or "simple").lower()
            if mode not in ("simple", "advanced"):
                mode = "simple"
            title = "HELP · SIMPLE (anyone)" if mode == "simple" else "HELP · ADVANCED (senior)"
            self.texts.draw(
                font,
                title,
                hx + 14,
                hy + 12,
                (120, 220, 150) if mode == "simple" else (140, 180, 255),
                max_w=int(hw - 28),
                clip=hclip2,
            )
            self.texts.draw(
                font_sm,
                "H switch simple/advanced · Esc close · docs/GODSEYE_HELP.md",
                hx + 14,
                hy + 32,
                (120, 128, 145),
                max_w=int(hw - 28),
                clip=hclip2,
            )
            if mode == "simple":
                lines = [
                    "This is a MAP of your brain. Dots = things it knows.",
                    "Drag = move · Scroll = zoom · Click = name card",
                    "Double-click = zoom to that thing · 0 = fit all",
                    "Green Healthy pill (top-left) = good. You can ignore the rest.",
                    "I = engineer panel (optional) · Q = quit",
                    "Confused? Close this (Esc) and just drag around.",
                    "Chat in Codex still works if you quit GodsEye.",
                ]
            else:
                gpu = f"{self.gpu_renderer or '?'} · {self.gpu_path}"
                lines = [
                    f"GPU: {gpu}"[:72],
                    "I Inspector · M minimap · P stages · Space freeze · R reseed · S reload",
                    "F/T source·tier · 1-4 tiers · 5 all · L legend · E evidence path",
                    "N neighbors · [ ] trail walk · dual-pane EVIDENCE in Inspector",
                    "simple_mode default · scissor/clip = no window bleed",
                    f"fps {self.fps:.0f} · lod {self.lod_scale:.2f} · load {len(self.nodes)}n · corpus {self.snapshot_total}",
                    "Telemetry: .brain/state/godseye_perf.json · godseye_metrics.json",
                ]
            for i, line in enumerate(lines):
                yy = hy + 56 + i * 28
                if yy + 16 > hy + hh - 8:
                    break
                self.texts.draw(
                    font_sm,
                    line,
                    hx + 14,
                    yy,
                    (220, 225, 235),
                    max_w=int(hw - 28),
                    clip=hclip2,
                )


def mark_dismissed() -> None:
    st = brain_dir() / "state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "godseye.dismissed").write_text("1\n", encoding="utf-8")
    for name in ("godseye.pid", "visualizer.pid"):
        p = st / name
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain TRUE OpenGL Live Ops")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()

    snap = Path(args.snapshot) if args.snapshot else brain_dir() / "graph" / "snapshot.json"
    dag = brain_dir() / "state" / "last_dag.json"
    events = brain_dir() / "state" / "gui_events.jsonl"
    emb = brain_dir() / "index" / "embeddings"
    metrics_dir = brain_dir() / "state" / "metrics"

    pygame.init()
    # Request hardware-accelerated OpenGL (GPU) — not software rasterizer
    try:
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 16)
        pygame.display.gl_set_attribute(pygame.GL_ACCELERATED_VISUAL, 1)
        # Prefer modern-ish context when available (falls back silently)
        if hasattr(pygame, "GL_CONTEXT_MAJOR_VERSION"):
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 2)
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
    except Exception:
        pass
    pygame.display.set_caption("Private Brain — GodsEye")
    flags = OPENGL | DOUBLEBUF | RESIZABLE
    pygame.display.set_mode((args.width, args.height), flags)

    viz = LiveGL(args.width, args.height)
    viz.setup_gl()
    # Log GPU renderer once (helps Corporate verify acceleration)
    try:
        from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER, GL_VERSION

        vend = glGetString(GL_VENDOR)
        rend = glGetString(GL_RENDERER)
        ver = glGetString(GL_VERSION)
        viz.event_log.appendleft(
            f"GPU {vend!s} | {rend!s} | {ver!s}".replace("b'", "").replace("'", "")[:90]
        )
        print(f"GodsEye GPU: vendor={vend} renderer={rend} version={ver}", flush=True)
    except Exception as e:
        viz.event_log.appendleft(f"GPU probe failed: {e}")
    viz.reload_snapshot(snap)
    viz.reload_dag(dag)
    viz.reload_vectors(emb)
    viz.reload_metrics(metrics_dir)
    viz.reload_ops_state()
    viz.reload_cloud_health()

    font = pygame.font.SysFont("menlo,consolas,monospace", 14)
    font_sm = pygame.font.SysFont("menlo,consolas,monospace", 12)
    font_title = pygame.font.SysFont("menlo,consolas,monospace", 17, bold=True)
    clock = pygame.time.Clock()
    dragging = False
    drag_last = (0, 0)
    last_poll = 0.0
    last_click_t = 0.0
    last_click_id: str | None = None

    running = True
    while running:
        now = time.time()
        if now - last_poll > 0.45:
            try:
                viz.reload_snapshot(snap)
                viz.reload_dag(dag)
                viz.poll_events(events)
                viz.reload_vectors(emb)
                viz.reload_metrics(metrics_dir)
                if viz.tick % 90 == 0 or not viz.cloud_health:
                    viz.reload_cloud_health()
            except Exception:
                pass
            last_poll = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                pygame.display.set_mode((event.w, event.h), flags)
                viz.resize(event.w, event.h)
            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_q or (
                    event.key == pygame.K_w and (mods & (pygame.KMOD_META | pygame.KMOD_CTRL))
                ):
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    if viz.show_help:
                        viz.show_help = False
                    elif viz.show_legend:
                        viz.show_legend = False
                    elif viz.show_inspector:
                        viz.show_inspector = False
                        viz.event_log.appendleft("inspector OFF")
                    elif viz.selected:
                        viz.select_node(None)
                    else:
                        running = False
                elif event.key == pygame.K_h:
                    # Cycle: closed → simple → advanced → closed
                    if not viz.show_help:
                        viz.show_help = True
                        viz.help_mode = "simple"
                    elif viz.help_mode == "simple":
                        viz.help_mode = "advanced"
                    else:
                        viz.show_help = False
                        viz.help_mode = "simple"
                    viz.event_log.appendleft(
                        f"help {viz.help_mode}" if viz.show_help else "help OFF"
                    )
                elif event.key == pygame.K_i:
                    viz.show_inspector = not viz.show_inspector
                    viz.event_log.appendleft(
                        "inspector ON" if viz.show_inspector else "inspector OFF"
                    )
                elif event.key == pygame.K_SPACE:
                    viz.layout_live = not viz.layout_live
                    if not viz.layout_live:
                        for v in viz.vel.values():
                            v[0] = v[1] = 0.0
                    viz.event_log.appendleft("layout LIVE" if viz.layout_live else "layout FROZEN")
                elif event.key == pygame.K_p:
                    if not viz.show_inspector:
                        viz.show_inspector = True
                    viz.stages_compact = not viz.stages_compact
                    viz.event_log.appendleft(
                        "stages compact" if viz.stages_compact else "stages expanded"
                    )
                elif event.key == pygame.K_m:
                    viz.show_minimap = not viz.show_minimap
                    viz.event_log.appendleft("minimap ON" if viz.show_minimap else "minimap OFF")
                elif event.key == pygame.K_r:
                    viz.pos.clear()
                    viz.vel.clear()
                    viz.snap_mtime = 0
                    viz.reload_snapshot(snap)
                    viz.layout_live = True
                    viz.layout_settled = False
                    viz.layout_energy = 1.0
                    viz.event_log.appendleft("universe reseed (constellations)")
                elif event.key == pygame.K_s:
                    viz.snap_mtime = viz.dag_mtime = 0
                    viz.events_offset = 0
                    viz.reload_snapshot(snap)
                    viz.reload_dag(dag)
                elif event.key == pygame.K_0 or event.key == pygame.K_HOME:
                    viz.focus_camera(None)
                    viz.event_log.appendleft("camera fit")
                elif event.key == pygame.K_f:
                    order = [
                        "all", "gitlab", "github", "jira", "confluence",
                        "brain", "codex_session", "local", "metrics",
                    ]
                    i = order.index(viz.source_filter) if viz.source_filter in order else 0
                    viz.source_filter = order[(i + 1) % len(order)]
                    viz.event_log.appendleft(f"filter source={viz.source_filter}")
                elif event.key == pygame.K_t:
                    order = ["all", "T0", "T1", "T2", "T3"]
                    i = order.index(viz.tier_filter) if viz.tier_filter in order else 0
                    viz.tier_filter = order[(i + 1) % len(order)]
                    viz.event_log.appendleft(f"filter tier={viz.tier_filter}")
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    tier_map = {
                        pygame.K_1: "T0",
                        pygame.K_2: "T1",
                        pygame.K_3: "T2",
                        pygame.K_4: "T3",
                        pygame.K_5: "all",
                    }
                    viz.tier_filter = tier_map[event.key]
                    viz.event_log.appendleft(f"tier={viz.tier_filter}")
                elif event.key == pygame.K_l:
                    viz.show_legend = not viz.show_legend
                    viz.event_log.appendleft("legend ON" if viz.show_legend else "legend OFF")
                elif event.key == pygame.K_e:
                    if not viz.evidence_ids:
                        viz.event_log.appendleft("no concert evidence yet — run concert")
                    else:
                        viz.start_path_autoplay(viz.evidence_ids)
                elif event.key == pygame.K_n:
                    if not viz.selected:
                        viz.event_log.appendleft("select a node first (click)")
                    else:
                        seed = viz.selected
                        viz.lit_nodes[seed] = 1.0
                        for a, b, _rel in viz.adj.get(seed) or []:
                            other = b if a == seed else a
                            viz.lit_nodes[other] = 0.85
                            viz.lit_edges.add((a, b) if a < b else (b, a))
                        viz.event_log.appendleft(f"neighbors of {seed[:32]}")
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_LEFT):
                    viz.walk_trail(+1)
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_RIGHT):
                    viz.walk_trail(-1)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    hit = viz.hit_test(*event.pos)
                    tnow = time.time()
                    if hit:
                        dbl = (
                            hit == last_click_id
                            and (tnow - last_click_t) < 0.35
                        )
                        viz.select_node(hit, focus=dbl)
                        if dbl:
                            viz.event_log.appendleft(f"focus {hit[:36]}")
                        last_click_id = hit
                        last_click_t = tnow
                    else:
                        gx, gy, gw, gh = viz.graph_rect()
                        if gx <= event.pos[0] <= gx + gw and gy <= event.pos[1] <= gy + gh:
                            viz.select_node(None)
                        dragging = True
                        drag_last = event.pos
                        last_click_id = None
                elif event.button == 4:
                    viz.zoom = min(4.0, viz.zoom * 1.12)
                elif event.button == 5:
                    viz.zoom = max(0.12, viz.zoom / 1.12)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION:
                viz.mouse_xy = event.pos
                if dragging:
                    dx = event.pos[0] - drag_last[0]
                    dy = event.pos[1] - drag_last[1]
                    viz.pan[0] += dx / viz.zoom
                    viz.pan[1] += dy / viz.zoom
                    drag_last = event.pos
                else:
                    # hover every frame is cheap vs layout
                    viz.hover_id = viz.hit_test(*event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                viz.zoom = min(4.0, viz.zoom * 1.12) if event.y > 0 else max(0.12, viz.zoom / 1.12)

        t_work0 = time.perf_counter()
        viz.update_camera()
        viz.step_layout()
        try:
            viz.tick_path_autoplay()
        except Exception:
            pass
        if viz.tick % 3 == 0:
            viz.decay_lit()
        viz.tick += 1
        viz.draw(font, font_sm, font_title)
        pygame.display.flip()
        viz._work_ms = (time.perf_counter() - t_work0) * 1000.0
        viz.note_frame()
        # Settled layout → lower frame ceiling frees CPU (micro-breathe still smooth)
        if viz.layout_settled and not viz.cam_target and viz.lod_scale >= 0.95:
            clock.tick(48)
        else:
            clock.tick(60)
        # Telemetry: metrics every ~2s; perf on same cadence (time-based so low-FPS still writes)
        viz.write_metrics_snapshot(force=False)
        now_w = time.time()
        if not hasattr(viz, "_last_perf_snap_t"):
            viz._last_perf_snap_t = 0.0
        if now_w - float(viz._last_perf_snap_t) >= 2.0:
            viz._last_perf_snap_t = now_w
            try:
                perf_path = brain_dir() / "state" / "godseye_perf.json"
                perf_path.parent.mkdir(parents=True, exist_ok=True)
                perf_path.write_text(
                    json.dumps(
                        {
                            "fps": round(viz.fps, 1),
                            "frame_ms": round(viz.frame_ms, 1),
                            "work_ms": round(getattr(viz, "_work_ms", 0), 1),
                            "lod_scale": round(viz.lod_scale, 3),
                            "drawn_nodes": viz.drawn_nodes,
                            "drawn_edges": viz.drawn_edges,
                            "loaded_nodes": len(viz.nodes),
                            "loaded_edges": len(viz.edges),
                            "corpus_nodes": viz.snapshot_total,
                            "perf_warn": viz.perf_warn,
                            "gpu_path": viz.gpu_path,
                            "gpu_vendor": viz.gpu_vendor,
                            "gpu_renderer": viz.gpu_renderer,
                            "gpu_version": viz.gpu_version,
                            "layout_settled": viz.layout_settled,
                            "layout_energy": round(viz.layout_energy, 4),
                            "stages_compact": viz.stages_compact,
                            "minimap": viz.show_minimap,
                            "inspector": viz.show_inspector,
                            "simple_mode": not viz.show_inspector,
                            "hover": bool(viz.hover_id),
                            "ultra": {
                                "scissor": True,
                                "no_window_bleed": True,
                                "simple_default": True,
                                "draw_arrays": True,
                                "hierarchical_seed": True,
                                "tooltip": True,
                                "minimap": viz.show_minimap,
                                "camera_focus": True,
                                "floating_selection_sheet": True,
                                "dual_help": True,
                                "help_mode": viz.help_mode,
                            },
                            "ok": viz.fps >= 28 or viz.tick < 45,
                            "target_frame_ms": TARGET_FRAME_MS,
                        }
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

    mark_dismissed()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
