"""Shared filesystem RAG-DAG primitives. No database. Cross-platform."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_fs_lock = threading.RLock()
# Process-local fast paths — avoid thrashing meta/session on every call.
_tree_ready: bool = False
_tree_ready_path: Path | None = None
_nodes_cache: list[dict[str, Any]] | None = None
_edges_cache: list[dict[str, Any]] | None = None
# Parallel lowercased meta blobs for query() — built with nodes cache.
_nodes_meta_lc: list[str] | None = None


def invalidate_graph_cache() -> None:
    global _nodes_cache, _edges_cache, _nodes_meta_lc
    _nodes_cache = None
    _edges_cache = None
    _nodes_meta_lc = None


def resolve_brain_root() -> Path:
    for key in ("PRIVATE_BRAIN_HOME", "PRIVATE_BRAIN_ROOT"):
        v = os.environ.get(key)
        if v:
            return Path(v).expanduser().resolve()
    codex = os.environ.get("CODEX_HOME")
    if codex:
        p = Path(codex).expanduser().resolve() / "private-brain"
        if p.is_dir() or True:
            return p
    home = Path.home() / ".codex" / "private-brain"
    return home.resolve()


def resolve_brain_dir() -> Path:
    # Sideload law: PRIVATE_BRAIN_HOME / PRIVATE_BRAIN_ROOT always win when set
    # (hooks + CI + multi-kit). Only then allow project-local .brain override.
    if os.environ.get("PRIVATE_BRAIN_HOME") or os.environ.get("PRIVATE_BRAIN_ROOT"):
        return resolve_brain_root() / ".brain"
    cwd_brain = Path.cwd() / ".brain"
    if cwd_brain.is_dir() and (cwd_brain / "meta.json").exists():
        return cwd_brain.resolve()
    return resolve_brain_root() / ".brain"


BRAIN_ROOT = resolve_brain_root()
BRAIN = resolve_brain_dir()
NODE_DIR = BRAIN / "nodes"
EDGE_DIR = BRAIN / "edges"
CONTENT_DIR = BRAIN / "content"
CHUNK_DIR = BRAIN / "chunks"
INDEX_DIR = BRAIN / "index"
GRAPH_DIR = BRAIN / "graph"
STATE_DIR = BRAIN / "state"
LOG_DIR = BRAIN / "logs"
CRAWL_DIR = BRAIN / "crawls"

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


def _subdirs() -> list[Path]:
    return [
        NODE_DIR,
        EDGE_DIR,
        CONTENT_DIR,
        CHUNK_DIR,
        INDEX_DIR / "by_tag",
        INDEX_DIR / "by_type",
        INDEX_DIR / "by_source",
        INDEX_DIR / "inverted",
        GRAPH_DIR,
        STATE_DIR,
        LOG_DIR,
        CRAWL_DIR / "jira",
        CRAWL_DIR / "confluence",
        CRAWL_DIR / "gitlab",
        BRAIN / "prompts",
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_id(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", node_id)


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    """Atomic JSON write (unique tmp per call — safe under multi-process reindex)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    last_err: Exception | None = None
    with _fs_lock:
        for attempt in range(6):
            # Unique tmp avoids FileNotFoundError when two processes share path.tmp
            tmp = path.parent / (
                f".{path.name}.{os.getpid()}.{threading.get_ident()}."
                f"{time.time_ns()}.{attempt}.tmp"
            )
            try:
                tmp.write_text(data, encoding="utf-8")
                os.replace(str(tmp), str(path))
                return
            except (FileNotFoundError, OSError) as e:
                last_err = e
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
                path.parent.mkdir(parents=True, exist_ok=True)
                time.sleep(0.015 * (attempt + 1))
    if last_err:
        raise last_err
    raise OSError(f"write_json failed for {path}")


def read_json(path: Path) -> Any:
    """Read JSON file. Lock-free: writers use atomic tmp+replace."""
    # Hot path: bulk load_all_* / vectors — avoid lock thrash on thousands of files.
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _read_json_bytes(path: Path) -> Any:
    """Slightly faster bulk read (one open, no text decode intermediate for small files)."""
    with path.open("rb") as f:
        raw = f.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def log(event: str, **kwargs: Any) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = {"ts": utc_now(), "event": event, **kwargs}
    day = time.strftime("%Y%m%d")
    append_jsonl(LOG_DIR / f"{day}.jsonl", line)


