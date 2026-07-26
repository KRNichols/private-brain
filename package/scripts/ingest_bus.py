#!/usr/bin/env python3
"""
Unified ingest bus — nothing that passes through is dropped.

write → node/edge files → chunks → vector index → knowledge rate stamp → audit
"""

from __future__ import annotations

from typing import Any

from audit_lib import audit
from brain_lib import (
    ensure_tree,
    node_path,
    read_json,
    utc_now,
    write_edge,
    write_json,
    write_node,
)
from knowledge_rater import score_node
from vector_manager import upsert_vector


def ingest_node(
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
    agent_id: str = "ingest_bus",
    role: str = "db_manager",
) -> dict[str, Any]:
    ensure_tree()
    tags = list(tags or [])
    if "cataloged" not in tags:
        tags.append("cataloged")
    # Enterprise stamp: classification + program_id on every write
    try:
        from enterprise import is_enterprise, stamp_props

        if is_enterprise():
            props = stamp_props(props)
            if "enterprise" not in tags:
                tags.append("enterprise")
    except Exception:
        props = props or {}
    node = write_node(
        node_id,
        type=type,
        source=source,
        title=title,
        tier=tier,
        uri=uri,
        tags=tags,
        labels=labels,
        parent_id=parent_id,
        content=content,
        props=props or {},
    )
    # vectorize
    try:
        v = upsert_vector(node_id, node=node)
    except Exception as e:
        v = {"error": str(e)[:200]}
    # knowledge worth
    try:
        worth = score_node(node)
        path = node_path(node_id)
        if path.exists():
            obj = read_json(path)
            obj["knowledge_worth"] = worth["knowledge_worth"]
            obj["knowledge_band"] = worth["knowledge_band"]
            obj["rated_at"] = utc_now()
            write_json(path, obj)
            node = obj
    except Exception as e:
        worth = {"error": str(e)[:200]}

    audit(
        "ingest",
        agent_id=agent_id,
        role=role,
        object_id=node_id,
        result="ok",
        detail=f"type={type} source={source}",
        props={
            "vector_dims": (v or {}).get("dims"),
            "worth": (worth or {}).get("knowledge_worth"),
            "band": (worth or {}).get("knowledge_band"),
        },
    )
    return {
        "node": {"id": node_id, "tier": tier, "type": type, "source": source},
        "vector": v,
        "worth": worth,
    }


def ingest_edge(src: str, rel: str, dst: str, agent_id: str = "ingest_bus") -> dict:
    e = write_edge(src, rel, dst)
    audit("ingest_edge", agent_id=agent_id, role="db_manager", object_id=e["id"], result="ok", detail=rel)
    return e
