#!/usr/bin/env python3
"""Re-chunk Confluence Page nodes that have stored content but empty chunk_ids.

Bounded, offline: reads local content files only — no remote API.
Safe to run from background deferred work or beastMode --heal (not from UPS).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-id", default="", help="e.g. confluence:page:633240886")
    ap.add_argument("--all-empty", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    brain = Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain"
    ).expanduser().resolve()
    scripts = brain / "scripts"
    sys.path.insert(0, str(scripts))
    os.environ["PRIVATE_BRAIN_HOME"] = str(brain)

    from brain_lib import (  # type: ignore
        CONTENT_DIR,
        node_path,
        read_json,
        write_node,
        NODE_DIR,
    )

    targets: list[str] = []
    if args.page_id:
        targets = [args.page_id]
    elif args.all_empty:
        for p in NODE_DIR.glob("*.json"):
            try:
                n = read_json(p)
            except Exception:
                continue
            if not isinstance(n, dict):
                continue
            if n.get("type") != "Page" and not str(n.get("id", "")).startswith("confluence:page:"):
                continue
            cids = n.get("chunk_ids") or []
            if cids:
                continue
            if n.get("content_path") or (CONTENT_DIR / f"{p.stem}.md").exists():
                targets.append(str(n.get("id")))
    else:
        print("usage: --page-id ID | --all-empty", file=sys.stderr)
        return 2

    results = []
    for pid in targets:
        np = node_path(pid)
        if not np.is_file():
            results.append({"id": pid, "ok": False, "reason": "missing_node"})
            continue
        node = read_json(np) or {}
        content = ""
        cp = node.get("content_path")
        if cp:
            # content_path is relative under .brain
            cand = brain / ".brain" / cp
            if not cand.is_file():
                cand = CONTENT_DIR / Path(cp).name
            if cand.is_file():
                content = cand.read_text(encoding="utf-8", errors="replace")
        if not content:
            md = CONTENT_DIR / f"{np.stem}.md"
            if md.is_file():
                content = md.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            results.append({"id": pid, "ok": False, "reason": "no_content"})
            continue
        updated = write_node(
            pid,
            type=node.get("type") or "Page",
            source=node.get("source") or "confluence",
            title=node.get("title") or pid,
            tier=node.get("tier") or "T0",
            uri=node.get("uri"),
            tags=node.get("tags") or [],
            labels=node.get("labels") or [],
            parent_id=node.get("parent_id"),
            content=content,
            props=node.get("props") or {},
            created_at=node.get("created_at"),
            chunk=True,
        )
        results.append(
            {
                "id": pid,
                "ok": True,
                "chunk_count": len(updated.get("chunk_ids") or []),
                "chunk_ids": updated.get("chunk_ids") or [],
            }
        )

    out = {
        "ok": all(r.get("ok") for r in results) if results else False,
        "pages": results,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] or not results else 1


if __name__ == "__main__":
    raise SystemExit(main())
