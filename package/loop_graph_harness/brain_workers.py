"""Brain-aware loop workers — gather graph/vector slices in CHILD context only.

Each spawn gets a narrow material payload (a query slice or source tag). The
worker may call brain_lib / vector_manager inside its own window and returns a
small evidence pack. Parent never sees full node JSON — only the pack.

This is the production bridge from the duration demo to Private Brain RAG-DAG.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .harness import Context
from .loop import Report, run_loop


def _safe_query(token: str, limit: int = 6) -> list[dict[str, Any]]:
    try:
        from brain_lib import query  # type: ignore

        hits = query(token, limit=limit) or []
        out = []
        for h in hits:
            if not isinstance(h, dict):
                continue
            out.append(
                {
                    "id": str(h.get("id") or h.get("node_id") or "")[:80],
                    "type": str(h.get("type") or h.get("node_type") or "")[:40],
                    "tier": str(h.get("tier") or h.get("knowledge_tier") or "")[:8],
                    "source": str(h.get("source") or "")[:40],
                    "score": float(h.get("score") or h.get("rank") or 0.0),
                    "title": str(h.get("title") or h.get("label") or "")[:120],
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        return [{"id": "", "error": f"query:{type(exc).__name__}:{exc}"}]


def _safe_vector(token: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        from vector_manager import search_vectors  # type: ignore

        hits = search_vectors(token, limit=limit) or []
        out = []
        for h in hits:
            if isinstance(h, dict):
                out.append(
                    {
                        "id": str(h.get("id") or h.get("node_id") or "")[:80],
                        "score": float(h.get("score") or 0.0),
                        "snippet": str(h.get("text") or h.get("snippet") or "")[:160],
                    }
                )
            elif isinstance(h, (list, tuple)) and len(h) >= 2:
                out.append({"id": str(h[0])[:80], "score": float(h[1]), "snippet": ""})
        return out
    except Exception as exc:  # noqa: BLE001
        return [{"id": "", "error": f"vector:{type(exc).__name__}:{exc}"}]


def brain_slice_worker(ctx: Context, tools: dict, task: str, material: str) -> dict:
    """Loop-worker over one token/slice of a user prompt against the brain.

    material: JSON or plain token string describing the slice.
    Returns tiny dict: {token, hits, top_ids, ok, attempts}.
    """
    try:
        payload = json.loads(material) if material.strip().startswith("{") else {"token": material.strip()}
    except Exception:
        payload = {"token": material.strip()}

    token = str(payload.get("token") or task.split(":")[-1]).strip() or "status"
    limit = int(payload.get("limit") or 6)
    ctx.add(f"slice token={token!r} limit={limit}")

    def verify(candidate: dict) -> Report:
        fails: list[str] = []
        if candidate.get("error"):
            fails.append(str(candidate["error"]))
        if not isinstance(candidate.get("hits"), list):
            fails.append("hits not a list")
        # Allow empty hits (gap is valid knowledge) but require structure
        if "token" not in candidate:
            fails.append("missing token")
        if candidate.get("ok") is False and not candidate.get("error"):
            fails.append("ok=false without error")
        return Report(not fails, fails)

    def act(sheet: str, prior_failures: list[str]) -> dict:
        # Attempt 1: graph query. Attempt 2+: add vectors if empty/failed.
        try:
            hits = _safe_query(token, limit=limit)
            if prior_failures or not hits or (hits and hits[0].get("error")):
                vec = _safe_vector(token, limit=max(3, limit // 2))
                # merge by id
                seen = {h.get("id") for h in hits if h.get("id")}
                for v in vec:
                    if v.get("id") and v["id"] not in seen:
                        hits.append(v)
                        seen.add(v["id"])
            # strip error-only rows if we recovered
            clean = [h for h in hits if h.get("id") and not h.get("error")]
            if not clean and hits and hits[0].get("error") and not prior_failures:
                # force retry path
                return {
                    "token": token,
                    "hits": [],
                    "top_ids": [],
                    "ok": False,
                    "error": hits[0].get("error", "empty"),
                }
            top_ids = [h["id"] for h in clean[:5] if h.get("id")]
            return {
                "token": token,
                "hits": clean[:limit],
                "top_ids": top_ids,
                "n_hits": len(clean),
                "ok": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "token": token,
                "hits": [],
                "top_ids": [],
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    result = run_loop(material, act, verify, max_attempts=3)
    if not result.accepted:
        return {
            "token": token,
            "hits": [],
            "top_ids": [],
            "n_hits": 0,
            "attempts": result.attempts,
            "ok": False,
            "log": result.log,
        }
    val = result.value if isinstance(result.value, dict) else {}
    return {
        "token": token,
        "hits": val.get("hits") or [],
        "top_ids": val.get("top_ids") or [],
        "n_hits": int(val.get("n_hits") or 0),
        "attempts": result.attempts,
        "ok": True,
    }


def tokenize_prompt(prompt: str, n: int = 4) -> list[str]:
    toks = [t for t in re.split(r"[^\w]+", prompt.lower()) if len(t) > 2]
    seen: set[str] = set()
    out: list[str] = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        out = ["status", "graph", "knowledge"]
    if len(out) < n:
        out = (out * ((n // len(out)) + 1))[:n]
    return out[:n]


def brain_evidence_rules(artifact: dict) -> list[str]:
    """Adversarial rules for a merged evidence pack — no loyalty to workers."""
    bad: list[str] = []
    if not isinstance(artifact, dict):
        return ["artifact not a dict"]
    if int(artifact.get("slices") or 0) <= 0:
        bad.append("no slices")
    if int(artifact.get("slices_ok") or 0) < 0:
        bad.append("negative slices_ok")
    # Structure required even when graph is empty
    if "unique_ids" not in artifact:
        bad.append("missing unique_ids")
    if not isinstance(artifact.get("unique_ids"), list):
        bad.append("unique_ids not a list")
    return bad
