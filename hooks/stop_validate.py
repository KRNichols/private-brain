#!/usr/bin/env python3
"""Codex Stop hook — force one more pass if answer ignored brain evidence.

Codex 0.144.x Stop stdout contract (strict):
  Allowed keys only: continue, decision, reason, systemMessage, stopReason, suppressOutput.
  Unsupported fields (e.g. hookSpecificOutput) → "invalid stop hook JSON" on Windows/CLI.
  Exit 0 always with pure JSON on stdout. Never print logs/tracebacks to stdout.
"""
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


def _emit(obj: dict) -> int:
    """Write minimal Codex-legal Stop JSON. Strip unknown keys hard."""
    allowed = {"continue", "decision", "reason", "systemMessage", "stopReason", "suppressOutput"}
    clean = {k: v for k, v in obj.items() if k in allowed}
    # Prefer decision/block OR continue — never both (Codex can reject mixed shapes)
    if clean.get("decision") == "block":
        clean.pop("continue", None)
        if "reason" not in clean:
            clean["reason"] = "Private Brain: rewrite with evidence cites."
    else:
        clean = {"continue": True}
    try:
        sys.stdout.write(json.dumps(clean, ensure_ascii=True, separators=(",", ":")))
        sys.stdout.flush()
    except Exception:
        # Last-resort legal payload
        sys.stdout.write('{"continue":true}')
        try:
            sys.stdout.flush()
        except Exception:
            pass
    return 0


def main() -> int:
    # Windows: stdin may be cp1252 / partial; never explode
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace") if hasattr(sys.stdin, "buffer") else sys.stdin.read()
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    # If already continued once, do not loop forever
    if payload.get("stop_hook_active"):
        return _emit({"continue": True})

    last = payload.get("last_assistant_message") or ""
    if not isinstance(last, str):
        last = str(last or "")

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
            return _emit({"continue": True})

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
                return _emit({
                    "decision": "block",
                    "reason": (
                        f"Private Brain ENTERPRISE: citation gate unavailable ({e}). "
                        "Refuse ungrounded answer."
                    ),
                })
            return _emit({"continue": True})

        gate = citation_gate(last, evidence)
        if not gate.get("ok"):
            ids = ", ".join(
                f"`{e.get('id')}` ({e.get('tier')})" for e in evidence[:6] if e.get("id")
            ) or "(no graph evidence — refuse or crawl)"
            mode = "ENTERPRISE" if is_enterprise() else "validator"
            return _emit({
                "decision": "block",
                "reason": (
                    f"Private Brain {mode}: {gate.get('reason')}. "
                    f"Rewrite with `node_id` cites from: {ids}. "
                    "Never ask permission. Answer from the DAG only."
                ),
            })
        return _emit({"continue": True})
    except Exception as e:
        # Enterprise fail-closed on unexpected errors
        try:
            from brain_lib import STATE_DIR as SD
            if (SD / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
                return _emit({
                    "decision": "block",
                    "reason": f"Private Brain ENTERPRISE: stop validator error — refuse ({e}).",
                })
        except Exception:
            pass
        return _emit({"continue": True})


if __name__ == "__main__":
    raise SystemExit(main())
