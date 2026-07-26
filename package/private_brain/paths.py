"""Path resolution — one place, no guessing."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


@lru_cache(maxsize=1)
def codex_home() -> Path:
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]).expanduser().resolve()
    return (user_home() / ".codex").resolve()


@lru_cache(maxsize=1)
def brain_home() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser().resolve()
    return (codex_home() / "private-brain").resolve()


def brain_dir() -> Path:
    return brain_home() / ".brain"


def nodes_dir() -> Path:
    return brain_dir() / "nodes"


def edges_dir() -> Path:
    return brain_dir() / "edges"


def content_dir() -> Path:
    return brain_dir() / "content"


def chunks_dir() -> Path:
    return brain_dir() / "chunks"


def index_dir() -> Path:
    return brain_dir() / "index"


def embeddings_dir() -> Path:
    return index_dir() / "embeddings"


def graph_dir() -> Path:
    return brain_dir() / "graph"


def state_dir() -> Path:
    return brain_dir() / "state"


def audit_dir() -> Path:
    return brain_dir() / "audit"


def logs_dir() -> Path:
    return brain_dir() / "logs"


def sessions_dir() -> Path:
    """Corporate: %USERPROFILE%\\.codex\\sessions\\YYYY\\MM\\DD\\"""
    return codex_home() / "sessions"


def safe_id(node_id: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9._-]+", "_", node_id)
