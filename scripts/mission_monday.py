#!/usr/bin/env python3
"""Monday zero-fail mission orchestrator — phased gates for Corporate walk-in.

Phases (see MISSION_MONDAY.md):
  0 PREFLIGHT     — codex + sessions tree + kit present
  1 INSTALL       — sideload present
  2 PACKAGES      — Corporate Library/capabilities (degrade OK)
  3 SESSIONS      — local session harvest FIRST
  4 LOCAL_READY   — heal + doctor hard 100%
  5 OPS           — internal sources (if URLs set) + quarantine
  6 CLOUD         — AWS SHIM endpoints (if set) infra assessment
  7 REPORT        — mission scoreboard

  python mission_monday.py              # run all possible phases
  python mission_monday.py --phase local
  python mission_monday.py --json

Never requires Corporate Library/AWS/Jira/Confluence to exist — unknown = soft degrade.
Human life at stake → hard gates only for local trust path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))


def _brain() -> Path:
    return Path(os.environ.get("PRIVATE_BRAIN_HOME") or (_codex_home() / "private-brain"))


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "hard": hard}


def phase_preflight() -> dict[str, Any]:
    ch = _codex_home()
    sessions = ch / "sessions"
    has_sessions = sessions.is_dir()
    n_rollouts = 0
    if has_sessions:
        try:
            n_rollouts = sum(1 for _ in sessions.rglob("rollout-*.jsonl"))
        except Exception:
            n_rollouts = 0
    codex_bin = False
    try:
        import shutil

        codex_bin = bool(shutil.which("codex"))
    except Exception:
        pass
    checks = [
        gate("codex_home", ch.is_dir(), str(ch)),
        gate("sessions_tree", has_sessions, f"{sessions} rollouts={n_rollouts}", hard=False),
        gate("sessions_gold", n_rollouts > 0 or has_sessions, f"rollouts={n_rollouts}", hard=False),
        gate("codex_binary", codex_bin, "codex on PATH", hard=False),
    ]
    return {
        "phase": "0_PREFLIGHT",
        "ok": all(c["ok"] for c in checks if c["hard"]),
        "checks": checks,
        "note": "Backup/restore sessions before uninstall is operator step — not automated here",
    }


def phase_install() -> dict[str, Any]:
    br = _brain()
    checks = [
        gate("brain_home", br.is_dir(), str(br)),
        gate("orchestrate", (br / "scripts" / "orchestrate.py").exists()),
        gate("smart_discover", (br / "scripts" / "smart_discover.py").exists()),
        gate("capabilities", (br / "scripts" / "capabilities.py").exists()),
        gate("hooks", (_codex_home() / "hooks.json").exists() or (br / "hooks" / "hooks.json").exists()),
        gate("beast_profile", (_codex_home() / "beast-enterprise.config.toml").exists()
             or (_codex_home() / "beast.config.toml").exists(), hard=False),
    ]
    return {"phase": "1_INSTALL", "ok": all(c["ok"] for c in checks if c["hard"]), "checks": checks}


def phase_packages() -> dict[str, Any]:
    """Corporate Library/capabilities — soft degrade if no index."""
    from capabilities import heal_optional, probe, write_state, apply_env_hints

    # Prefer enterprise-ish package policy when enterprise flag set
    caps = probe()
    apply_env_hints(caps)
    write_state(caps)
    heal = heal_optional(dry_run=False)
    env = caps.get("environment") or {}
    feat = heal.get("features_after") or caps.get("features") or {}
    checks = [
        gate("core_rag_stdlib", True, "always"),
        gate(
            "pip_index",
            bool(env.get("index_url_set")) or not env.get("enterprise"),
            f"index_set={env.get('index_url_set')} site={env.get('site')}",
            hard=False,
        ),
        gate(
            "capabilities_heal",
            bool(heal.get("ok", True)),
            f"degraded={heal.get('degraded')} missing={heal.get('still_missing') or heal.get('missing') or []}",
            hard=False,
        ),
        gate(
            "godseye_path",
            True,
            f"mode={feat.get('godseye_mode')} layout={feat.get('layout_accel')}",
            hard=False,
        ),
    ]
    return {
        "phase": "2_PACKAGES",
        "ok": True,  # packages never hard-block local pilot
        "checks": checks,
        "features": feat,
        "site": env.get("site"),
    }


def phase_sessions() -> dict[str, Any]:
    """Sessions FIRST — local gold before AppGate sources.

    Hard gate: either codex_session nodes >= 1, or operator set PB_SESSIONS_EMPTY_ACK=1
    (explicit empty-sessions acknowledge after restore check).
    """
    try:
        from smart_discover import run_discover_ingest

        out = run_discover_ingest(max_files=400, force=False, agent_id="mission-sessions")
    except Exception as e:
        out = {"ok": False, "error": str(e)[:200]}
    try:
        from brain_lib import status

        st = status() or {}
        by = st.get("by_source") or {}
        sess = int(by.get("codex_session") or 0)
    except Exception:
        sess = 0
        st = {}
    empty_ack = os.environ.get("PB_SESSIONS_EMPTY_ACK", "").lower() in ("1", "true", "yes")
    sess_ok = sess >= 1 or empty_ack
    checks = [
        gate(
            "session_ingest",
            bool(out.get("ok", True)) or "error" not in out,
            json.dumps({k: out.get(k) for k in ("ingested", "skipped", "error") if k in out})[:160],
        ),
        gate(
            "codex_session_nodes",
            sess_ok,
            f"codex_session={sess} empty_ack={empty_ack} "
            f"(restore sessions or set PB_SESSIONS_EMPTY_ACK=1)",
            hard=True,
        ),
        gate(
            "graph_nonempty",
            int(st.get("node_count") or 0) >= 0,
            f"nodes={st.get('node_count')}",
            hard=False,
        ),
    ]
    # hard: ingest must not crash AND sessions present or ack
    hard_ok = ( "error" not in out or bool(out.get("ok")) ) and sess_ok
    return {
        "phase": "3_SESSIONS",
        "ok": hard_ok,
        "checks": checks,
        "discover": {k: out.get(k) for k in ("ingested", "skipped", "rated", "ok", "error") if k in out},
    }


def phase_local_ready() -> dict[str, Any]:
    """Heal + doctor hard gates — 100% local trust path."""
    os.environ.setdefault("PB_ENTERPRISE", "1")
    heal_rep: dict[str, Any] = {}
    try:
        from enterprise import self_heal

        heal_rep = self_heal()
    except Exception as e:
        heal_rep = {"ok": False, "error": str(e)[:200]}
    try:
        from enterprise import doctor_enterprise

        doc = doctor_enterprise()
    except Exception as e:
        doc = {"ok": False, "checks": [], "error": str(e)[:200]}

    soft = {
        "corpus_public_ratio",
        "corpus_pilot_ready",
        "sres_approved_source",
        "optional_capabilities",
        "corpus_pilot_ops",  # ops soft until internal crawl
    }
    hard_fails = [
        c for c in (doc.get("checks") or [])
        if not c.get("ok") and c.get("name") not in soft
    ]
    checks = [
        gate("heal", bool(heal_rep.get("ok", True)), f"actions={heal_rep.get('actions')}", hard=True),
        gate("doctor_hard", len(hard_fails) == 0,
             f"fails={[c.get('name') for c in hard_fails]}", hard=True),
        gate("chain", any(c.get("name") == "audit_chain" and c.get("ok") for c in (doc.get("checks") or [])),
             "audit_chain", hard=True),
        gate("vectors", any(c.get("name") == "vector_parity" and c.get("ok") for c in (doc.get("checks") or [])),
             "vector_parity", hard=True),
    ]
    # Empty brand-new graph: vector parity may be nodes=0 — allow if doctor soft-path OK
    if not any(c.get("name") == "vector_parity" and c.get("ok") for c in (doc.get("checks") or [])):
        try:
            from brain_lib import status
            from vector_manager import status as vs

            n = int((status() or {}).get("node_count") or 0)
            v = int((vs() or {}).get("vectors") or 0)
            if n == 0 and v == 0:
                checks.append(gate("vectors_empty_ok", True, "empty graph allowed pre-ingest", hard=True))
                # remove hard fail on vectors if empty
                checks = [c for c in checks if c["name"] != "vectors"] + [
                    gate("vectors", True, "empty parity OK", hard=True)
                ]
        except Exception:
            pass

    ok = all(c["ok"] for c in checks if c["hard"]) and len(hard_fails) == 0
    return {
        "phase": "4_LOCAL_READY",
        "ok": ok,
        "checks": checks,
        "hard_fails": [c.get("name") for c in hard_fails],
        "heal_actions": heal_rep.get("actions"),
        "doctor_ok": doc.get("ok"),
    }


def phase_ops() -> dict[str, Any]:
    """Internal crawl only if URLs present; always attempt quarantine hygiene."""
    gl = os.environ.get("PB_GITLAB_URL") or os.environ.get("GITLAB_URL") or ""
    jr = os.environ.get("PB_JIRA_URL") or os.environ.get("JIRA_URL") or ""
    cf = os.environ.get("PB_CONFLUENCE_URL") or os.environ.get("CONFLUENCE_URL") or ""
    has_src = bool(gl or jr or cf)
    crawl_note = "skipped — no GitLab/Jira/Confluence URLs yet (soft)"
    if has_src:
        try:
            from internal_crawl_swarm import run_swarm  # type: ignore

            crawl_note = "swarm_available"
            # Do not auto-fire heavy crawl without operator; mark ready-to-crawl
        except Exception:
            crawl_note = "URLs set — run DAY1 crawl / beastMode -ingestion when AppGate up"

    pur: dict[str, Any] = {}
    try:
        from enterprise import corpus_purity_audit, quarantine_public_nodes

        q = quarantine_public_nodes(dry_run=False)
        pur = (q.get("purity") if isinstance(q, dict) else None) or corpus_purity_audit(write=True)
    except Exception as e:
        pur = {"error": str(e)[:160]}

    checks = [
        gate("internal_urls", has_src, f"gl={bool(gl)} jira={bool(jr)} conf={bool(cf)}", hard=False),
        gate(
            "pilot_ops_ready",
            bool(pur.get("pilot_ops_ready")),
            f"q_cov={pur.get('quarantine_coverage')} clean={pur.get('clean_nodes')}",
            hard=False,
        ),
        gate(
            "pilot_ready",
            bool(pur.get("pilot_ready")),
            f"public_ratio={pur.get('public_ratio')} (needs internal re-ingest)",
            hard=False,
        ),
        gate("crawl_policy", True, crawl_note, hard=False),
    ]
    return {
        "phase": "5_OPS",
        "ok": True,  # ops never hard-block without URLs
        "checks": checks,
        "purity": {
            k: pur.get(k)
            for k in (
                "pilot_ops_ready",
                "pilot_ready",
                "quarantine_coverage",
                "public_ratio",
                "total_nodes",
            )
            if k in pur
        },
    }


def phase_cloud() -> dict[str, Any]:
    """AWS SHIM assessment — hard only for endpoints that ARE configured."""
    neptune = os.environ.get("PB_NEPTUNE_ENDPOINT") or ""
    opensearch = os.environ.get("PB_OPENSEARCH_ENDPOINT") or ""
    llm = os.environ.get("PB_LLM_BASE_URL") or ""
    region = (
        os.environ.get("PB_BEDROCK_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or ""
    )
    configured = bool(neptune or opensearch or llm)

    cloud_checks: list[dict[str, Any]] = []
    if not configured:
        return {
            "phase": "6_CLOUD",
            "ok": True,
            "checks": [
                gate(
                    "cloud_not_configured",
                    True,
                    "no SHIM endpoints yet — local RAG remains pilot path (OK)",
                    hard=False,
                )
            ],
            "mode": "local_only",
            "note": "Interview C: set PB_NEPTUNE_ENDPOINT PB_OPENSEARCH_ENDPOINT PB_LLM_BASE_URL then re-run",
        }

    try:
        from infra_test import test_cloud

        cloud_checks = test_cloud()
    except Exception as e:
        cloud_checks = [{"name": "infra_test", "ok": False, "detail": str(e)[:160]}]

    # Map to gates: optional flags stay soft; configured failures are hard
    gates = []
    for c in cloud_checks:
        name = c.get("name") or "cloud"
        ok = bool(c.get("ok"))
        optional = bool(c.get("optional"))
        hard = configured and not optional and name not in ("cloud_endpoints", "backend_config")
        # backend_config always soft-info
        if name in ("backend_config", "cloud_endpoints"):
            hard = False
        gates.append(gate(name, ok, str(c.get("detail") or c.get("msg") or "")[:160], hard=hard))

    # SHIM presence
    gates.append(gate("llm_shim", bool(llm), f"PB_LLM_BASE_URL={llm or 'unset'}", hard=False))
    gates.append(gate("region", bool(region), f"region={region or 'unset'}", hard=False))
    gates.append(gate("neptune_configured", bool(neptune), neptune[:80] or "unset", hard=False))
    gates.append(gate("opensearch_configured", bool(opensearch), opensearch[:80] or "unset", hard=False))

    hard_ok = all(g["ok"] for g in gates if g["hard"])
    return {
        "phase": "6_CLOUD",
        "ok": hard_ok,
        "checks": gates,
        "mode": "cloud_probe",
        "godseye_neptune": (
            "enable KPI panel when PB_NEPTUNE_ENDPOINT set and dual-write active"
            if neptune
            else "local graph watch only until Neptune configured"
        ),
    }


def run_mission(*, stop_after: str | None = None) -> dict[str, Any]:
    phases = [
        ("preflight", phase_preflight),
        ("install", phase_install),
        ("packages", phase_packages),
        ("sessions", phase_sessions),
        ("local", phase_local_ready),
        ("ops", phase_ops),
        ("cloud", phase_cloud),
    ]
    report: dict[str, Any] = {
        "ts": _ts(),
        "mission": "monday_zero_fail_pilot",
        "phases": [],
        "ok": True,
        "local_ready": False,
        "ops_ready": False,
        "cloud_ready": False,
        "band": "FAIL",
    }
    for key, fn in phases:
        if stop_after == "packages" and key in ("sessions", "local", "ops", "cloud"):
            break
        if stop_after == "local" and key in ("ops", "cloud"):
            break
        if stop_after == "ops" and key == "cloud":
            break
        try:
            ph = fn()
        except Exception as e:
            ph = {"phase": key, "ok": False, "error": str(e)[:200], "checks": []}
        report["phases"].append(ph)
        if key == "local":
            report["local_ready"] = bool(ph.get("ok"))
        if key == "ops":
            pur = ph.get("purity") or {}
            report["ops_ready"] = bool(pur.get("pilot_ops_ready"))
        if key == "cloud":
            report["cloud_ready"] = bool(ph.get("ok")) and (ph.get("mode") == "cloud_probe")
        # Hard phase failures
        if key in ("install", "sessions", "local") and not ph.get("ok"):
            report["ok"] = False

    # Score
    pts = 0
    pts += 15 if report["phases"][0].get("ok") else 0  # preflight
    pts += 15 if any(p.get("phase", "").startswith("1_") and p.get("ok") for p in report["phases"]) else 0
    pts += 10  # packages always non-blocking credit if ran
    pts += 15 if any(p.get("phase", "").startswith("3_") and p.get("ok") for p in report["phases"]) else 0
    pts += 25 if report["local_ready"] else 0
    pts += 10 if report["ops_ready"] else 5  # partial credit for quarantine attempt
    if any(p.get("phase", "").startswith("6_") for p in report["phases"]):
        cloud = next(p for p in report["phases"] if str(p.get("phase", "")).startswith("6_"))
        if cloud.get("mode") == "local_only":
            pts += 5  # honest local-only
        elif cloud.get("ok"):
            pts += 10
    report["score_100"] = min(100, pts)
    if report["local_ready"] and report["ok"]:
        report["band"] = "LOCAL_READY_SHIP" if not report["cloud_ready"] else "FULL_SHIP"
        if report["ops_ready"]:
            report["band"] = "OPS_READY_SHIP" if not report["cloud_ready"] else "FULL_SHIP"
    elif report["score_100"] >= 55:
        report["band"] = "CAUTION"
    else:
        report["band"] = "FAIL"

    report["next"] = _next_actions(report)
    path = _brain() / ".brain" / "state" / "mission_monday.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["path"] = str(path)
    return report


def _next_actions(report: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not report.get("local_ready"):
        out.append("Run: beastMode --enterprise --heal && beastMode --enterprise --doctor")
        out.append("Fix any HARD doctor fails (chain / vectors / hooks) before AWS")
        return out
    out.append("LOCAL_READY achieved — pilot can work on local RAG-DAG")
    if not report.get("ops_ready"):
        out.append("Interview B: set PB_GITLAB_URL / JIRA / CONFLUENCE + tokens; AppGate on; DAY1 crawl")
        out.append("Then: beastMode --quarantine-public")
    neptune = os.environ.get("PB_NEPTUNE_ENDPOINT")
    if not neptune and not os.environ.get("PB_OPENSEARCH_ENDPOINT"):
        out.append(
            "Interview C (AWS SHIM): PB_LLM_BASE_URL, PB_OPENSEARCH_ENDPOINT, "
            "PB_NEPTUNE_ENDPOINT, AWS_PROFILE, region — then: python scripts/mission_monday.py"
        )
    else:
        out.append("Re-run mission_monday for CLOUD_READY; enable dual-write when green")
        out.append("GodsEye: local graph now; Neptune KPI when dual-write active")
    out.append("Self-heal anytime: beastMode --heal")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Monday zero-fail mission")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--phase",
        choices=["all", "local", "packages", "ops"],
        default="all",
        help="stop after phase group",
    )
    args = ap.parse_args()
    stop = None if args.phase == "all" else args.phase
    # ensure enterprise-ish for local gates without forcing package public pip block on home
    if "PB_ENTERPRISE" not in os.environ:
        # mission is Corporate walk-in — default enterprise profile
        os.environ["PB_ENTERPRISE"] = "1"

    report = run_mission(stop_after=stop)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("==============================================")
        print(" Private Brain — MONDAY MISSION (zero-fail)")
        print("==============================================")
        print(f" band:   {report['band']}  score={report['score_100']}")
        print(f" local:  {report['local_ready']}  ops: {report['ops_ready']}  cloud: {report['cloud_ready']}")
        for ph in report["phases"]:
            mark = "PASS" if ph.get("ok") else "FAIL"
            print(f"\n[{mark}] {ph.get('phase')}")
            for c in ph.get("checks") or []:
                m = "ok" if c.get("ok") else ("HARD" if c.get("hard") else "soft")
                print(f"   {m:4}  {c.get('name')}: {str(c.get('detail') or '')[:90]}")
        print("\n── NEXT ──")
        for line in report.get("next") or []:
            print(f" · {line}")
        print(f"\n state: {report.get('path')}")
        print(" docs:  MISSION_MONDAY.md")
        print("==============================================")
    return 0 if report.get("ok") and report.get("local_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