def ensure_tree() -> Path:
    """Idempotent tree ensure. Fast-path after first successful init in-process."""
    global BRAIN, NODE_DIR, EDGE_DIR, CONTENT_DIR, CHUNK_DIR, INDEX_DIR
    global GRAPH_DIR, STATE_DIR, LOG_DIR, CRAWL_DIR, BRAIN_ROOT
    global _tree_ready, _tree_ready_path

    # Ultra-hot path: skip Path.resolve() thrash when already ready and dirs live.
    # Env-based root changes mid-process are vanishingly rare; invalidate by process restart.
    if (
        _tree_ready
        and _tree_ready_path is not None
        and NODE_DIR.is_dir()
        and STATE_DIR.is_dir()
        and EDGE_DIR.is_dir()
    ):
        return _tree_ready_path

    BRAIN_ROOT = resolve_brain_root()
    brain = resolve_brain_dir()

    BRAIN = brain
    NODE_DIR = BRAIN / "nodes"
    EDGE_DIR = BRAIN / "edges"
    CONTENT_DIR = BRAIN / "content"
    CHUNK_DIR = BRAIN / "chunks"
    INDEX_DIR = BRAIN / "index"
    GRAPH_DIR = BRAIN / "graph"
    STATE_DIR = BRAIN / "state"
    LOG_DIR = BRAIN / "logs"
    CRAWL_DIR = BRAIN / "crawls"

    for d in _subdirs():
        d.mkdir(parents=True, exist_ok=True)

    meta = BRAIN / "meta.json"
    if not meta.exists():
        write_json(
            meta,
            {
                "version": 1,
                "created_at": utc_now(),
                "sources": ["gitlab", "jira", "confluence"],
                "node_count": 0,
                "edge_count": 0,
                "snapshot_dirty": True,
                "last_init": utc_now(),
                "brain_root": str(BRAIN_ROOT),
            },
        )
    # Do NOT rewrite meta/session on every ensure — that was ~1ms * N write thrash.

    cursors = STATE_DIR / "cursors.json"
    if not cursors.exists():
        write_json(
            cursors,
            {
                "gitlab": {"last_topo": None, "last_deep": {}},
                "jira": {"last_topo": None, "last_deep": {}},
                "confluence": {"last_topo": None, "last_deep": {}},
            },
        )

    sess = STATE_DIR / "session.json"
    if not sess.exists():
        write_json(
            sess,
            {"started_at": utc_now(), "visualizer_pid": None, "status": "ready"},
        )

    snap = GRAPH_DIR / "snapshot.json"
    if not snap.exists():
        write_json(snap, {"nodes": [], "edges": [], "generated_at": utc_now()})

    _tree_ready = True
    _tree_ready_path = brain
    return BRAIN


def node_path(node_id: str) -> Path:
    return NODE_DIR / f"{safe_id(node_id)}.json"


def edge_path(src: str, rel: str, dst: str) -> Path:
    eid = f"{safe_id(src)}__{safe_id(rel)}__{safe_id(dst)}"
    return EDGE_DIR / f"{eid}.json"



def _audit_safe(action: str, **kwargs):
    try:
        from audit_lib import audit as _audit
        _audit(action, **kwargs)
    except Exception:
        pass


