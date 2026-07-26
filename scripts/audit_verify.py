#!/usr/bin/env python3
"""Thin CLI: verify audit hash chain + secret scan."""
from __future__ import annotations

import json


def main() -> int:
    from audit_lib import scan_content_for_secrets, verify_chain

    v = verify_chain()
    print(json.dumps({"chain": v, "secret_scan_hits": len(scan_content_for_secrets())}, indent=2))
    return 0 if v.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
