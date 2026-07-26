# Contributing

1. Fork and PR against `main`.
2. Keep secrets out of the tree (no `.env`, no corpus dumps).
3. CI must stay green on **Ubuntu**, **Windows**, and **macOS**.
4. Prefer real results: nuclear gate + first-boot smokes over agent-count metrics.

## Local checks

```bash
PB_ENTERPRISE=1 python scripts/nuclear_x10.py
# or
PB_ENTERPRISE=1 python scripts/nuclear_zero_fail.py
```

Corporate Library = approved package index. Protected Gateway = proxied package gateway.  
Use generic names in docs; do not commit employer-specific branding.
