#!/usr/bin/env python3
"""Codex UserPromptSubmit — natural-language mode control + compact RAG inject.

Product model:
  Install once (hooks sideloaded). Open Codex. Talk. No daily shell launcher required.
  Every SessionStart forces BEAST on. Mid-session user can pause; reopen re-enables.

Conversation (no flags):
  "stop beast mode" / "normal mode" / "turn off rag"  → RAG-DAG OFF (this session)
  "beast mode" / "enterprise mode" / "turn on rag"     → RAG-DAG ON again

When RAG off: no retrieve inject, no cite hard-gate (Stop hook also checks mode).
When RAG on: compact local retrieve only — never remote API/page fetch/graph write/
chunk/vector/snapshot work synchronously (developer handoff 2026-07-28).
Budget: materially under Codex 180s UPS timeout (default 25s wall).
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

HOME = Path.home()
BRAIN_HOME = Path(
    os.environ.get("PRIVATE_BRAIN_HOME")
    or str(Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "private-brain")
).resolve()
SCRIPTS = BRAIN_HOME / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["PRIVATE_BRAIN_HOME"] = str(BRAIN_HOME)
os.environ["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", "")

STATE = BRAIN_HOME / ".brain" / "state"
MODE_FILE = STATE / "conversation_mode.json"  # {"mode": "beast"|"normal"}
UPS_BUDGET_SEC = float(os.environ.get("PB_UPS_BUDGET", "25") or "25")


def _mode() -> str:
    try:
        if MODE_FILE.exists():
            d = json.loads(MODE_FILE.read_text(encoding="utf-8"))
            m = str(d.get("mode") or "beast").lower()
            if m in ("normal", "plain", "off"):
                return "normal"
            return "beast"
    except Exception:
        pass
    # default beast when enterprise flag present
    if (STATE / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
        return "beast"
    return "beast"


def _set_mode(mode: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(
        json.dumps({"mode": mode, "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z"}),
        encoding="utf-8",
    )
    # stop hook + other processes
    if mode == "normal":
        (STATE / "rag.off").write_text("1\n", encoding="utf-8")
    else:
        p = STATE / "rag.off"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        (STATE / "enterprise.on").write_text("1\n", encoding="utf-8")
        (STATE / "beastmode.on").write_text("1\n", encoding="utf-8")


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    prompt = payload.get("prompt") or ""
    if len(prompt.strip()) < 2:
        sys.stdout.write(json.dumps({"continue": True}))
        return 0

    low = prompt.strip().lower()

    # ── Natural conversation: mode switches (zero flags) ──
    normal_phrases = (
        "normal mode",
        "plain codex",
        "plain mode",
        "turn off rag",
        "turn off the rag",
        "disable rag",
        "rag off",
        "no beast",
        "exit beast",
        "vanilla codex",
        "stop beast mode",
        "stop beastmode",
        "stop beast",
        "turn off beast mode",
        "turn off beastmode",
        "disable beast mode",
        "disable beastmode",
        "end beast mode",
        "pause private brain",
        "private brain off",
        "sideload off",
    )
    beast_phrases = (
        "beast mode",
        "enterprise mode",
        "turn on rag",
        "enable rag",
        "rag on",
        "reactivate beast",
        "private brain on",
        "sideload on",
        "start beast mode",
        "resume beast mode",
        "enable beast mode",
    )
    if any(p in low for p in normal_phrases):
        _set_mode("normal")
        sys.stdout.write(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": (
                            "MODE=NORMAL. RAG-DAG is OFF for this session only. "
                            "No retrieve inject. No cite gate. You are plain Codex. "
                            "Do not invent Private Brain evidence. "
                            "Say 'beast mode' to turn RAG back on now. "
                            "When the user reopens Codex (new session), beast re-enables automatically."
                        ),
                    },
                    "systemMessage": "Private Brain: NORMAL — RAG off this session (reopen Codex → beast on)",
                }
            )
        )
        return 0

    if any(p in low for p in beast_phrases):
        _set_mode("beast")
        g = ""
        try:
            from golden_config import load_compact_for_inject

            g = load_compact_for_inject(max_chars=600)
        except Exception:
            g = ""
        # Do NOT run heal_access (remote) synchronously — ledger only if instant file read
        acc = ""
        sys.stdout.write(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": (
                            "MODE=BEAST. RAG-DAG reactivated. Full system access + evidence cites required.\n"
                            f"{acc}\n"
                            + g
                        )[:2500],
                    },
                    "systemMessage": "Private Brain: BEAST mode — RAG-DAG on",
                }
            )
        )
        return 0

    # Conversational forensics / ops / phase-2 handoff (zero flags)
    if _mode() != "normal":
        try:
            from conversation_router import route as conv_route

            hit = conv_route(prompt)
            if hit and hit.get("matched"):
                sys.stdout.write(
                    json.dumps(
                        {
                            "continue": True,
                            "hookSpecificOutput": {
                                "hookEventName": "UserPromptSubmit",
                                "additionalContext": hit.get("context") or "",
                            },
                            "systemMessage": hit.get("system") or hit.get("title"),
                        }
                    )
                )
                return 0
        except Exception as e:
            # non-fatal — fall through to concert
            pass

    # If normal mode sticky: skip entire RAG pipeline
    if _mode() == "normal":
        sys.stdout.write(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": (
                            "MODE=NORMAL (sticky). RAG-DAG off. Answer as plain Codex. "
                            "Say 'beast mode' to reactivate Private Brain."
                        ),
                    },
                }
            )
        )
        return 0

    # ── BEAST path: golden / coworker / godseye / concert ──
    if any(
        x in low
        for x in (
            "show golden config",
            "golden config",
            "control surface",
            "show control surface",
            "add co-worker",
            "add coworker",
            "onboard teammate",
            "onboard co-worker",
            "coworker join",
        )
    ):
        try:
            from golden_config import load_compact_for_inject, write_golden

            g = write_golden()
            compact = load_compact_for_inject(max_chars=14000)
            join = g.get("coworker_join") or ""
            if "co-worker" in low or "coworker" in low or "teammate" in low or "onboard" in low:
                msg = (
                    "PHASE 5 COWORKER JOIN ready.\n"
                    f"Share this file (no secrets): `{join}`\n"
                    "Co-worker: Codex + their sessions + START + golden_join.json → "
                    "AppGate → AWS → beastMode only.\n\n"
                    + compact
                )
            else:
                msg = (
                    "GOLDEN CONFIG refreshed.\n"
                    f"Full: `.brain/state/GOLDEN_CONFIG.md` · Join: `{join}`\n\n"
                    + compact
                )
            sys.stdout.write(
                json.dumps(
                    {
                        "continue": True,
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": msg[:20000],
                        },
                    }
                )
            )
            return 0
        except Exception as e:
            sys.stdout.write(
                json.dumps(
                    {
                        "continue": True,
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": f"Golden config failed: {e}",
                        },
                    }
                )
            )
            return 0

    if any(
        x in low
        for x in (
            "show godseye",
            "show gods eye",
            "open godseye",
            "open gods eye",
            "start godseye",
            "launch godseye",
        )
    ):
        # Codex 0.144.x Windows: NEVER Popen/GUI from UserPromptSubmit (hook timeout / hung child).
        # Enable flags + instruct agent/shell to launch via beastMode -GodsEye or godseye.py start.
        try:
            STATE.mkdir(parents=True, exist_ok=True)
            (STATE / "godseye.on").write_text("1\n", encoding="utf-8")
            os.environ["PB_GODSEYE"] = "1"
            os.environ["PB_GODSEYE_FORCE"] = "1"
            try:
                import godseye as ge

                ge.clear_dismissed()
                ge.set_enabled(True)
            except Exception:
                pass
            msg = (
                "GodsEye REQUESTED (flags set: godseye.on, PB_GODSEYE=1). "
                "Do NOT spawn GUI from this hook. "
                "Launch out-of-band: beastMode -GodsEye  OR  "
                f"`{SCRIPTS / 'godseye.py'} start`  OR  session_boot with PB_GODSEYE=1. "
                "Prefer NVIDIA discrete GPU when present (RTX); Intel Arc is display fallback. "
                "Headless/CI: stay PB_GODSEYE=0 — graph truth still works in chat."
            )
            sys.stdout.write(
                json.dumps(
                    {
                        "continue": True,
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": msg,
                        },
                        "systemMessage": "GodsEye: flags on — launch via beastMode -GodsEye (no hook Popen)",
                    }
                )
            )
            return 0
        except Exception as e:
            sys.stdout.write(
                json.dumps(
                    {
                        "continue": True,
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": f"GodsEye flag-only path failed: {e}",
                        },
                    }
                )
            )
            return 0

    # ── BEAST path: compact local retrieve only (no remote / no crawl / no write) ──
    wall0 = time.perf_counter()
    deadline = wall0 + UPS_BUDGET_SEC
    deferred_id = ""
    timings: dict = {}
    ctx = ""
    evidence: list = []

    try:
        # Compact existing-graph retrieve only — never allow_crawl in-hook
        t0 = time.perf_counter()
        if time.perf_counter() < deadline - 1.0:
            try:
                from orchestrate import dag_turn

                # allow_crawl=False: no remote, no long crawl in hook budget
                res = dag_turn(prompt, allow_crawl=False)
                ctx = res.get("context") or ""
                evidence = (res.get("retrieve") or {}).get("evidence") or res.get("evidence") or []
            except TypeError:
                # older signature without allow_crawl
                from orchestrate import dag_turn

                res = dag_turn(prompt)
                ctx = res.get("context") or ""
                evidence = (res.get("retrieve") or {}).get("evidence") or []
            except Exception as e:
                ctx = f"(compact retrieve unavailable: {e})"
        timings["retrieve_sec"] = round(time.perf_counter() - t0, 4)

        # Persist current evidence bundle for Stop handoff
        try:
            STATE.mkdir(parents=True, exist_ok=True)
            if evidence:
                (STATE / "current_evidence.json").write_text(
                    json.dumps(
                        {
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "prompt_hash": str(abs(hash(prompt)))[:16],
                            "evidence": evidence[:48],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                (STATE / "ups_evidence.json").write_text(
                    json.dumps({"evidence": evidence[:48]}, indent=2), encoding="utf-8"
                )
        except Exception:
            pass

        # Queue any approved background work (page ingest, chunk, vector) — do not run here
        try:
            deferred_id = f"ups-{uuid.uuid4().hex[:12]}"
            ddir = STATE / "deferred"
            ddir.mkdir(parents=True, exist_ok=True)
            (ddir / f"{deferred_id}.json").write_text(
                json.dumps(
                    {
                        "task_id": deferred_id,
                        "reason": "ups_no_sync_remote",
                        "queued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "work": [
                            "remote_api_deferred",
                            "page_fetch_deferred",
                            "graph_write_deferred",
                            "chunk_vector_deferred",
                            "snapshot_deferred",
                        ],
                        "status": "queued_not_started_in_hook",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            deferred_id = ""

        total = round(time.perf_counter() - wall0, 4)
        try:
            (STATE / "ups_telemetry.json").write_text(
                json.dumps(
                    {
                        "hook": "UserPromptSubmit",
                        "total_sec": total,
                        "budget_sec": UPS_BUDGET_SEC,
                        "context_chars": len(ctx or ""),
                        "deferred_task_id": deferred_id,
                        "stages": timings,
                        "skipped": [
                            "remote_api",
                            "page_fetch",
                            "graph_mutation",
                            "chunking",
                            "vectoring",
                            "snapshot_rebuild",
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

        # Cap inject size — never dump multi-KB remote pages
        inject = (ctx or "")[:4000]
        if deferred_id:
            inject = (
                inject
                + f"\n\n[UPS deferred_task_id={deferred_id} — no sync remote/crawl/chunk in hook]"
            ).strip()
        out = {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": inject,
            },
            "systemMessage": f"Private Brain UPS · t={total}s · deferred={deferred_id or 'none'}",
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=True))
        return 0
    except Exception as e:
        sys.stdout.write(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": f"Private Brain turn error (non-fatal): {e}",
                    },
                },
                ensure_ascii=True,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
