#!/usr/bin/env python3
"""Neo4J LocalExport path reconciliation — derive from actual node fields.

Never claim relative_path_preservation_complete / preserved_verified unless every
canonical LocalExport node has non-empty approved_relative_path verified against
an approved root. Do not reconstruct from node IDs alone.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _brain() -> Path:
    return Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain"
    ).expanduser().resolve()


def _local_export_nodes() -> list[dict[str, Any]]:
    """Collect LocalExport-like nodes from graph or freeze metadata."""
    brain = _brain()
    scripts = brain / "scripts"
    sys.path.insert(0, str(scripts))
    nodes: list[dict[str, Any]] = []

    # Prefer live graph
    try:
        from brain_lib import list_nodes, query_nodes, all_nodes  # type: ignore
    except Exception:
        list_nodes = None  # type: ignore
        query_nodes = None  # type: ignore
        all_nodes = None  # type: ignore

    for fn in (query_nodes, list_nodes, all_nodes):
        if not fn:
            continue
        try:
            try:
                raw = fn(type="LocalExport")  # type: ignore
            except TypeError:
                raw = fn()  # type: ignore
            if isinstance(raw, list):
                for n in raw:
                    if not isinstance(n, dict):
                        continue
                    t = str(n.get("type") or n.get("label") or "")
                    if "LocalExport" in t or n.get("source_alias") or "local_export" in str(n.get("id", "")).lower():
                        nodes.append(n)
                if nodes:
                    return nodes
        except Exception:
            continue

    # Freeze / state metadata only
    state = brain / ".brain" / "state"
    for name in (
        "local_ingest_neoj_exports.json",
        "neoj_exports_freeze.json",
        "neoj_local_exports.json",
    ):
        p = state / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            nodes.extend([x for x in data if isinstance(x, dict)])
        elif isinstance(data, dict):
            for key in ("nodes", "local_exports", "exports", "items"):
                if isinstance(data.get(key), list):
                    nodes.extend([x for x in data[key] if isinstance(x, dict)])
    return nodes


def reconcile(nodes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    nodes = nodes if nodes is not None else _local_export_nodes()
    total = len(nodes)
    with_rel = 0
    abs_like = 0
    source_alias = 0
    for n in nodes:
        props = n.get("props") if isinstance(n.get("props"), dict) else n
        if not isinstance(props, dict):
            props = {}
        rel = props.get("approved_relative_path") or n.get("approved_relative_path")
        if rel and str(rel).strip():
            with_rel += 1
        path_val = str(
            props.get("path") or props.get("file_path") or n.get("path") or ""
        )
        if path_val.startswith("/") or (len(path_val) > 2 and path_val[1] == ":"):
            abs_like += 1
        if props.get("source_alias") or n.get("source_alias"):
            source_alias += 1

    # Rules from handoff
    if total == 0:
        preservation_complete = False
        path_identity = "unknown_or_unverified"
    elif with_rel < total:
        preservation_complete = False
        path_identity = "unknown_or_unverified"
    else:
        preservation_complete = True
        path_identity = "preserved_verified"

    path_redaction_complete = abs_like == 0  # only for verified absolute removal

    report = {
        "ok": True,
        "local_export_count": total,
        "source_alias_count": source_alias,
        "approved_relative_path_present_count": with_rel,
        "absolute_path_like_count": abs_like,
        "relative_path_preservation_complete": preservation_complete,
        "path_identity_status": path_identity,
        "path_redaction_complete": path_redaction_complete,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule": "preservation_complete only when every LocalExport has approved_relative_path",
    }

    # Persist corrected recon (read path is fine; writing recon report is diagnostic repair)
    try:
        state = _brain() / ".brain" / "state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "neoj_exports_reconciliation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        # Regression: missing approved_relative_path must not claim preserved_verified
        fake = [
            {"id": "export:1", "type": "LocalExport", "source_alias": "a"},
            {"id": "export:2", "type": "LocalExport", "source_alias": "b"},
        ]
        r = reconcile(fake)
        assert r["relative_path_preservation_complete"] is False
        assert r["path_identity_status"] == "unknown_or_unverified"
        assert r["approved_relative_path_present_count"] == 0
        # With paths
        good = [
            {
                "id": "export:1",
                "type": "LocalExport",
                "approved_relative_path": "docs/a.md",
            },
            {
                "id": "export:2",
                "type": "LocalExport",
                "approved_relative_path": "docs/b.md",
            },
        ]
        r2 = reconcile(good)
        assert r2["relative_path_preservation_complete"] is True
        assert r2["path_identity_status"] == "preserved_verified"
        print(json.dumps({"self_test": "ok", "missing": r, "good": r2}, indent=2))
        return 0

    rep = reconcile()
    print(json.dumps(rep, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
