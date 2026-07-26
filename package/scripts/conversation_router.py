#!/usr/bin/env python3
"""Pure conversation router — forensics + ops with zero human flags.

Returns additionalContext string for UserPromptSubmit hooks.
Executes scripts under PRIVATE_BRAIN_HOME via subprocess when needed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))


def _py() -> str:
    venv = _ROOT / "venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    venv = _ROOT / "venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return sys.executable


def _run(script: str, args: list[str] | None = None, timeout: int = 300) -> dict[str, Any]:
    cmd = [_py(), str(_SCRIPTS / script)] + (args or [])
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(_ROOT)
    env["PB_ENTERPRISE"] = "1"
    env["PYTHONPATH"] = str(_SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_ROOT),
            env=env,
        )
        out = (p.stdout or "")[-4000:]
        err = (p.stderr or "")[-1500:]
        return {"rc": p.returncode, "stdout": out, "stderr": err, "ok": p.returncode == 0}
    except Exception as e:
        return {"rc": -1, "stdout": "", "stderr": str(e), "ok": False}


def _heal_access_if_needed() -> str:
    """Ensure gpt-5.1 / codex can use system resources; ledger so we don't thrash."""
    notes = []
    try:
        from heal_ledger import record_access_repair, record_heal, should_heal
        from enterprise import ensure_enterprise_profile, self_heal
        from capabilities import self_repair

        if should_heal("enterprise_profile", "danger-full-access"):
            ensure_enterprise_profile()
            record_heal("enterprise_profile", "danger-full-access", actions=["ensure_enterprise_profile"])
            notes.append("enterprise profile → gpt-5.1 + danger-full-access")
        if should_heal("capabilities_repair", "optional_stack"):
            self_repair()
            record_heal("capabilities_repair", "optional_stack", actions=["self_repair"])
            notes.append("capabilities self_repair")
        if should_heal("full_heal", "chain_vectors"):
            h = self_heal()
            record_heal("full_heal", "chain_vectors", actions=(h or {}).get("actions") if isinstance(h, dict) else [])
            notes.append(f"self_heal actions={((h or {}) if isinstance(h, dict) else {})}")
            record_access_repair("full_heal_ok")
        return "Access repair: " + ("; ".join(notes) if notes else "ledger clean — no repeat heals")
    except Exception as e:
        return f"Access repair soft-fail: {e}"


def route(prompt: str) -> dict[str, Any] | None:
    """If prompt matches a conversational op, return hook payload pieces. Else None."""
    low = prompt.strip().lower()
    if len(low) < 3:
        return None

    # ── Forensics / ops (no flags) ──
    def pack(title: str, r: dict[str, Any], extra: str = "") -> dict[str, Any]:
        body = (r.get("stdout") or r.get("stderr") or "")[-3500:]
        return {
            "matched": True,
            "title": title,
            "context": f"{title}\nok={r.get('ok')} rc={r.get('rc')}\n{extra}\n\n{body}"[:16000],
            "system": title,
        }

    if any(x in low for x in ("fire drill", "firedrill", "scream test", "zero fail smoke", "airtight test")):
        return pack("FORENSICS · fire drill (conversational)", _run("fire_drill.py", timeout=400))

    if any(x in low for x in ("run doctor", "health check", "are we green", "are we ready", "doctor status")):
        # enterprise doctor via module
        r = _run("enterprise.py", ["doctor"], timeout=180)
        if not r.get("stdout") and not r.get("ok"):
            r = _run(
                "enterprise.py",
                [],
                timeout=30,
            )
            # fallback: python -c
            cmd = [
                _py(),
                "-c",
                "from enterprise import doctor_enterprise; import json; print(json.dumps(doctor_enterprise(), indent=2, default=str))",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(_SCRIPTS)
            env["PRIVATE_BRAIN_HOME"] = str(_ROOT)
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env, cwd=str(_ROOT))
                r = {"rc": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-1000:], "ok": p.returncode == 0}
            except Exception as e:
                r = {"rc": -1, "stdout": "", "stderr": str(e), "ok": False}
        return pack("FORENSICS · doctor (conversational)", r)

    if any(
        x in low
        for x in (
            "heal yourself",
            "self heal",
            "self-heal",
            "fix yourself",
            "repair access",
            "fix sandbox",
            "i can't access",
            "permission denied",
            "tools blocked",
        )
    ):
        note = _heal_access_if_needed()
        r = _run("enterprise.py", ["heal"], timeout=300)
        return pack("FORENSICS · heal (conversational, ledgered)", r, extra=note)

    if any(x in low for x in ("show metrics", "ops metrics", "scoreboard", "how healthy")):
        return pack("FORENSICS · ops metrics", _run("ops_metrics.py", timeout=120))

    if any(x in low for x in ("run mission", "monday gates", "mission monday", "local ready")):
        return pack("FORENSICS · mission gates", _run("mission_monday.py", timeout=300))

    if any(x in low for x in ("wake organism", "full wake", "water pipe", "spin up everything")):
        return pack("ORGANISM · full water pipe", _run("organism.py", ["--quiet"], timeout=600))

    if any(x in low for x in ("ingest sessions", "harvest sessions", "load my sessions")):
        cmd = [
            _py(),
            "-c",
            "from smart_discover import run_discover_ingest; import json; "
            "print(json.dumps(run_discover_ingest(max_files=5000, force=True, agent_id='conversation'), default=str))",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_SCRIPTS)
        env["PRIVATE_BRAIN_HOME"] = str(_ROOT)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=str(_ROOT))
            r = {"rc": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-1000:], "ok": p.returncode == 0}
        except Exception as e:
            r = {"rc": -1, "stdout": "", "stderr": str(e), "ok": False}
        return pack("LEARN · sessions ingest", r)

    if any(x in low for x in ("phase 2", "phase2", "handoff to grok", "talk to grok", "brief for grok", "parent ai")):
        try:
            from airgap_brief import write_brief
            from phase2_handoff import write_handoff

            b = write_brief()
            h = write_handoff()
            return {
                "matched": True,
                "title": "AIR-GAP · Phase-2 handoff for Grok",
                "context": (
                    "PHASE-2 HANDOFF ready for parent AI (Grok 4.5). No secrets.\n"
                    f"Day brief: {b.get('paths')}\n"
                    f"Handoff: {h.get('paths')}\n"
                    "Copy the MD files to the Grok machine. Pure offline planning.\n\n"
                    + (h.get("preview") or "")[:12000]
                ),
                "system": "Phase-2 handoff written",
            }
        except Exception as e:
            return {
                "matched": True,
                "title": "AIR-GAP handoff failed",
                "context": str(e),
                "system": "handoff fail",
            }

    if any(x in low for x in ("day brief", "end of day", "eod brief", "air gap brief", "airgap brief")):
        try:
            from airgap_brief import write_brief

            b = write_brief()
            return {
                "matched": True,
                "title": "AIR-GAP day brief",
                "context": f"Written: {b.get('paths')}\n\n{(b.get('compact') or '')}",
                "system": "day brief",
            }
        except Exception as e:
            return {"matched": True, "title": "brief fail", "context": str(e), "system": "fail"}

    # kingdom / api knowledge refresh
    if any(x in low for x in ("kingdom keys", "show apis", "how does corporate package index", "corporate_library api", "gitlab api")):
        keys = _ROOT / "docs" / "KINGDOM_KEYS.md"
        text = keys.read_text(encoding="utf-8")[:14000] if keys.exists() else "KINGDOM_KEYS.md missing"
        return {
            "matched": True,
            "title": "KINGDOM KEYS",
            "context": text,
            "system": "kingdom keys",
        }

    return None
