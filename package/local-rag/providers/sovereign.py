#!/usr/bin/env python3
"""Sovereign provider shim — routes to enterprise-approved model endpoints only."""
from __future__ import annotations

import json
import os
import time


def complete(prompt: str, **kwargs) -> dict:
    model = os.environ.get("PB_EDGE_MODEL") or os.environ.get("PB_SOVEREIGN_MODEL") or "gpt-5.1"
    # No unrestricted filesystem / secrets exposure
    return {
        "ok": True,
        "provider": "sovereign",
        "model": model,
        "text": "",
        "note": "wire to approved enterprise endpoint; mock-safe when PB_LOCAL_RAG_MOCK=1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    print(json.dumps(complete("ping")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
