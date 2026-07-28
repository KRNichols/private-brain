#!/usr/bin/env python3
"""Private Brain local-rag ask CLI — scoped retrieve + cited answer path.

Defaults to external runs root:
  %USERPROFILE%\\.codex\\local-rag-runtime\\runs\\
Never writes runtime state into installed code under local-rag/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser()


def _brain() -> Path:
    return Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or (_codex_home() / "private-brain")
    ).expanduser().resolve()


def _runs_root() -> Path:
    env = os.environ.get("PB_LOCAL_RAG_RUNS")
    if env:
        return Path(env).expanduser().resolve()
    return (_codex_home() / "local-rag-runtime" / "runs").resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description="local-rag ask (scoped graph retrieve)")
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--runs-root", default="")
    args = ap.parse_args()
    q = (args.question or "").strip()
    if not q and not sys.stdin.isatty():
        q = sys.stdin.read().strip()
    if not q:
        print("usage: ask.py 'question'", file=sys.stderr)
        return 2

    brain = _brain()
    scripts = brain / "scripts"
    sys.path.insert(0, str(scripts))
    os.environ["PRIVATE_BRAIN_HOME"] = str(brain)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    runs = Path(args.runs_root).expanduser() if args.runs_root else _runs_root()
    runs.mkdir(parents=True, exist_ok=True)
    run_id = f"ask-{uuid.uuid4().hex[:12]}"
    run_dir = runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    evidence = []
    context = ""
    ok = False
    err = None
    try:
        from orchestrate import dag_turn  # type: ignore

        res = dag_turn(q, allow_crawl=False) if True else {}
        try:
            res = dag_turn(q, allow_crawl=False)
        except TypeError:
            res = dag_turn(q)
        context = res.get("context") or ""
        evidence = (res.get("retrieve") or {}).get("evidence") or res.get("evidence") or []
        ok = True
    except Exception as e:
        err = str(e)[:300]

    report = {
        "run_id": run_id,
        "question": q[:2000],
        "ok": ok,
        "error": err,
        "evidence": evidence[:32],
        "context_chars": len(context or ""),
        "runs_root": str(runs),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (run_dir / "ask_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if context:
        (run_dir / "context.txt").write_text(context[:50000], encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"run_id={run_id} ok={ok} evidence={len(evidence)} runs={runs}")
        if context:
            print(context[:4000])
        if err:
            print(f"error: {err}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
