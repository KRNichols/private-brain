#!/usr/bin/env python3
"""Codex Stop hook — force one more pass if answer ignored brain evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOME = Path.home()
BRAIN_HOME = Path(
    os.environ.get("PRIVATE_BRAIN_HOME")
    or str(Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "private-brain")
).resolve()
SCRIPTS = BRAIN_HOME / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["PRIVATE_BRAIN_HOME"] = str(BRAIN_HOME)

# Enterprise flag file survives exec into codex if env was set by beastMode
_flag = BRAIN_HOME / ".brain" / "state" / "enterprise.on"
if _flag.exists() and not os.environ.get("PB_ENTERPRISE"):
    os.environ["PB_ENTERPRISE"] = "1"


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    # If already continued once, do not loop forever
    if payload.get("stop_hook_active"):
        sys.stdout.write(json.dumps({"continue": True}))
        return 0

    last = payload.get("last_assistant_message") or ""
    try:
        from brain_lib import STATE_DIR, read_json

        # NORMAL mode: no cite gate — plain Codex
        rag_off = (STATE_DIR / "rag.off").exists()
        mode_path = STATE_DIR / "conversation_mode.json"
        if mode_path.exists():
            try:
                if json.loads(mode_path.read_text(encoding="utf-8")).get("mode") == "normal":
                    rag_off = True
            except Exception:
                pass
        if rag_off:
            sys.stdout.write(json.dumps({"continue": True}))
            return 0

        last_dag = {}
        p = STATE_DIR / "last_dag.json"
        if p.exists():
            last_dag = read_json(p)
        # Elevate enterprise flag → env so citation_gate is hard
        if (STATE_DIR / "enterprise.on").exists():
            os.environ["PB_ENTERPRISE"] = "1"

        evidence = (last_dag.get("retrieve") or {}).get("evidence") or []
        # Enterprise fail-closed: no evidence → refuse free-form claims
        try:
            from enterprise import citation_gate, is_enterprise
        except Exception as e:
            if (STATE_DIR / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
                sys.stdout.write(json.dumps({
                    "decision": "block",
                    "reason": f"Private Brain ENTERPRISE: citation gate unavailable ({e}). Refuse ungrounded answer.",
                }))
                return 0
            sys.stdout.write(json.dumps({"continue": True}))
            return 0

        gate = citation_gate(last, evidence)
        if not gate.get("ok"):
            ids = ", ".join(
                f"`{e.get('id')}` ({e.get('tier')})" for e in evidence[:6] if e.get("id")
            ) or "(no graph evidence — refuse or crawl)"
            mode = "ENTERPRISE" if is_enterprise() else "validator"
            sys.stdout.write(json.dumps({
                "decision": "block",
                "reason": (
                    f"Private Brain {mode}: {gate.get('reason')}. "
                    f"Rewrite with `node_id` cites from: {ids}. "
                    "Never ask permission. Answer from the DAG only."
                ),
            }))
            return 0
        sys.stdout.write(json.dumps({"continue": True}))
        return 0
    except Exception as e:
        # Enterprise fail-closed on unexpected errors
        try:
            from brain_lib import STATE_DIR as SD
            if (SD / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
                sys.stdout.write(json.dumps({
                    "decision": "block",
                    "reason": f"Private Brain ENTERPRISE: stop validator error — refuse ({e}).",
                }))
                return 0
        except Exception:
            pass
        sys.stdout.write(json.dumps({"continue": True}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