def write_node(
    node_id: str,
    *,
    type: str,
    source: str,
    title: str,
    tier: str = "T2",
    uri: str | None = None,
    tags: list[str] | None = None,
    labels: list[str] | None = None,
    parent_id: str | None = None,
    content: str | None = None,
    props: dict[str, Any] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
    chunk: bool = True,
    max_chunk_chars: int = 4000,
) -> dict[str, Any]:
    ensure_tree()
    tags = tags or []
    labels = labels or []
    props = props or {}
    now = utc_now()
    content_path = None
    chunk_ids: list[str] = []
    body_hash = None

    if content is not None:
        content_path = f"content/{safe_id(node_id)}.md"
        (CONTENT_DIR / f"{safe_id(node_id)}.md").write_text(content, encoding="utf-8")
        body_hash = sha256_text(content)
        # Always emit ≥1 Chunk when content present (handoff: page with body must
        # not end with chunk_ids=[]). Short pages still get a single chunk.
        if chunk and str(content).strip():
            chunk_ids = _write_chunks(node_id, content, max_chunk_chars)

    node = {
        "id": node_id,
        "type": type,
        "source": source,
        "title": title,
        "uri": uri,
        "tier": tier,
        "tags": tags,
        "labels": labels,
        "parent_id": parent_id,
        "created_at": created_at or now,
        "updated_at": updated_at or now,
        "crawled_at": now,
        "content_path": content_path,
        "chunk_ids": chunk_ids,
        "props": props,
        "hash": body_hash,
    }
    write_json(node_path(node_id), node)
    _index_node(node)
    invalidate_graph_cache()
    _mark_dirty()
    log("write_node", id=node_id, type=type, source=source)
    _audit_safe("graph_write_node", agent_id=__import__("os").environ.get("PRIVATE_BRAIN_AGENT_ID", "brain_lib"),
                role=__import__("os").environ.get("PRIVATE_BRAIN_ROLE", "graph-writer"),
                object_id=node_id, result="ok", detail=f"type={type} source={source}")
    return node


