#!/usr/bin/env python3
"""
Bootstrap power runner — diagnose → stand-up → rebuild knowledge → evaluate → deploy plan.

This is the executable spine behind POWER_PROMPT_BOOTSTRAP.md.
Codex beast mode should call this; humans can too.

  python bootstrap_power.py diagnose
  python bootstrap_power.py rebuild-knowledge
  python bootstrap_power.py evaluate
  python bootstrap_power.py deploy-plan
  python bootstrap_power.py full
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ensure scripts on path
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from audit_lib import audit, verify_chain
from brain_lib import (
    STATE_DIR,
    ensure_tree,
    resolve_brain_root,
    status,
    utc_now,
    write_json,
)


def brain_root() -> Path:
    return resolve_brain_root()


def codex_home() -> Path:
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]).expanduser()
    user = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(user) / ".codex"


def stage(name: str, ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"stage": name, "status": "green" if ok else "red", "ok": ok, "detail": detail, **extra}


def diagnose() -> dict[str, Any]:
    """S0 — is the system stood up?"""
    ensure_tree()
    br = brain_root()
    ch = codex_home()
    checks = {
        "brain_root": str(br),
        "codex_home": str(ch),
        "beast_mode_md": (br / "beast-mode.md").exists(),
        "orchestrate": (br / "scripts" / "orchestrate.py").exists(),
        "smart_discover": (br / "scripts" / "smart_discover.py").exists(),
        "vector_manager": (br / "scripts" / "vector_manager.py").exists(),
        "hooks_json": (ch / "hooks.json").exists(),
        "session_start_hook": (br / "hooks" / "session_start.py").exists(),
        "beast_profile": (ch / "beast.config.toml").exists(),
        "venv": (br / "venv" / "bin" / "python3").exists()
        or (br / "venv" / "Scripts" / "python.exe").exists(),
        "agents_dir": (ch / "agents").is_dir(),
        "backend_yaml": (br / "config" / "backend.yaml").exists(),
    }
    st = status()
    chain = verify_chain()
    try:
        from vector_manager import status as vs

        vec = vs()
    except Exception as e:
        vec = {"error": str(e)[:160], "vectors": 0}

    missing = [k for k, v in checks.items() if v is False]
    stood_up = len(missing) == 0
    ready = (
        stood_up
        and st.get("node_count", 0) > 0
        and chain.get("ok")
        and int(vec.get("vectors") or 0) > 0
    )

    out = {
        "stage": "S0_diagnose",
        "stood_up": "yes" if stood_up else ("partial" if checks["orchestrate"] else "no"),
        "ready_for_use": ready,
        "checks": checks,
        "missing": missing,
        "brain": {
            "nodes": st.get("node_count"),
            "edges": st.get("edge_count"),
            "by_source": st.get("by_source"),
        },
        "chain_ok": chain.get("ok"),
        "chain_events": chain.get("events_checked"),
        "vectors": vec,
        "ts": utc_now(),
    }
    audit(
        "bootstrap_diagnose",
        agent_id="bootstrap",
        role="orchestrator",
        result="ok" if ready else "partial",
        detail=f"stood_up={out['stood_up']} ready={ready}",
        props={"missing": missing, "nodes": st.get("node_count")},
    )
    write_json(STATE_DIR / "bootstrap_diagnose.json", out)
    return out


def rebuild_knowledge(max_files: int = 500) -> dict[str, Any]:
    """S2 — smart discover + rate + snapshot (knowledge stage rebuild)."""
    ensure_tree()
    rid = f"rebuild-{utc_now()}"
    audit("bootstrap_rebuild", agent_id="bootstrap", role="orchestrator", run_id=rid, result="start")
    report: dict[str, Any] = {"stage": "S2_rebuild_knowledge", "ok": False}

    try:
        from smart_discover import run_discover_ingest

        disc = run_discover_ingest(max_files=max_files, force=False, agent_id=f"discover-{rid}")
        report["discover"] = {
            "discovered": disc.get("discovered"),
            "ingested": disc.get("ingested"),
            "skipped": disc.get("skipped"),
            "by_kind": disc.get("by_kind"),
            "rating": disc.get("rating"),
            "brain": disc.get("brain"),
        }
    except Exception as e:
        report["discover_error"] = str(e)[:300]

    try:
        from vector_manager import reindex_all
        from vector_manager import status as vs

        # incremental: only reindex if vectors lag nodes
        st = status()
        v = vs()
        if int(v.get("vectors") or 0) < int(st.get("node_count") or 0) * 0.9:
            report["reindex"] = reindex_all()
        else:
            report["reindex"] = {"skipped": True, "vectors": v}
        report["vectors"] = vs()
    except Exception as e:
        report["vector_error"] = str(e)[:200]

    try:
        from knowledge_rater import rate_all

        report["rating"] = rate_all(persist=True)
    except Exception as e:
        report["rating_error"] = str(e)[:200]

    try:
        from brain_lib import build_snapshot

        report["snapshot"] = build_snapshot().get("stats")
    except Exception as e:
        report["snapshot_error"] = str(e)[:160]

    st = status()
    report["brain"] = {"nodes": st.get("node_count"), "edges": st.get("edge_count"), "by_source": st.get("by_source")}
    report["ok"] = int(st.get("node_count") or 0) > 0
    report["status"] = "green" if report["ok"] else "red"
    audit(
        "bootstrap_rebuild",
        agent_id="bootstrap",
        role="orchestrator",
        run_id=rid,
        result="ok" if report["ok"] else "fail",
        detail=f"nodes={st.get('node_count')}",
    )
    write_json(STATE_DIR / "bootstrap_rebuild.json", report)
    return report


def evaluate() -> dict[str, Any]:
    """S3 — readiness evaluation via infra DAG tests (local + cloud + codex node)."""
    ensure_tree()
    try:
        from infra_test import repair, run_tests

        report = run_tests()
        repaired = None
        if not report.get("ready_for_use"):
            # PERFORM the work — not just report
            repaired = repair()
            report = repaired.get("after") or run_tests()
            report["repair_performed"] = True
            report["repair_actions"] = [
                a.get("action") for a in (repaired.get("actions") or []) if a.get("ok") is not False or True
            ]
        else:
            report["repair_performed"] = False

        results = []
        for section in ("local", "cloud", "dag"):
            for c in report.get(section) or []:
                results.append(
                    stage(c.get("name") or section, bool(c.get("ok")), str(c.get("detail") or "")[:200])
                )
        out = {
            "stage": "S3_evaluate",
            "ready_for_use": bool(report.get("ready_for_use")),
            "score": f"{report.get('summary',{}).get('green')}/{report.get('summary',{}).get('total')}",
            "hard_fails": report.get("hard_fails"),
            "repair_performed": report.get("repair_performed"),
            "results": results,
            "infra": report,
            "ts": utc_now(),
        }
    except Exception as e:
        out = {
            "stage": "S3_evaluate",
            "ready_for_use": False,
            "score": "0/0",
            "error": str(e)[:300],
            "ts": utc_now(),
        }
    audit(
        "bootstrap_evaluate",
        agent_id="bootstrap",
        role="orchestrator",
        result="ok" if out.get("ready_for_use") else "fail",
        detail=str(out.get("score")),
    )
    write_json(STATE_DIR / "bootstrap_evaluate.json", out)
    return out


def deploy_plan() -> dict[str, Any]:
    """S4–S5 — migrate vs build plan for gov-region-1 (no silent cloud writes)."""
    ensure_tree()
    try:
        from backends import load_backend_config, recommend_govcloud

        cfg = load_backend_config()
        gov = recommend_govcloud()
    except Exception as e:
        cfg = None
        gov = {"error": str(e)[:200]}

    endpoints = {
        "PB_NEPTUNE_ENDPOINT": os.environ.get("PB_NEPTUNE_ENDPOINT"),
        "PB_OPENSEARCH_ENDPOINT": os.environ.get("PB_OPENSEARCH_ENDPOINT"),
        "PB_BEDROCK_REGION": os.environ.get("PB_BEDROCK_REGION") or os.environ.get("AWS_REGION") or "gov-region-1",
        "AWS_PROFILE": os.environ.get("AWS_PROFILE"),
    }
    has_neptune = bool(endpoints["PB_NEPTUNE_ENDPOINT"])
    has_os = bool(endpoints["PB_OPENSEARCH_ENDPOINT"])
    mode = "migrate" if (has_neptune or has_os) else "build"

    steps_migrate = [
        "Keep dual_write_filesystem=true (laptop .brain remains SoT cache).",
        "Set backend.yaml: graph=neptune (or neptune-analytics), vectors=opensearch, embeddings=bedrock-titan.",
        "Verify VPC endpoints: bedrock-runtime, neptune, es/opensearch in gov-region-1.",
        "Confirm Titan embed model ID enabled for this Government Cloud account.",
        "Batch export: nodes/edges → openCypher/CSV; chunks+embeddings → OpenSearch bulk.",
        "Read path: OpenSearch hybrid → Neptune hop expand → tier/worth re-rank (same as local DAG).",
        "Run bootstrap_power.py evaluate after dual-write smoke.",
        "Codex validate node: smart_discover.py validate.",
    ]
    steps_build = [
        "Do not invent ARNs — survey existing VPC/subnets/security groups first.",
        "Preferred stack: managed Neptune Database (graph) + managed OpenSearch k-NN (vectors) + Bedrock Titan (embed).",
        "Not Neptune classic alone for vectors; consider Neptune Analytics only if GraphRAG+vectors one-engine is approved.",
        "EC2 OpenSearch only if managed search blocked by ATO.",
        "IL/FedRAMP: private subnets, no public endpoints, KMS CMKs, CloudTrail, config rules.",
        "After infra green: set PB_* endpoints and switch backend.yaml; then migrate steps above.",
        "Local beast mode keeps working offline regardless of cloud.",
    ]

    out = {
        "stage": "S4_S5_deploy",
        "mode": mode,
        "region": "gov-region-1",
        "endpoints_detected": endpoints,
        "active_backend": cfg.to_dict() if cfg else None,
        "govcloud_summary": (gov or {}).get("summary"),
        "recommended_stack": (gov or {}).get("tiers", {}).get("govcloud_preferred"),
        "actions": steps_migrate if mode == "migrate" else steps_build,
        "migrate_checklist": steps_migrate,
        "build_checklist": steps_build,
        "ts": utc_now(),
    }
    audit(
        "bootstrap_deploy_plan",
        agent_id="bootstrap",
        role="orchestrator",
        result="ok",
        detail=f"mode={mode}",
        props={"has_neptune": has_neptune, "has_opensearch": has_os},
    )
    write_json(STATE_DIR / "bootstrap_deploy_plan.json", out)
    return out


def full() -> dict[str, Any]:
    """Autonomous path: diagnose → rebuild if needed → evaluate → deploy plan."""
    d = diagnose()
    rebuilt = None
    if d.get("stood_up") != "yes" or not d.get("ready_for_use"):
        # attempt knowledge rebuild even if partial stand-up (scripts present)
        if d.get("checks", {}).get("orchestrate"):
            rebuilt = rebuild_knowledge()
        else:
            rebuilt = {
                "ok": False,
                "status": "red",
                "detail": "Package not installed — run Install-PrivateBrain.ps1 from zip first",
            }
    else:
        # still refresh knowledge lightly
        rebuilt = rebuild_knowledge(max_files=80)

    ev = evaluate()
    plan = deploy_plan()

    report = {
        "suite": "bootstrap_power_full",
        "stood_up": d.get("stood_up"),
        "ready_for_use": ev.get("ready_for_use"),
        "S0_diagnose": d,
        "S2_rebuild": {
            "ok": (rebuilt or {}).get("ok"),
            "nodes": (rebuilt or {}).get("brain", {}).get("nodes"),
            "discover": (rebuilt or {}).get("discover"),
        },
        "S3_evaluate": {"ready": ev.get("ready_for_use"), "score": ev.get("score"), "results": ev.get("results")},
        "S4_S5_deploy": {"mode": plan.get("mode"), "actions_head": (plan.get("actions") or [])[:5]},
        "ts": utc_now(),
    }
    write_json(STATE_DIR / "bootstrap_full.json", report)
    audit(
        "bootstrap_full",
        agent_id="bootstrap",
        role="orchestrator",
        result="ok" if ev.get("ready_for_use") else "partial",
        detail=f"ready={ev.get('ready_for_use')} mode={plan.get('mode')}",
    )
    return report


def render_human(report: dict[str, Any]) -> str:
    """Markdown summary for Codex / operator."""
    if "suite" in report:
        lines = [
            "## Stand-up status",
            f"stood_up: {report.get('stood_up')}",
            f"ready_for_use: {report.get('ready_for_use')}",
            "",
            "## Stage results",
            f"S0 diagnose: stood_up={report.get('stood_up')}",
            f"S2 rebuild: ok={report.get('S2_rebuild',{}).get('ok')} nodes={report.get('S2_rebuild',{}).get('nodes')}",
            f"S3 evaluate: {report.get('S3_evaluate',{}).get('score')} ready={report.get('S3_evaluate',{}).get('ready')}",
            f"S4/S5 deploy mode: {report.get('S4_S5_deploy',{}).get('mode')}",
            "",
            "## Next actions",
        ]
        for i, a in enumerate(report.get("S4_S5_deploy", {}).get("actions_head") or [], 1):
            lines.append(f"{i}. {a}")
        return "\n".join(lines)
    return json.dumps(report, indent=2, default=str)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Private Brain bootstrap power runner")
    ap.add_argument(
        "cmd",
        choices=["diagnose", "rebuild-knowledge", "evaluate", "deploy-plan", "full"],
    )
    ap.add_argument("--max-files", type=int, default=150)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "diagnose":
        out = diagnose()
    elif args.cmd == "rebuild-knowledge":
        out = rebuild_knowledge(max_files=args.max_files)
    elif args.cmd == "evaluate":
        out = evaluate()
    elif args.cmd == "deploy-plan":
        out = deploy_plan()
    else:
        out = full()

    if args.json or args.cmd != "full":
        print(json.dumps(out, indent=2, default=str))
    else:
        print(render_human(out))
        print("\n--- raw ---")
        print(json.dumps(out, indent=2, default=str)[:4000])
    return 0 if out.get("ready_for_use", out.get("ok", True)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
