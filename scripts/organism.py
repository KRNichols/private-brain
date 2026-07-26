#!/usr/bin/env python3
"""Private Brain ORGANISM — water-pipe wake (not a flag dance).

Phases:
  0 SESSIONS     — ingest all ~/.codex/sessions rollouts into the graph
  1 MAP          — conversational map if incomplete (delegates day1)
  2 LOCAL        — GodsEye up · heal · polite crawl · max agent swarm · LOCAL_READY
  3 AWS          — gov-region-1 shim / OpenSearch / Neptune probes · GSS routing
  4 ALIVE        — write scoreboard; beastMode stays on

  python organism.py                 # full water pipe
  python organism.py --quiet
  python organism.py --json
  python organism.py --no-godseye
  python organism.py --no-swarm
  python organism.py --interview     # force reconfigure conversation
  python organism.py --sessions-only

beastMode with no flags calls this then opens Codex.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
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


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    p = _ROOT / ".brain" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(f"  · {msg}", flush=True)
    try:
        from gui_bus import gui_event

        gui_event("organism", "progress", msg[:200])
    except Exception:
        pass


def max_agents() -> int:
    """Money unconstrained; cap by CPU/memory safety. Default floor 32, ceiling 256."""
    env = os.environ.get("PB_MAX_AGENTS") or os.environ.get("PB_SWARM_AGENTS") or ""
    if env.strip() and env.strip() not in ("0", "auto"):
        try:
            return max(1, min(256, int(env)))
        except ValueError:
            pass
    try:
        import os as _os

        n = int(_os.cpu_count() or 8)
    except Exception:
        n = 8
    # Interactive-safe: stress showed N=32 ~8min on 27k nodes; default floor 16, soft cap 32
    # Offline/organism force can set PB_MAX_AGENTS higher (up to 256).
    return max(16, min(32, n * 4))


def map_complete() -> bool:
    p = _state() / "organism_map.json"
    if not p.exists():
        # day1 map counts
        d1 = _state() / "day1_map.json"
        if d1.exists():
            try:
                d = json.loads(d1.read_text(encoding="utf-8"))
                # need at least a route decision
                return bool(d.get("route") or d.get("answers", {}).get("route"))
            except Exception:
                return False
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return bool(d.get("complete"))
    except Exception:
        return False


# ── PHASE 0: SESSIONS ──────────────────────────────────────────────


def phase_sessions(report: dict[str, Any], quiet: bool, *, force: bool = True) -> None:
    t0 = time.perf_counter()
    _log("PHASE 0 · ingesting ALL Codex sessions → graph", quiet)
    try:
        from smart_discover import run_discover_ingest

        out = run_discover_ingest(
            max_files=int(os.environ.get("PB_SESSION_MAX_FILES", "5000")),
            force=force,
            agent_id="organism-sessions",
        )
        report["sessions"] = {
            "ok": True,
            "ingested": out.get("ingested"),
            "skipped": out.get("skipped"),
            "discovered": out.get("discovered"),
            "by_kind": out.get("by_kind"),
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(
            f"sessions: ingested={out.get('ingested')} skipped={out.get('skipped')} "
            f"discovered={out.get('discovered')}",
            quiet,
        )
        (_state() / "organism_sessions.json").write_text(
            json.dumps({"ts": _ts(), **report["sessions"]}, default=str), encoding="utf-8"
        )
    except Exception as e:
        report["sessions"] = {"ok": False, "error": str(e)[:240]}
        _log(f"sessions: soft-fail {e}", quiet)


# ── PHASE 1: MAP / INTERVIEW ───────────────────────────────────────


def phase_map(report: dict[str, Any], quiet: bool, *, force_interview: bool) -> None:
    if map_complete() and not force_interview:
        report["map"] = {"skipped": True, "reason": "complete"}
        _log("PHASE 1 · map already complete — skip interview", quiet)
        return
    _log("PHASE 1 · conversational map (packages · code · wiki · issues · AWS)", quiet)
    # If noninteractive env, run day1 --yes with defaults; else interactive day1
    t0 = time.perf_counter()
    try:
        py = sys.executable
        d1 = _SCRIPTS / "day1_first_start.py"
        if not d1.exists():
            report["map"] = {"ok": False, "error": "day1_first_start.py missing"}
            return
        args = [py, str(d1)]
        if os.environ.get("PB_NONINTERACTIVE") in ("1", "true", "yes") or not sys.stdin.isatty():
            args.append("--yes")
            if os.environ.get("PB_ROUTE"):
                args += ["--route", os.environ["PB_ROUTE"]]
        env = os.environ.copy()
        env["PB_ENTERPRISE"] = "1"
        env["PYTHONPATH"] = str(_SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
        # organism mode uses human-language prompts inside day1
        env["PB_ORGANISM_INTERVIEW"] = "1"
        proc = subprocess.run(args, env=env, cwd=str(_ROOT), timeout=3600)
        report["map"] = {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        if proc.returncode == 0:
            (_state() / "organism_map.json").write_text(
                json.dumps({"ts": _ts(), "complete": True}, indent=2), encoding="utf-8"
            )
        _log(f"map: rc={proc.returncode}", quiet)
    except Exception as e:
        report["map"] = {"ok": False, "error": str(e)[:240]}
        _log(f"map: soft-fail {e}", quiet)


# ── PHASE 2: LOCAL + GODSEYE + SWARM ───────────────────────────────


def phase_godseye(report: dict[str, Any], quiet: bool, *, no_godseye: bool) -> None:
    if no_godseye or os.environ.get("PB_GODSEYE", "1") in ("0", "false", "no", "off"):
        report["godseye"] = {"skipped": True, "reason": "disabled"}
        return
    t0 = time.perf_counter()
    try:
        import godseye as ge

        if ge.user_dismissed() and os.environ.get("PB_GODSEYE_FORCE", "") not in ("1", "true", "yes"):
            report["godseye"] = {"skipped": True, "reason": "user_dismissed"}
            _log("GodsEye: user closed it earlier — leave closed (say 'show GodsEye' to reopen)", quiet)
            return
        # prefer-on (respect user dismiss unless force)
        force = os.environ.get("PB_GODSEYE_FORCE", "") in ("1", "true", "yes")
        ge.set_enabled(True)
        os.environ["PB_GODSEYE"] = "1"
        os.environ.setdefault("PB_GODSEYE_BACKEND", "gl")
        out = {}
        if hasattr(ge, "ensure_gui"):
            out = ge.ensure_gui(force=force) or {}
            started = out.get("gui") not in (None, "off", "error", False) or out.get("godseye")
            if out.get("gui") == "error":
                started = False
        else:
            started = False
        report["godseye"] = {
            "ok": bool(started),
            "started": bool(started),
            "detail": out,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(f"GodsEye: {'up' if started else 'headless OK (install pygame from Corporate Library or reopen later)'}", quiet)
    except Exception as e:
        report["godseye"] = {"ok": False, "error": str(e)[:200]}
        _log(f"GodsEye: soft-fail {e} — continue headless", quiet)


def phase_local_heal(report: dict[str, Any], quiet: bool) -> None:
    t0 = time.perf_counter()
    _log("PHASE 2 · self-heal capabilities · chain · vectors", quiet)
    try:
        from capabilities import apply_env_hints, probe, self_repair, write_state

        rep = self_repair()
        r = probe()
        write_state(r)
        apply_env_hints(r)
        report["capabilities"] = {
            "site": (r.get("environment") or {}).get("site"),
            "godseye_mode": (r.get("features") or {}).get("godseye_mode"),
            "repair_ok": (rep or {}).get("ok") if isinstance(rep, dict) else True,
        }
    except Exception as e:
        report["capabilities"] = {"error": str(e)[:160]}
    try:
        from enterprise import self_heal

        h = self_heal()
        report["heal"] = {
            "ok": h.get("ok") if isinstance(h, dict) else True,
            "actions": h.get("actions") if isinstance(h, dict) else None,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(f"heal: actions={report['heal'].get('actions')}", quiet)
    except Exception as e:
        report["heal"] = {"ok": False, "error": str(e)[:200]}
        _log(f"heal: {e}", quiet)


def phase_crawl(report: dict[str, Any], quiet: bool) -> None:
    """Polite crawl — shallow first, rate-limited. No stampede."""
    urls = []
    for key in ("PB_GITLAB_URL", "GITLAB_URL", "PB_JIRA_URL", "PB_CONFLUENCE_URL"):
        v = os.environ.get(key) or ""
        if v.strip():
            urls.append((key, v.strip()))
    if not urls:
        report["crawl"] = {"skipped": True, "reason": "no_urls_configured"}
        _log("crawl: no source URLs yet — set in interview once", quiet)
        return
    _log("PHASE 2 · polite internal crawl (no DDOS — shallow + rate limits)", quiet)
    results = []
    for key, url in urls:
        t0 = time.perf_counter()
        try:
            script = _SCRIPTS / "ingest_url.py"
            cmd = [
                sys.executable,
                str(script),
                "--url",
                url,
                "--deep",
                "--shallow",  # polite first wave
                "--json",
            ]
            env = os.environ.copy()
            env["PB_ENTERPRISE"] = "1"
            env["PYTHONPATH"] = str(_SCRIPTS)
            # min interval if supported via env
            env.setdefault("PB_INGEST_MIN_INTERVAL", "0.35")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("PB_CRAWL_TIMEOUT", "240")),
                env=env,
                cwd=str(_ROOT),
            )
            results.append(
                {
                    "source": key,
                    "url": url[:80],
                    "ok": proc.returncode == 0,
                    "rc": proc.returncode,
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
            _log(f"crawl {key}: rc={proc.returncode}", quiet)
        except Exception as e:
            results.append({"source": key, "ok": False, "error": str(e)[:160]})
            _log(f"crawl {key}: soft-fail {e}", quiet)
    report["crawl"] = {"results": results}
    # quarantine after crawl
    try:
        from enterprise import quarantine_public_nodes

        quarantine_public_nodes()
        report["quarantine"] = {"ok": True}
        _log("quarantine: public hosts stamped", quiet)
    except Exception as e:
        report["quarantine"] = {"error": str(e)[:120]}


def phase_swarm(report: dict[str, Any], quiet: bool, *, no_swarm: bool) -> None:
    if no_swarm:
        report["swarm"] = {"skipped": True}
        return
    n = max_agents()
    os.environ["PB_SWARM_AGENTS"] = str(n)
    _log(f"PHASE 2 · MAX agent swarm N={n} on shared graph (one goal: RAG-DAG)", quiet)
    t0 = time.perf_counter()
    try:
        from agent_swarm import sweep

        prompt = os.environ.get(
            "PB_SWARM_GOAL",
            "Corporate enterprise RAG-DAG: map local knowledge, find gaps, link sessions to sources, "
            "prefer non-public evidence, prepare for AWS gov-region-1 dual-write",
        )
        out = sweep(prompt, n_agents=n, max_workers=min(n, 64))
        report["swarm"] = {
            "ok": out.get("ok") if isinstance(out, dict) else True,
            "n_agents": n,
            "completed": out.get("completed") if isinstance(out, dict) else None,
            "expected": out.get("expected") if isinstance(out, dict) else None,
            "ms": int((time.perf_counter() - t0) * 1000),
        }
        _log(
            f"swarm: expected={report['swarm'].get('expected')} completed={report['swarm'].get('completed')}",
            quiet,
        )
    except Exception as e:
        report["swarm"] = {"ok": False, "error": str(e)[:240], "n_agents": n}
        _log(f"swarm: soft-fail {e}", quiet)


def phase_local_ready(report: dict[str, Any], quiet: bool) -> None:
    _log("PHASE 2 · LOCAL_READY check", quiet)
    try:
        from enterprise import doctor_enterprise

        d = doctor_enterprise()
        soft = {
            "corpus_public_ratio",
            "sres_approved_source",
            "optional_capabilities",
            "corpus_pilot_ready",
        }
        hard = []
        for c in d.get("checks") or []:
            if c.get("ok"):
                continue
            name = c.get("name") or ""
            if name in soft:
                continue
            hard.append(name)
        report["local_ready"] = {
            "ok": len(hard) == 0,
            "hard_fails": hard,
            "pilot_ops": any(
                c.get("name") == "corpus_pilot_ops" and c.get("ok") for c in (d.get("checks") or [])
            ),
        }
        _log(f"LOCAL_READY: {report['local_ready']['ok']} hard={hard or 'none'}", quiet)
    except Exception as e:
        report["local_ready"] = {"ok": False, "error": str(e)[:160]}


# ── PHASE 3: AWS gov-region-1 ─────────────────────────────────────


def phase_aws(report: dict[str, Any], quiet: bool) -> None:
    _log("PHASE 3 · AWS gov-region-1 (shim · OpenSearch · Neptune · GSS routing)", quiet)
    region = (
        os.environ.get("PB_AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or "gov-region-1"
    )
    os.environ.setdefault("PB_AWS_REGION", region)
    os.environ.setdefault("AWS_DEFAULT_REGION", region)
    cloud: dict[str, Any] = {
        "region": region,
        "profile": os.environ.get("AWS_PROFILE") or "",
        "llm_shim": os.environ.get("PB_LLM_BASE_URL") or "",
        "opensearch": bool(os.environ.get("PB_OPENSEARCH_ENDPOINT")),
        "neptune": bool(os.environ.get("PB_NEPTUNE_ENDPOINT")),
    }
    # Apply GSS routing preference when shim present
    if cloud["llm_shim"]:
        os.environ.setdefault("PB_MODEL_PLANE", "aws")
        os.environ.setdefault("PB_MODEL_PREFERENCE", "enterprise-frontier-model")
        _apply_aws_routing(report, quiet)
    else:
        os.environ.setdefault("PB_MODEL_PLANE", "edge")
        os.environ.setdefault("PB_MODEL_PREFERENCE", "gpt-5.1")
        _apply_edge_routing(report, quiet)

    # Probes (soft)
    try:
        from infra_test import test_cloud

        checks = test_cloud()
        cloud["checks"] = [
            {"name": c.get("name"), "ok": c.get("ok"), "detail": str(c.get("detail") or "")[:100]}
            for c in (checks or [])
        ]
        cloud["any_cloud"] = any(c.get("ok") for c in (checks or []))
    except Exception as e:
        cloud["probe_error"] = str(e)[:160]
        cloud["any_cloud"] = False

    # Config self-repair hint file for operators
    cloud["ready"] = bool(cloud.get("llm_shim")) and bool(cloud.get("any_cloud") or cloud.get("opensearch"))
    report["aws"] = cloud
    path = _state() / "cloud_ready.json"
    path.write_text(json.dumps({"ts": _ts(), **cloud}, indent=2, default=str), encoding="utf-8")
    _log(
        f"AWS: region={region} shim={'yes' if cloud['llm_shim'] else 'no'} "
        f"ready={cloud['ready']} (soft if not — local still pilot-ready)",
        quiet,
    )


def _apply_edge_routing(report: dict[str, Any], quiet: bool) -> None:
    try:
        route_path = _ROOT / "config" / "model_routing.json"
        if route_path.exists():
            data = json.loads(route_path.read_text(encoding="utf-8"))
            edge = (data.get("routing_edge") or {}).get("orchestrator") or {}
            report["routing"] = {"plane": "edge", "orchestrator": edge.get("model")}
            _log(f"routing: EDGE model={edge.get('model')}", quiet)
    except Exception as e:
        report["routing"] = {"plane": "edge", "error": str(e)[:80]}


def _apply_aws_routing(report: dict[str, Any], quiet: bool) -> None:
    try:
        route_path = _ROOT / "config" / "model_routing.json"
        if route_path.exists():
            data = json.loads(route_path.read_text(encoding="utf-8"))
            aws = (data.get("routing_aws_when_shim") or {}).get("orchestrator") or {}
            report["routing"] = {"plane": "aws", "orchestrator": aws.get("model") or "enterprise-frontier-model"}
            _log(f"routing: AWS GSS plane model={report['routing']['orchestrator']}", quiet)
            # Write active routing stamp for agents
            (_state() / "active_routing.json").write_text(
                json.dumps(
                    {
                        "ts": _ts(),
                        "plane": "aws",
                        "region": "gov-region-1",
                        "orchestrator": report["routing"]["orchestrator"],
                        "shim": os.environ.get("PB_LLM_BASE_URL"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    except Exception as e:
        report["routing"] = {"plane": "aws", "error": str(e)[:80]}


# ── PHASE 4: METRICS / ALIVE ───────────────────────────────────────


def phase_golden(report: dict[str, Any], quiet: bool) -> None:
    """Teach the model the complete Corporate map + co-worker join pack."""
    _log("GOLDEN CONFIG · write model law + co-worker join pack", quiet)
    try:
        from golden_config import write_golden

        g = write_golden(compact_chars=int(os.environ.get("PB_GOLDEN_COMPACT_CHARS", "12000")))
        report["golden"] = {
            "ok": True,
            "paths": g.get("paths"),
            "coworker_join": g.get("coworker_join"),
            "full_chars": g.get("full_chars"),
            "compact_chars": g.get("compact_chars"),
        }
        _log(
            f"golden: full={g.get('full_chars')}c compact={g.get('compact_chars')}c "
            f"join={g.get('coworker_join')}",
            quiet,
        )
    except Exception as e:
        report["golden"] = {"ok": False, "error": str(e)[:200]}
        _log(f"golden: soft-fail {e}", quiet)


def phase_alive(report: dict[str, Any], quiet: bool) -> None:
    try:
        from ops_metrics import collect, write_metrics

        m = collect()
        write_metrics(m)
        report["metrics"] = {
            "band": (m.get("score") or {}).get("band"),
            "score": (m.get("score") or {}).get("ops_100"),
            "hard": (m.get("health") or {}).get("hard_issues") or [],
        }
    except Exception as e:
        report["metrics"] = {"error": str(e)[:120]}
    local_ok = bool((report.get("local_ready") or {}).get("ok", True))
    report["alive"] = local_ok
    report["band"] = "WATER_FLOWING" if local_ok else "BLOCKED_LOCAL"
    path = _state() / "organism.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["state"] = str(path)
    # enterprise always-on flag
    (_state() / "enterprise.on").write_text("1\n", encoding="utf-8")
    (_state() / "beastmode.on").write_text("1\n", encoding="utf-8")
    _log(f"ALIVE: {report['alive']} band={report['band']} metrics={report.get('metrics')}", quiet)


def run(
    *,
    quiet: bool = False,
    no_godseye: bool = False,
    no_swarm: bool = False,
    no_crawl: bool = False,
    interview: bool = False,
    sessions_only: bool = False,
    force_sessions: bool = True,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    os.environ["PB_ENTERPRISE"] = "1"
    report: dict[str, Any] = {
        "ts": _ts(),
        "suite": "organism_water_pipe",
        "platform": sys.platform,
        "max_agents": max_agents(),
        "phases": {},
    }
    if not quiet:
        print("==============================================")
        print(" Private Brain — ORGANISM (water pipe)")
        print(" sessions → map → local+GodsEye → AWS → alive")
        print("==============================================")
        print(f" max_agents={report['max_agents']}  region_default=gov-region-1")

    phase_sessions(report, quiet, force=force_sessions)
    if sessions_only:
        phase_alive(report, quiet)
        report["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        return report

    phase_map(report, quiet, force_interview=interview)
    phase_godseye(report, quiet, no_godseye=no_godseye)
    phase_local_heal(report, quiet)
    if not no_crawl:
        phase_crawl(report, quiet)
    phase_swarm(report, quiet, no_swarm=no_swarm)
    phase_local_ready(report, quiet)
    phase_aws(report, quiet)
    phase_golden(report, quiet)
    phase_alive(report, quiet)

    report["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    if not quiet:
        print("----------------------------------------------")
        print(f" band:    {report.get('band')}")
        print(f" alive:   {report.get('alive')}")
        print(f" local:   {(report.get('local_ready') or {})}")
        print(f" aws:     shim={bool((report.get('aws') or {}).get('llm_shim'))} ready={(report.get('aws') or {}).get('ready')}")
        print(f" swarm:   N={(report.get('swarm') or {}).get('n_agents')}")
        print(f" state:   {report.get('state')}")
        print("==============================================")
        print(" Water is flowing. Open Codex and work.")
        print("   beastMode          # default — organism + Codex")
        print("   show GodsEye       # in chat if you closed the HUD")
        print("==============================================")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain organism — water pipe")
    ap.add_argument("--quiet", "-q", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-godseye", action="store_true")
    ap.add_argument("--no-swarm", action="store_true")
    ap.add_argument("--no-crawl", action="store_true")
    ap.add_argument("--interview", action="store_true", help="Force reconfigure conversation")
    ap.add_argument("--sessions-only", action="store_true")
    ap.add_argument("--no-force-sessions", action="store_true")
    args = ap.parse_args()
    r = run(
        quiet=args.quiet or args.json,
        no_godseye=args.no_godseye,
        no_swarm=args.no_swarm,
        no_crawl=args.no_crawl,
        interview=args.interview,
        sessions_only=args.sessions_only,
        force_sessions=not args.no_force_sessions,
    )
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    return 0 if r.get("alive") else 1


if __name__ == "__main__":
    raise SystemExit(main())
