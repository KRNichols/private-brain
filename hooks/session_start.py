#!/usr/bin/env python3
"""Codex SessionStart hook — fires Private Brain DAG boot and injects context."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Resolve brain home
HOME = Path.home()
BRAIN_HOME = Path(
    os.environ.get("PRIVATE_BRAIN_HOME")
    or os.environ.get("CODEX_HOME", str(HOME / ".codex")) + "/private-brain"
)
if not BRAIN_HOME.is_absolute():
    BRAIN_HOME = (HOME / ".codex" / "private-brain").resolve()
else:
    BRAIN_HOME = BRAIN_HOME.resolve()

SCRIPTS = BRAIN_HOME / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["PRIVATE_BRAIN_HOME"] = str(BRAIN_HOME)
os.environ["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", "")

def main() -> int:
    raw = sys.stdin.read()
    # Codex may send a JSON payload on stdin; SessionStart only needs boot, not fields.
    try:
        if raw.strip():
            json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        # Incremental session learning every Codex session (self-learning)
        try:
            from smart_discover import run_discover_ingest

            run_discover_ingest(max_files=200, force=False, agent_id="session-start-harvest")
        except Exception:
            pass

        from orchestrate import dag_boot

        res = dag_boot()
        ctx = res.get("context") or "Private Brain boot complete."
        # Never-forget second mind — compact identity + active project only
        mind = ""
        try:
            from second_mind import boot_context

            mind = "\n\n" + boot_context(max_chars=2500)
        except Exception as mind_err:
            mind = f"\n\n(second mind brief unavailable: {mind_err})"
        # GOLDEN CONFIG + KINGDOM KEYS — complete Corporate surface + APIs + conversational law
        golden = ""
        try:
            from golden_config import load_compact_for_inject

            golden = "\n\n" + load_compact_for_inject(max_chars=7000)
        except Exception as g_err:
            golden = f"\n\n(golden config unavailable: {g_err})"
        kingdom = ""
        try:
            kk = BRAIN_HOME / "docs" / "KINGDOM_KEYS.md"
            if kk.exists():
                # inject core of kingdom keys (APIs + conversation surface)
                kingdom = "\n\n" + kk.read_text(encoding="utf-8")[:9000]
        except Exception:
            pass
        # ledgered access assert (no thrash)
        try:
            from conversation_router import _heal_access_if_needed

            _heal_access_if_needed()
        except Exception:
            pass
        # Product law: every NEW Codex open (startup|resume|clear) = BEAST ON.
        # User can say "stop beast mode" / "normal mode" mid-session → RAG off until reopen.
        # They never need a shell beastMode launcher for daily use — hooks ARE the sideload.
        state = BRAIN_HOME / ".brain" / "state"
        state.mkdir(parents=True, exist_ok=True)
        try:
            import datetime as _dt

            (state / "conversation_mode.json").write_text(
                json.dumps(
                    {
                        "mode": "beast",
                        "ts": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "reason": "session_start_auto_beast",
                    }
                ),
                encoding="utf-8",
            )
            (state / "beastmode.on").write_text("1\n", encoding="utf-8")
            (state / "enterprise.on").write_text("1\n", encoding="utf-8")
            rag_off = state / "rag.off"
            if rag_off.exists():
                try:
                    rag_off.unlink()
                except OSError:
                    pass
        except Exception:
            pass
        # Pending pilot scenarios (hosts/tokens/index/AWS/sessions/GodsEye) — heal→ask→synthesize
        ingest_sc = ""
        try:
            from scenario_heal import conversation_inject, synthesize_all

            # Light scan on session open (no network) — write pending if high gaps
            synthesize_all(reason="session_start_gap_scan")
            inj = conversation_inject()
            if inj.strip():
                ingest_sc = "\n\n" + inj
        except Exception:
            try:
                from ingest_scenario import conversation_inject as _ic

                inj = _ic()
                if inj.strip():
                    ingest_sc = "\n\n" + inj
            except Exception:
                pass
        extra = (
            ctx
            + golden
            + kingdom
            + mind
            + ingest_sc
            + "\n\nBEAST MODE ACTIVE (auto on every Codex open). "
            "Human manages Private Brain by conversation only — no shell parade. "
            "Never ask permission for tool use — but DO ask once for missing internal GitLab/Jira/Confluence URLs "
            "when pending_ingest_scenario is active (heal from state first; never invent hosts). "
            "ZERO FLAGS: fire drill, doctor, heal, metrics, day brief, phase 2 handoff, show GodsEye. "
            "GOLDEN CONFIG + KINGDOM KEYS are law for hosts/APIs/AWS when present. "
            "Cite node_ids while beast is on. "
            "If user says stop beast mode / normal mode / turn off RAG → plain Codex until THIS session ends. "
            "Next Codex open re-enables beast automatically. "
            f"PRIVATE_BRAIN_HOME={BRAIN_HOME}"
        )
        nodes = res.get("boot", {}).get("nodes")
        inject = extra[:28000] if len(extra) > 28000 else extra
        out = {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": inject,
            },
            "systemMessage": f"Private Brain · BEAST on · nodes={nodes} · talk only (stop beast mode to pause)",
        }
        sys.stdout.write(json.dumps(out))
        return 0
    except Exception as e:
        # Never block session
        msg = f"Private Brain boot error (non-fatal): {e}"
        sys.stdout.write(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": msg
                        + f"\nRun: {BRAIN_HOME}/venv/bin/python3 {SCRIPTS}/orchestrate.py boot",
                    },
                    "systemMessage": msg,
                }
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
