#!/usr/bin/env python3
"""Mock provider for local-rag CI/readiness — no network, one JSON."""
from __future__ import annotations

import json
import time


def complete(prompt: str, **kwargs) -> dict:
    return {
        "ok": True,
        "provider": "mock",
        "text": f"[mock] {prompt[:200]}",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    print(json.dumps(complete("ping")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
