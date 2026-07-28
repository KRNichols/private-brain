#!/usr/bin/env python3
"""Dashboard entry — consumes godseye/product readiness JSON, no state guesses."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    brain = Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain"
    )
    ge = brain / "scripts" / "godseye.py"
    out = {"godseye": None, "product": None}
    if ge.is_file():
        try:
            r = subprocess.run(
                [sys.executable, str(ge), "status", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            out["godseye"] = json.loads(r.stdout or "{}")
        except Exception as e:
            out["godseye"] = {"error": str(e)[:200]}
    pr = brain / "scripts" / "product_readiness.py"
    if pr.is_file():
        try:
            r = subprocess.run(
                [sys.executable, str(pr)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            out["product"] = json.loads(r.stdout or "{}")
        except Exception as e:
            out["product"] = {"error": str(e)[:200]}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
