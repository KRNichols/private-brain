#!/usr/bin/env python3
"""Init filesystem brain tree + optional demo seed."""
from __future__ import annotations

import json

from brain_lib import build_snapshot, ensure_tree, status


def main() -> int:
    ensure_tree()
    try:
        from brain_lib import seed_demo
        seed_demo()
    except Exception:
        pass
    build_snapshot()
    print(json.dumps(status(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