def write_edge(
    src: str,
    rel: str,
    dst: str,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_tree()
    edge = {
        "id": f"{src}__{rel}__{dst}",
        "src": src,
        "rel": rel,
        "dst": dst,
        "props": props or {},
        "created_at": utc_now(),
    }
    write_json(edge_path(src, rel, dst), edge)
    invalidate_graph_cache()
    _mark_dirty()
    log("write_edge", src=src, rel=rel, dst=dst)
    _audit_safe("graph_write_edge", agent_id=__import__("os").environ.get("PRIVATE_BRAIN_AGENT_ID", "brain_lib"),
                role=__import__("os").environ.get("PRIVATE_BRAIN_ROLE", "graph-writer"),
                object_id=f"{src}__{rel}__{dst}", result="ok", detail=rel)
    return edge


def _write_chunks(node_id: str, content: str, max_chars: int) -> list[str]:
    parts = _structure_chunk(content, max_chars)
    ids: list[str] = []
    prev: str | None = None
    for i, part in enumerate(parts):
        cid = f"{node_id}__{i}"
        ids.append(cid)
        (CHUNK_DIR / f"{safe_id(cid)}.md").write_text(part, encoding="utf-8")
        write_json(
            node_path(cid),
            {
                "id": cid,
                "type": "BrainChunk",
                "source": "brain",
                "title": f"chunk {i} of {node_id}",
                "tier": "T2",
                "tags": [],
                "labels": ["chunk"],
                "parent_id": node_id,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "crawled_at": utc_now(),
                "content_path": f"chunks/{safe_id(cid)}.md",
                "chunk_ids": [],
                "props": {"chunk_index": i, "parent_id": node_id},
                "hash": sha256_text(part),
            },
        )
        write_edge(node_id, "HAS_CHUNK", cid)
        if prev is not None:
            write_edge(prev, "NEXT_CHUNK", cid)
        prev = cid
    return ids


def _structure_chunk(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    blocks = re.split(r"(?m)(?=^#{1,6}\s)", text)
    if len(blocks) == 1:
        blocks = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    buf = ""
    for b in blocks:
        if not b:
            continue
        if len(buf) + len(b) + 1 <= max_chars:
            buf = f"{buf}\n{b}".strip() if buf else b
        else:
            if buf:
                chunks.append(buf)
            if len(b) <= max_chars:
                buf = b
            else:
                for i in range(0, len(b), max_chars):
                    chunks.append(b[i : i + max_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [text[:max_chars]]


def _index_node(node: dict[str, Any]) -> None:
    entry = {"id": node["id"], "title": node.get("title"), "tier": node.get("tier")}
    append_jsonl(INDEX_DIR / "by_type" / f"{safe_id(node['type'])}.jsonl", entry)
    append_jsonl(INDEX_DIR / "by_source" / f"{safe_id(node['source'])}.jsonl", entry)
    for tag in node.get("tags") or []:
        append_jsonl(INDEX_DIR / "by_tag" / f"{safe_id(tag)}.jsonl", entry)


def _mark_dirty() -> None:
    meta_path = BRAIN / "meta.json"
    if meta_path.exists():
        m = read_json(meta_path)
        m["snapshot_dirty"] = True
        write_json(meta_path, m)


def _node_meta_lc(n: dict[str, Any]) -> str:
    """Lowercased meta blob for lexical query (no content I/O, no json.dumps thrash)."""
    props = n.get("props") or {}
    if props:
        prop_parts: list[str] = []
        for k, v in props.items():
            prop_parts.append(str(k))
            if v is None or v is False:
                continue
            if isinstance(v, (str, int, float, bool)):
                prop_parts.append(str(v))
            elif isinstance(v, (list, tuple)):
                prop_parts.extend(str(x) for x in v if x is not None)
            # skip nested dicts — rare on hot path; tags/title cover retrieval
        prop_s = " ".join(prop_parts)
    else:
        prop_s = ""
    return " ".join(
        [
            n.get("id") or "",
            n.get("title") or "",
            " ".join(n.get("tags") or []),
            " ".join(n.get("labels") or []),
            prop_s,
        ]
    ).lower()


def load_all_nodes() -> list[dict[str, Any]]:
    """Load all nodes; process-cached until write_node/write_edge invalidates."""
    global _nodes_cache, _nodes_meta_lc
    ensure_tree()
    if _nodes_cache is not None:
        return _nodes_cache
    nodes: list[dict[str, Any]] = []
    for p in NODE_DIR.glob("*.json"):
        try:
            nodes.append(_read_json_bytes(p))
        except Exception:
            continue
    _nodes_cache = nodes
    # Meta index built lazily on first query() — keeps cold load lean.
    _nodes_meta_lc = None
    return nodes


def load_all_edges() -> list[dict[str, Any]]:
    """Load all edges; process-cached until graph write invalidates."""
    global _edges_cache
    ensure_tree()
    if _edges_cache is not None:
        return _edges_cache
    edges: list[dict[str, Any]] = []
    for p in EDGE_DIR.glob("*.json"):
        try:
            edges.append(_read_json_bytes(p))
        except Exception:
            continue
    _edges_cache = edges
    return edges


def build_snapshot(*, force: bool = False) -> dict[str, Any]:
    """Rebuild graph snapshot. Skips work when clean unless force=True."""
    ensure_tree()
    meta_path = BRAIN / "meta.json"
    snap_path = GRAPH_DIR / "snapshot.json"
    if not force and meta_path.exists() and snap_path.exists():
        try:
            m = read_json(meta_path)
            if not m.get("snapshot_dirty", True):
                return read_json(snap_path)
        except Exception:
            pass
    nodes = load_all_nodes()
    edges = load_all_edges()
    viz_nodes = [n for n in nodes if n.get("type") != "BrainChunk"]
    viz_edges = [e for e in edges if e.get("rel") not in ("HAS_CHUNK", "NEXT_CHUNK")]
    snap = {
        "nodes": [
            {
                "id": n["id"],
                "type": n.get("type"),
                "source": n.get("source"),
                "title": n.get("title"),
                "tier": n.get("tier"),
                "tags": n.get("tags") or [],
                "labels": n.get("labels") or [],
                "uri": n.get("uri"),
                "parent_id": n.get("parent_id"),
            }
            for n in viz_nodes
        ],
        "edges": [
            {"id": e["id"], "src": e["src"], "rel": e["rel"], "dst": e["dst"]}
            for e in viz_edges
        ],
        "generated_at": utc_now(),
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "viz_nodes": len(viz_nodes),
            "viz_edges": len(viz_edges),
        },
    }
    write_json(GRAPH_DIR / "snapshot.json", snap)
    meta = read_json(BRAIN / "meta.json")
    meta["node_count"] = len(nodes)
    meta["edge_count"] = len(edges)
    meta["snapshot_dirty"] = False
    meta["last_snapshot"] = utc_now()
    write_json(BRAIN / "meta.json", meta)
    log("snapshot", nodes=len(nodes), edges=len(edges))
    return snap


def query(
    text: str | None = None,
    *,
    type: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    tier: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Lexical query. Metadata first; content only if meta pool thin (hard cap I/O)."""
    global _nodes_meta_lc
    nodes = load_all_nodes()
    # Ensure meta index matches nodes (rebuild if stale / missing).
    if _nodes_meta_lc is None or len(_nodes_meta_lc) != len(nodes):
        _nodes_meta_lc = [_node_meta_lc(n) for n in nodes]
    meta_lc = _nodes_meta_lc
    meta_hits: list[dict[str, Any]] = []
    need_content: list[dict[str, Any]] = []
    q = (text or "").lower().strip()
    q_tokens = [t for t in re.split(r"\s+", q) if len(t) > 1] if q else []
    for i, n in enumerate(nodes):
        if type and n.get("type") != type:
            continue
        if source and n.get("source") != source:
            continue
        if tier and n.get("tier") != tier:
            continue
        if tag and tag not in (n.get("tags") or []):
            continue
        if not q:
            meta_hits.append(n)
            if len(meta_hits) >= limit * 4:
                break
            continue
        meta_blob = meta_lc[i]
        if q in meta_blob or (q_tokens and all(t in meta_blob for t in q_tokens)):
            meta_hits.append(n)
            # enough meta hits → skip expensive content scans entirely
            if len(meta_hits) >= limit * 2:
                break
        elif n.get("content_path"):
            need_content.append(n)

    out = list(meta_hits)
    # content fallback only when meta is thin
    if q and len(out) < limit:
        content_budget = min(80, max(0, 40 + limit - len(out)))
        for n in need_content[:content_budget]:
            cpath = n.get("content_path")
            if not cpath:
                continue
            fp = BRAIN / cpath
            if not fp.exists():
                continue
            try:
                body = fp.read_text(encoding="utf-8", errors="ignore")[:6000].lower()
            except OSError:
                continue
            if q in body or (q_tokens and all(t in body for t in q_tokens)):
                out.append(n)
                if len(out) >= limit * 2:
                    break
    out.sort(
        key=lambda n: (
            TIER_ORDER.get(n.get("tier") or "T3", 9),
            n.get("updated_at") or "",
        )
    )
    return out[:limit]


def neighbors(
    node_id: str,
    hops: int = 1,
    *,
    edges: list[dict[str, Any]] | None = None,
    nodes_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """1-hop (or N-hop) neighborhood. Pass edges/nodes_by_id to avoid reloads in loops."""
    if edges is None:
        edges = load_all_edges()
    if nodes_by_id is None:
        nodes_by_id = {n["id"]: n for n in load_all_nodes()}
    frontier = {node_id}
    seen = set(frontier)
    collected_edges: list[dict[str, Any]] = []
    for _ in range(hops):
        nxt: set[str] = set()
        for e in edges:
            if e["src"] in frontier or e["dst"] in frontier:
                collected_edges.append(e)
                if e["src"] not in seen:
                    nxt.add(e["src"])
                    seen.add(e["src"])
                if e["dst"] not in seen:
                    nxt.add(e["dst"])
                    seen.add(e["dst"])
        frontier = nxt
    return {
        "seed": node_id,
        "nodes": [nodes_by_id[i] for i in seen if i in nodes_by_id],
        "edges": collected_edges,
    }


def status() -> dict[str, Any]:
    ensure_tree()
    nodes = load_all_nodes()
    edges = load_all_edges()
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for n in nodes:
        by_source[n.get("source") or "?"] = by_source.get(n.get("source") or "?", 0) + 1
        by_type[n.get("type") or "?"] = by_type.get(n.get("type") or "?", 0) + 1
        by_tier[n.get("tier") or "?"] = by_tier.get(n.get("tier") or "?", 0) + 1
    meta = read_json(BRAIN / "meta.json") if (BRAIN / "meta.json").exists() else {}
    cursors = (
        read_json(STATE_DIR / "cursors.json")
        if (STATE_DIR / "cursors.json").exists()
        else {}
    )
    return {
        "brain_root": str(resolve_brain_root()),
        "brain": str(BRAIN),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "by_source": by_source,
        "by_type": by_type,
        "by_tier": by_tier,
        "meta": meta,
        "cursors": cursors,
    }


def seed_demo() -> None:
    ensure_tree()
    if any(NODE_DIR.glob("*.json")):
        return
    g = write_node(
        "gitlab:group:1",
        type="Group",
        source="gitlab",
        title="platform",
        tier="T2",
        tags=["platform"],
        labels=["root-group"],
        uri="https://gitlab.example/platform",
    )
    sg = write_node(
        "gitlab:group:2",
        type="Subgroup",
        source="gitlab",
        title="payments",
        tier="T2",
        tags=["payments"],
        parent_id=g["id"],
        uri="https://gitlab.example/platform/payments",
    )
    write_edge(g["id"], "PARENT_OF", sg["id"])
    p = write_node(
        "gitlab:project:42",
        type="Project",
        source="gitlab",
        title="payments-api",
        tier="T2",
        tags=["payments", "backend"],
        labels=["service"],
        parent_id=sg["id"],
        uri="https://gitlab.example/platform/payments/payments-api",
        content="# payments-api\n\nCore payment orchestration service.\n",
    )
    write_edge(sg["id"], "CONTAINS", p["id"])
    repo = write_node(
        "gitlab:repo:42",
        type="Repo",
        source="gitlab",
        title="payments-api.git",
        tier="T2",
        tags=["payments"],
        parent_id=p["id"],
    )
    write_edge(p["id"], "CONTAINS", repo["id"])
    br = write_node(
        "gitlab:branch:42:main",
        type="Branch",
        source="gitlab",
        title="main",
        tier="T2",
        parent_id=repo["id"],
    )
    write_edge(repo["id"], "HAS_BRANCH", br["id"])
    mr = write_node(
        "gitlab:mr:42:88",
        type="MergeRequest",
        source="gitlab",
        title="PAY-441: circuit breaker on provider client",
        tier="T2",
        tags=["payments", "resilience"],
        parent_id=p["id"],
        content="## MR !88\n\nAdds circuit breaker around external provider calls.\n\nCloses PAY-441.\n",
    )
    write_edge(p["id"], "HAS_MR", mr["id"])
    cmt = write_node(
        "gitlab:mr_comment:42:88:1",
        type="MRComment",
        source="gitlab",
        title="LGTM after timeout tweak",
        tier="T3",
        parent_id=mr["id"],
        content="Looks good once timeout is 2s.",
    )
    write_edge(mr["id"], "HAS_COMMENT", cmt["id"])
    jp = write_node(
        "jira:project:PAY",
        type="JiraProject",
        source="jira",
        title="PAY",
        tier="T1",
        tags=["payments"],
    )
    issue = write_node(
        "jira:issue:PAY-441",
        type="Issue",
        source="jira",
        title="Add circuit breaker to provider client",
        tier="T1",
        tags=["payments", "resilience"],
        parent_id=jp["id"],
        content="As platform, we need resilience when provider X times out.",
        uri="https://jira.example/browse/PAY-441",
    )
    write_edge(jp["id"], "CONTAINS", issue["id"])
    write_edge(mr["id"], "IMPLEMENTS", issue["id"])
    write_edge(mr["id"], "REFERENCES", issue["id"])
    space = write_node(
        "confluence:space:ARCH",
        type="Space",
        source="confluence",
        title="Architecture",
        tier="T0",
        tags=["architecture"],
    )
    page = write_node(
        "confluence:page:90331",
        type="Page",
        source="confluence",
        title="Payments service resilience standard",
        tier="T0",
        tags=["payments", "resilience"],
        parent_id=space["id"],
        content="# Resilience standard\n\nAll external provider clients MUST use circuit breakers.\n",
        uri="https://confluence.example/spaces/ARCH/pages/90331",
    )
    write_edge(space["id"], "CONTAINS", page["id"])
    write_edge(page["id"], "DOCUMENTS", p["id"])
    write_edge(page["id"], "REFERENCES", issue["id"])
    build_snapshot()
