#!/usr/bin/env python3
"""Minimal local-rag TUI entrypoint (read-only status + ask prompt)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    print("Private Brain local-rag TUI")
    print("Use: python cli/ask.py 'your question'")
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    readiness = codex / "local-rag" / "READINESS.json"
    if readiness.is_file():
        print(readiness.read_text(encoding="utf-8")[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
