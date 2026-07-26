#!/usr/bin/env python3
"""
Pluggable RAG backends for Private Brain.

Local (default): filesystem graph + TF-IDF vectors
Cloud (optional, gov-region-1 ready design):
  - graph: neptune | neptune-analytics | none
  - vectors: local | opensearch | neptune-analytics | pgvector
  - embeddings: local-tfidf | bedrock-titan

Config file: PRIVATE_BRAIN_HOME/config/backend.yaml
Env overrides:
  PB_GRAPH_BACKEND, PB_VECTOR_BACKEND, PB_EMBED_BACKEND
  PB_NEPTUNE_ENDPOINT, PB_OPENSEARCH_ENDPOINT
  PB_BEDROCK_REGION (default gov-region-1)
  AWS_PROFILE / AWS_REGION

This module does NOT require cloud deps at import time.
Cloud clients load lazily when configured.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


@dataclass
class BackendConfig:
    graph: str = "filesystem"  # filesystem | neptune | neptune-analytics
    vectors: str = "local"  # local | opensearch | neptune-analytics | pgvector
    embeddings: str = "local-tfidf"  # local-tfidf | bedrock-titan
    region: str = "gov-region-1"
    neptune_endpoint: str | None = None
    opensearch_endpoint: str | None = None
    opensearch_index: str = "private-brain-vectors"
    titan_model_id: str = "amazon.titan-embed-text-v2:0"
    # Hybrid: always keep filesystem as source-of-truth cache on laptop
    dual_write_filesystem: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _brain_root() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser()
    codex = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(codex) / "private-brain"


def load_backend_config() -> BackendConfig:
    cfg = BackendConfig()
    path = _brain_root() / "config" / "backend.yaml"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        data: dict[str, Any]
        if yaml:
            data = yaml.safe_load(text) or {}
        else:
            # minimal key: value parser
            data = {}
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip("\"'")
        for k, v in data.items():
            if hasattr(cfg, k) and v is not None:
                if k == "dual_write_filesystem":
                    setattr(cfg, k, str(v).lower() in ("1", "true", "yes"))
                else:
                    setattr(cfg, k, v)
    # env overrides
    cfg.graph = os.environ.get("PB_GRAPH_BACKEND", cfg.graph)
    cfg.vectors = os.environ.get("PB_VECTOR_BACKEND", cfg.vectors)
    cfg.embeddings = os.environ.get("PB_EMBED_BACKEND", cfg.embeddings)
    cfg.region = os.environ.get("PB_BEDROCK_REGION") or os.environ.get("AWS_REGION") or cfg.region
    cfg.neptune_endpoint = os.environ.get("PB_NEPTUNE_ENDPOINT") or cfg.neptune_endpoint
    cfg.opensearch_endpoint = os.environ.get("PB_OPENSEARCH_ENDPOINT") or cfg.opensearch_endpoint
    return cfg


def recommend_govcloud() -> dict[str, Any]:
    """Opinionated architecture for gov-region-1 GraphRAG."""
    return {
        "region": "gov-region-1",
        "recommendation": "hybrid",
        "summary": (
            "Do NOT use Neptune alone if you only need vector RAG. "
            "For Private Brain (relationship-heavy org knowledge), prefer: "
            "filesystem/local on laptop → sync graph to Neptune Database (or Neptune Analytics if GraphRAG+vectors in one engine) "
            "+ OpenSearch Service (k-NN) for Titan vectors + Bedrock Titan Embeddings in Government Cloud West when authorized. "
            "Self-hosted EC2 OpenSearch is a fallback when managed OpenSearch/Serverless features are limited by ATO."
        ),
        "tiers": {
            "laptop_edge": {
                "graph": "filesystem .brain/",
                "vectors": "local-tfidf (current) or offline embedding model",
                "why": "air-gap capable, works offline, feeds cloud later",
            },
            "govcloud_preferred": {
                "graph": "Amazon Neptune Database (property graph / openCypher) OR Neptune Analytics if vector+graph hybrid queries are required in one place",
                "vectors": "Amazon OpenSearch Service (managed cluster with k-NN) — best hybrid BM25+vector",
                "embeddings": "Amazon Bedrock Titan Text Embeddings (v2 if listed for your account in gov-region-1)",
                "why": "matches multi-hop org relationships + strong RAG retrieval; Titan/Bedrock have Government Cloud FedRAMP paths",
            },
            "govcloud_minimal": {
                "graph": "optional (skip if pure doc RAG)",
                "vectors": "OpenSearch k-NN only",
                "embeddings": "Bedrock Titan",
                "why": "simpler ops if graph hops are secondary",
            },
            "govcloud_single_engine_graph_rag": {
                "graph_and_vectors": "Neptune Analytics (graph + vector similarity)",
                "embeddings": "Bedrock Titan (import vectors)",
                "why": "one query surface for GraphRAG; confirm Neptune Analytics availability & limits in your Government Cloud partition before committing",
            },
            "ec2_self_hosted": {
                "when": "managed OpenSearch Serverless / Analytics not approved or feature-gated in gov-region-1",
                "what": "EC2/ASG OpenSearch 2.x/3.x with k-NN plugin + optional Gremlin/Neptune still managed",
                "cost": "you own patching, backups, Multi-AZ, IL4/5 hardening",
                "better_than_neptune_only_for_vectors": True,
            },
        },
        "not_recommended": [
            "Neptune Database alone as the vector store (classic Neptune is graph; vectors need Analytics or external store)",
            "Commercial multi-tenant vector SaaS outside Government Cloud for CUI/SAP-ish data",
            "Assuming every commercial-region toy exists in gov-region-1 without checking the service matrix for your account",
        ],
        "integration_with_private_brain": {
            "write_path": "ingest_bus → dual_write filesystem + optional Neptune openCypher UPSERT + OpenSearch bulk index",
            "read_path": "hybrid: OpenSearch kNN/BM25 seeds → Neptune 1–2 hop expand → tier/worth re-rank → context pack",
            "config": "config/backend.yaml + PB_* env vars",
        },
        "verify_in_account": [
            "Bedrock model list for gov-region-1 (Titan embed IDs)",
            "Neptune / Neptune Analytics service enablement",
            "OpenSearch Service (managed) vs Serverless availability",
            "VPC endpoints for Bedrock, Neptune, OpenSearch (no public internet)",
        ],
    }


def status() -> dict[str, Any]:
    cfg = load_backend_config()
    return {
        "active": cfg.to_dict(),
        "govcloud_guidance": recommend_govcloud(),
    }


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "recommend"])
    args = ap.parse_args()
    if args.cmd == "recommend":
        print(json.dumps(recommend_govcloud(), indent=2))
    else:
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
