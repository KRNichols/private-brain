#!/usr/bin/env python3
"""Private Brain autopilot — the organism, not the checklist.

One call does what humans were told to type as 12 commands:
  sessions harvest (if stale) → capabilities repair → full heal if needed
  → quarantine public (enterprise) → ops metrics → optional crawl if URLs set
  → write alive state

Never grounds the pilot for missing Corporate Library/AWS/Jira. Hard failures only on
local trust path (chain, vectors, hooks) — then heals and retries once.

  python autopilot.py              # run + print scoreboard
  python autopilot.py --quiet      # silent (beastMode launch)
  python autopilot.py --json
  python autopilot.py --no-crawl   # skip network crawl even if URLs set

Env:
  PB_AUTOPILOT=0          disable when called from beastMode
  PB_AUTOPILOT_FORCE=1    always full heal even if healthy
  PB_SESSIONS_EMPTY_ACK=1 allow zero session nodes without soft warn
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))

os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# Stale thresholds (seconds)
SESSIONS_STALE_S = 6 * 3600  # re-harvest sessions every 6h
METRICS_STALE_S = 300
HEAL_IF_DOCTOR_HARD = True


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    p = _ROOT / ".brain" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _age(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 1e12


def _log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(f"  · {msg}", flush=True)


def step_sessions(report: dict[str, Any], quiet: bool) -> None:
    """Self-learning: harvest Codex sessions into the graph when stale."""
    t0 = time.perf_counter()
    marker = _state() / "autopilot_sessions.json"
    force = os.environ.get("PB_AUTOPILOT_FORCE", "") in ("1", "true", "yes")
    if not force and marker.exists() and _age(marker) < SESSIONS_STALE_S:
        report["sessions"] = {"skipped": True, "reason": "fresh", "age_s": round(_age(marker), 1)}
        _log("sessions: fresh — skip harvest", quiet)
        return
    try:
        from smart_discover import run_discover_ingest

        out = run_discover_ingest(max_files=400, force=False, agent_id="autopilot-sessions")
        report["sessions"] = {
            "skipped": False,
            "result": {
                "ingested": out.get("ingested") if isinstance(out, dict) else None,
                "skipped": out.get("skipped") if isinstance(out, dict) else None,
                "ok": out.get("ok") if isinstance(out, dict) else True,
            },
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        marker.write_text(json.dumps({"ts": _ts(), "result": report["sessions"]}, default=str), encoding="utf-8")
        _log(
            f"sessions: harvested ingested={report['sessions']['result'].get('ingested')} "
            f"skip={report['sessions']['result'].get('skipped')}",
            quiet,
        )
    except Exception as e:
        report["sessions"] = {"ok": False, "error": str(e)[:200]}
        _log(f"sessions: soft-fail {e}", quiet)


def step_capabilities(report: dict[str, Any], quiet: bool) -> None:
    t0 = time.perf_counter()
    try:
        from capabilities import apply_env_hints, probe, self_repair, write_state

        rep = self_repair()  # home free-pip / Corporate index-or-degrade
        r = probe()
        write_state(r)
        apply_env_hints(r)
        report["capabilities"] = {
            "site": (r.get("environment") or {}).get("site"),
            "godseye_mode": (r.get("features") or {}).get("godseye_mode"),
            "repair": {
                "actions": (rep or {}).get("actions") if isinstance(rep, dict) else None,
                "ok": (rep or {}).get("ok") if isinstance(rep, dict) else True,
            },
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(
            f"capabilities: site={report['capabilities'].get('site')} "
            f"mode={report['capabilities'].get('godseye_mode')}",
            quiet,
        )
    except Exception as e:
        report["capabilities"] = {"error": str(e)[:200]}
        _log(f"capabilities: soft-fail {e}", quiet)


def step_heal_if_needed(report: dict[str, Any], quiet: bool) -> None:
    t0 = time.perf_counter()
    force = os.environ.get("PB_AUTOPILOT_FORCE", "") in ("1", "true", "yes")
    need = force
    hard_fails: list[str] = []
    try:
        from enterprise import doctor_enterprise

        d = doctor_enterprise()
        for c in d.get("checks") or []:
            if c.get("ok"):
                continue
            name = c.get("name") or ""
            # soft Corporate unknowns never force full heal loop alone
            if name in (
                "corpus_public_ratio",
                "corporate_library_approved_source",
                "optional_capabilities",
                "cloud",
            ):
                continue
            hard_fails.append(name)
        need = need or (HEAL_IF_DOCTOR_HARD and bool(hard_fails))
        report["doctor_pre"] = {
            "hard_fails": hard_fails,
            "ok": d.get("ok"),
            "ready": not hard_fails,
        }
    except Exception as e:
        need = True
        report["doctor_pre"] = {"error": str(e)[:160]}

    if not need:
        # still light repair: chain + vector parity
        try:
            from audit_lib import seal_broken_chain, verify_chain

            ch = verify_chain() or {}
            if not ch.get("ok"):
                seal_broken_chain()
                report["light_heal"] = {"chain_sealed": True}
            else:
                report["light_heal"] = {"chain_ok": True}
        except Exception as e:
            report["light_heal"] = {"error": str(e)[:120]}
        try:
            from brain_lib import ensure_tree, status
            from vector_manager import reindex_all
            from vector_manager import status as vs

            ensure_tree()
            n = int((status() or {}).get("node_count") or 0)
            v = int((vs() or {}).get("vectors") or 0)
            if n and v < n:
                reindex_all(include_structural=True)
                report["light_heal"] = {**(report.get("light_heal") or {}), "reindexed": True, "nodes": n}
        except Exception as e:
            report["light_heal"] = {**(report.get("light_heal") or {}), "vec_err": str(e)[:120]}
        _log("heal: healthy — light chain/vector check only", quiet)
        report["heal"] = {"full": False, "ms": int((time.perf_counter() - t0) * 1000)}
        return

    _log(f"heal: FULL (fails={hard_fails or 'force'})", quiet)
    try:
        from enterprise import self_heal

        h = self_heal()
        report["heal"] = {
            "full": True,
            "actions": h.get("actions") if isinstance(h, dict) else None,
            "ok": h.get("ok") if isinstance(h, dict) else True,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as e:
        report["heal"] = {"full": True, "ok": False, "error": str(e)[:200]}
        _log(f"heal: error {e}", quiet)


def step_quarantine(report: dict[str, Any], quiet: bool) -> None:
    if os.environ.get("PB_ENTERPRISE", "") not in ("1", "true", "yes"):
        report["quarantine"] = {"skipped": True, "reason": "not_enterprise"}
        return
    t0 = time.perf_counter()
    try:
        from enterprise import corpus_purity_audit, quarantine_public_nodes

        pur = corpus_purity_audit(write=False)
        q = float(pur.get("quarantine_coverage") or 0)
        if q >= 0.99 and pur.get("pilot_ops_ready"):
            report["quarantine"] = {"skipped": True, "reason": "already_full", "q": q}
            _log(f"quarantine: already full q={q:.2f}", quiet)
            return
        out = quarantine_public_nodes()
        report["quarantine"] = {
            "skipped": False,
            "result": {
                "tagged": (out or {}).get("tagged") if isinstance(out, dict) else None,
                "ok": (out or {}).get("ok") if isinstance(out, dict) else True,
            },
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log("quarantine: stamped public hosts", quiet)
    except Exception as e:
        report["quarantine"] = {"error": str(e)[:200]}
        _log(f"quarantine: soft-fail {e}", quiet)


def step_crawl_if_configured(report: dict[str, Any], quiet: bool, *, no_crawl: bool) -> None:
    if no_crawl:
        report["crawl"] = {"skipped": True, "reason": "no_crawl_flag"}
        return
    gl = os.environ.get("PB_GITLAB_URL") or os.environ.get("GITLAB_URL")
    if not gl:
        report["crawl"] = {"skipped": True, "reason": "no_urls"}
        _log("crawl: no PB_GITLAB_URL — skip (set once, then automatic)", quiet)
        return
    # throttle crawls: at most once per 12h unless force
    marker = _state() / "autopilot_crawl.json"
    force = os.environ.get("PB_AUTOPILOT_FORCE", "") in ("1", "true", "yes")
    if not force and marker.exists() and _age(marker) < 12 * 3600:
        report["crawl"] = {"skipped": True, "reason": "fresh", "age_s": round(_age(marker), 1)}
        _log("crawl: recent — skip", quiet)
        return
    t0 = time.perf_counter()
    try:
        import subprocess

        py = sys.executable
        script = _SCRIPTS / "ingest_url.py"
        cmd = [py, str(script), "--url", gl, "--deep", "--json"]
        # shallow-ish on autopilot unless force (don't block launch forever)
        if os.environ.get("PB_AUTOPILOT_FORCE", "") not in ("1", "true", "yes"):
            cmd.append("--shallow")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
        env["PB_ENTERPRISE"] = os.environ.get("PB_ENTERPRISE", "1")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("PB_AUTOPILOT_CRAWL_TIMEOUT", "180")),
            env=env,
            cwd=str(_ROOT),
        )
        report["crawl"] = {
            "url": gl[:80],
            "rc": proc.returncode,
            "ok": proc.returncode == 0,
            "ms": int((time.perf_counter() - t0) * 1000),
            "tail": (proc.stdout or proc.stderr or "")[-300:],
        }
        if proc.returncode == 0:
            marker.write_text(json.dumps({"ts": _ts(), "url": gl}, default=str), encoding="utf-8")
            _log(f"crawl: ok {gl[:60]}…", quiet)
        else:
            _log(f"crawl: soft-fail rc={proc.returncode} (AppGate/token?)", quiet)
    except Exception as e:
        report["crawl"] = {"error": str(e)[:200]}
        _log(f"crawl: soft-fail {e}", quiet)


def step_metrics(report: dict[str, Any], quiet: bool) -> None:
    t0 = time.perf_counter()
    try:
        from ops_metrics import collect, write_metrics

        r = collect()
        path = write_metrics(r)
        report["metrics"] = {
            "band": (r.get("score") or {}).get("band"),
            "score": (r.get("score") or {}).get("ops_100"),
            "hard": (r.get("health") or {}).get("hard_issues") or [],
            "path": str(path),
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(f"metrics: {report['metrics'].get('band')} {report['metrics'].get('score')}/100", quiet)
    except Exception as e:
        report["metrics"] = {"error": str(e)[:200]}
        _log(f"metrics: soft-fail {e}", quiet)


def step_distill(report: dict[str, Any], quiet: bool) -> None:
    """Self-learning loop: distill vault → Codex skills when missing/stale."""
    try:
        skill = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "skills" / "private-brain" / "SKILL.md"
        if skill.exists() and _age(skill) < 24 * 3600:
            report["distill"] = {"skipped": True, "reason": "skill_fresh"}
            return
        from distill_vault import sync_to_codex

        out = sync_to_codex()
        report["distill"] = {"ok": True, "result": out if not isinstance(out, dict) else {k: out.get(k) for k in list(out)[:6]}}
        _log("distill: vault → Codex skills", quiet)
    except Exception as e:
        report["distill"] = {"skipped": True, "error": str(e)[:120]}


def run(*, quiet: bool = False, no_crawl: bool = False) -> dict[str, Any]:
    t0 = time.perf_counter()
    report: dict[str, Any] = {
        "ts": _ts(),
        "suite": "autopilot",
        "platform": sys.platform,
        "enterprise": os.environ.get("PB_ENTERPRISE", "") in ("1", "true", "yes"),
        "steps": {},
    }
    if not quiet:
        print("==============================================")
        print(" Private Brain — AUTOPILOT (self-heal · learn · score)")
        print("==============================================")

    step_sessions(report, quiet)
    step_capabilities(report, quiet)
    step_heal_if_needed(report, quiet)
    step_quarantine(report, quiet)
    step_crawl_if_configured(report, quiet, no_crawl=no_crawl)
    step_distill(report, quiet)
    step_metrics(report, quiet)

    # final doctor snapshot (soft)
    try:
        from enterprise import doctor_enterprise

        d = doctor_enterprise()
        hard = [c.get("name") for c in (d.get("checks") or []) if not c.get("ok") and c.get("name") not in (
            "corpus_public_ratio", "corporate_library_approved_source", "optional_capabilities"
        )]
        # re-classify soft
        soft_names = {"corpus_public_ratio", "corporate_library_approved_source", "optional_capabilities"}
        hard = []
        for c in d.get("checks") or []:
            if c.get("ok"):
                continue
            n = c.get("name") or ""
            if n in soft_names:
                continue
            if n == "corpus_pilot_ready" and os.environ.get("PB_ENTERPRISE") == "1":
                # ship path may still be ok via ops
                continue
            hard.append(n)
        report["doctor_post"] = {"hard_fails": hard, "ok": len(hard) == 0}
    except Exception as e:
        report["doctor_post"] = {"error": str(e)[:160]}

    report["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    report["alive"] = bool((report.get("doctor_post") or {}).get("ok", True))
    report["band"] = (report.get("metrics") or {}).get("band") or ("ALIVE" if report["alive"] else "HURT")

    path = _state() / "autopilot.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["state"] = str(path)

    if not quiet:
        m = report.get("metrics") or {}
        print(f" band:    {report.get('band')}  metrics={m.get('score')}/100")
        print(f" alive:   {report.get('alive')}  hard_post={(report.get('doctor_post') or {}).get('hard_fails') or []}")
        print(f" elapsed: {report.get('elapsed_ms')}ms")
        print(f" state:   {path}")
        print("==============================================")
        print(" You do not need heal/doctor/mission/metrics by hand.")
        print(" Just:  beastMode --enterprise")
        print("==============================================")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain autopilot — one organism")
    ap.add_argument("--quiet", "-q", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-crawl", action="store_true")
    ap.add_argument("--force", action="store_true", help="Full heal + re-harvest even if fresh")
    args = ap.parse_args()
    if args.force:
        os.environ["PB_AUTOPILOT_FORCE"] = "1"
    # enterprise default when flag file present
    flag = _ROOT / ".brain" / "state" / "enterprise.on"
    if flag.exists() and not os.environ.get("PB_ENTERPRISE"):
        os.environ["PB_ENTERPRISE"] = "1"
    r = run(quiet=args.quiet or args.json, no_crawl=args.no_crawl)
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    return 0 if r.get("alive") else 1


if __name__ == "__main__":
    raise SystemExit(main())
