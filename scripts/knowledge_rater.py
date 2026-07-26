#!/usr/bin/env python3
"""
Knowledge-worth rater for cataloged nodes.

Scores 0.0–100.0 and writes props on node file:
  knowledge_worth, knowledge_band, rated_at

Bands: GOLD >= 75 · SILVER >= 55 · BRONZE >= 35 · SLAG < 35
"""

from __future__ import annotations

import json
from typing import Any

from audit_lib import audit
from brain_lib import (
    BRAIN,
    ensure_tree,
    load_all_edges,
    load_all_nodes,
    node_path,
    read_json,
    utc_now,
    write_json,
)


def _content_len(node: dict[str, Any]) -> int:
    cpath = node.get("content_path")
    if not cpath:
        return 0
    fp = BRAIN / cpath
    if fp.exists():
        try:
            return len(fp.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            return 0
    return 0


def score_node(node: dict[str, Any], edge_counts: dict[str, int] | None = None) -> dict[str, Any]:
    edge_counts = edge_counts or {}
    score = 0.0
    reasons: list[str] = []

    tier = node.get("tier") or "T3"
    tier_pts = {"T0": 35, "T1": 28, "T2": 20, "T3": 8}.get(tier, 8)
    score += tier_pts
    reasons.append(f"tier {tier} +{tier_pts}")

    src = node.get("source") or ""
    src_pts = {
        "confluence": 12,
        "jira": 10,
        "gitlab": 10,
        "codex_session": 6,
        "brain": 4,
    }.get(src, 5)
    score += src_pts
    reasons.append(f"source {src} +{src_pts}")

    clen = _content_len(node)
    if clen >= 4000:
        score += 15
        reasons.append("long content +15")
    elif clen >= 800:
        score += 10
        reasons.append("medium content +10")
    elif clen >= 120:
        score += 5
        reasons.append("short content +5")
    else:
        reasons.append("minimal content +0")

    tags = node.get("tags") or []
    score += min(8, len(tags) * 2)
    if tags:
        reasons.append(f"tags +{min(8, len(tags)*2)}")

    deg = edge_counts.get(node.get("id") or "", 0)
    link_pts = min(12, deg * 2)
    score += link_pts
    if deg:
        reasons.append(f"graph degree {deg} +{link_pts}")

    # Session-derived starts lower unless rich
    if src == "codex_session":
        score -= 5
        reasons.append("session-derived -5 (promote when linked/reused)")

    # Prefer non-chunk parent docs
    if node.get("type") == "BrainChunk":
        score -= 10
        reasons.append("chunk -10")

    score = max(0.0, min(100.0, score))
    if score >= 75:
        band = "GOLD"
    elif score >= 55:
        band = "SILVER"
    elif score >= 35:
        band = "BRONZE"
    else:
        band = "SLAG"

    return {
        "id": node.get("id"),
        "knowledge_worth": round(score, 2),
        "knowledge_band": band,
        "reasons": reasons,
        "content_len": clen,
        "degree": deg,
    }


def rate_all(limit: int | None = None, persist: bool = True) -> dict[str, Any]:
    ensure_tree()
    nodes = load_all_nodes()
    edges = load_all_edges()
    deg: dict[str, int] = {}
    for e in edges:
        deg[e["src"]] = deg.get(e["src"], 0) + 1
        deg[e["dst"]] = deg.get(e["dst"], 0) + 1

    if limit:
        nodes = nodes[:limit]
    results = []
    bands = {"GOLD": 0, "SILVER": 0, "BRONZE": 0, "SLAG": 0}
    for n in nodes:
        r = score_node(n, deg)
        results.append(r)
        bands[r["knowledge_band"]] = bands.get(r["knowledge_band"], 0) + 1
        if persist:
            try:
                path = node_path(n["id"])
                if path.exists():
                    obj = read_json(path)
                    obj["knowledge_worth"] = r["knowledge_worth"]
                    obj["knowledge_band"] = r["knowledge_band"]
                    obj["rated_at"] = utc_now()
                    write_json(path, obj)
            except Exception:
                pass

    results.sort(key=lambda x: x["knowledge_worth"], reverse=True)
    out = {
        "rated": len(results),
        "bands": bands,
        "top": results[:25],
        "avg": round(sum(r["knowledge_worth"] for r in results) / max(1, len(results)), 2),
    }
    audit(
        "knowledge_rate",
        agent_id="knowledge_rater",
        role="rater",
        result="ok",
        detail=f"rated={out['rated']} avg={out['avg']}",
        props=bands,
    )
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args()
    print(json.dumps(rate_all(limit=args.limit, persist=not args.no_persist), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
