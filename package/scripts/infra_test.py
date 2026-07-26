#!/usr/bin/env python3
"""
Infrastructure readiness tests for Private Brain (local + optional gov-region-1).

Uses the same audit/DAG patterns. When something is red, `repair` tries to fix
what can be fixed locally; cloud repair returns an actionable work list (or
runs dual-write smoke if endpoints + AWS creds exist).

  python infra_test.py test
  python infra_test.py repair
  python infra_test.py full
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def _check(name: str, ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "status": "green" if ok else "red", "detail": detail, **extra}


def test_local() -> list[dict[str, Any]]:
    ensure_tree()
    br = resolve_brain_root()
    ch = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    out: list[dict[str, Any]] = []

    out.append(
        _check(
            "local_brain_tree",
            (br / ".brain" / "nodes").is_dir(),
            str(br / ".brain"),
        )
    )
    out.append(
        _check(
            "local_scripts",
            (br / "scripts" / "orchestrate.py").exists()
            and (br / "scripts" / "smart_discover.py").exists(),
            "orchestrate+smart_discover",
        )
    )
    out.append(
        _check(
            "local_hooks",
            (ch / "hooks.json").exists() and (br / "hooks" / "session_start.py").exists(),
            str(ch / "hooks.json"),
        )
    )
    out.append(
        _check(
            "local_beast_profile",
            (ch / "beast.config.toml").exists(),
            str(ch / "beast.config.toml"),
        )
    )

    st = status()
    out.append(
        _check(
            "local_corpus",
            int(st.get("node_count") or 0) > 0,
            f"nodes={st.get('node_count')} edges={st.get('edge_count')}",
        )
    )

    chain = verify_chain()
    out.append(
        _check("local_audit_chain", bool(chain.get("ok")), f"events={chain.get('events_checked')}")
    )

    try:
        from vector_manager import status as vs

        v = vs()
        out.append(
            _check(
                "local_vectors",
                int(v.get("vectors") or 0) > 0,
                f"vectors={v.get('vectors')} vocab={v.get('vocab_terms')}",
            )
        )
    except Exception as e:
        out.append(_check("local_vectors", False, str(e)[:160]))

    # sessions tree discoverable
    sessions = ch / "sessions"
    has_rollout = False
    if sessions.is_dir():
        for _ in sessions.rglob("rollout-*.jsonl"):
            has_rollout = True
            break
    out.append(
        _check(
            "local_sessions_tree",
            sessions.is_dir(),
            f"{sessions} rollouts_present={has_rollout}",
            rollouts_present=has_rollout,
        )
    )
    return out


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "tcp_ok"
    except Exception as e:
        return False, str(e)[:120]


def test_cloud() -> list[dict[str, Any]]:
    """Probe configured cloud endpoints; never requires them for local green."""
    out: list[dict[str, Any]] = []
    try:
        from backends import load_backend_config

        cfg = load_backend_config()
        out.append(
            _check(
                "backend_config",
                True,
                f"graph={cfg.graph} vectors={cfg.vectors} embed={cfg.embeddings} region={cfg.region}",
            )
        )
    except Exception as e:
        out.append(_check("backend_config", False, str(e)[:160]))
        cfg = None

    neptune = os.environ.get("PB_NEPTUNE_ENDPOINT") or (cfg.neptune_endpoint if cfg else None)
    os_ep = os.environ.get("PB_OPENSEARCH_ENDPOINT") or (cfg.opensearch_endpoint if cfg else None)
    region = (
        os.environ.get("PB_BEDROCK_REGION")
        or os.environ.get("AWS_REGION")
        or (cfg.region if cfg else "gov-region-1")
    )

    if not neptune and not os_ep:
        out.append(
            _check(
                "cloud_endpoints",
                True,
                "no cloud endpoints configured — local-only mode (OK). Set PB_NEPTUNE_ENDPOINT / PB_OPENSEARCH_ENDPOINT to enable infra tests",
                mode="local_only",
            )
        )
        return out

    # Neptune endpoint probe (wss/https host)
    if neptune:
        host = neptune
        port = 8182
        try:
            if "://" in neptune:
                u = urlparse(neptune.replace("wss://", "https://").replace("ws://", "http://"))
                host = u.hostname or neptune
                port = u.port or (443 if u.scheme == "https" else 8182)
        except Exception:
            pass
        ok, detail = _tcp_reachable(host, port)
        out.append(_check("neptune_tcp", ok, f"{host}:{port} {detail}", endpoint=neptune))
    else:
        out.append(_check("neptune_tcp", False, "PB_NEPTUNE_ENDPOINT not set", optional=True))

    if os_ep:
        host = os_ep
        port = 443
        try:
            u = urlparse(os_ep if "://" in os_ep else f"https://{os_ep}")
            host = u.hostname or os_ep
            port = u.port or 443
            # HTTPS HEAD-ish
            url = os_ep if os_ep.startswith("http") else f"https://{os_ep}"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    out.append(
                        _check(
                            "opensearch_http",
                            resp.status < 500,
                            f"HTTP {resp.status}",
                            endpoint=os_ep,
                        )
                    )
            except urllib.error.HTTPError as e:
                # 401/403 often means reachable but auth required — still "up"
                ok = e.code in (401, 403, 200, 404)
                out.append(
                    _check(
                        "opensearch_http",
                        ok,
                        f"HTTP {e.code} (reachable={ok})",
                        endpoint=os_ep,
                    )
                )
            except Exception as e:
                ok, detail = _tcp_reachable(host, port)
                out.append(_check("opensearch_http", ok, f"{detail}; {e}"[:160], endpoint=os_ep))
        except Exception as e:
            out.append(_check("opensearch_http", False, str(e)[:160]))
    else:
        out.append(_check("opensearch_http", False, "PB_OPENSEARCH_ENDPOINT not set", optional=True))

    # Bedrock / AWS creds presence (not full model invoke unless boto3+creds)
    has_creds = bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("AWS_PROFILE")
        or (Path.home() / ".aws" / "credentials").exists()
    )
    out.append(
        _check(
            "aws_creds_present",
            has_creds,
            f"region={region} (presence only — not a permission guarantee)",
        )
    )

    if has_creds:
        try:
            import boto3  # type: ignore

            br = boto3.client("bedrock", region_name=region)
            # list foundation models is a light authz probe
            br.list_foundation_models(byOutputModality="EMBEDDING")
            out.append(_check("bedrock_list_embedding_models", True, f"region={region}"))
        except ImportError:
            out.append(
                _check(
                    "bedrock_list_embedding_models",
                    False,
                    "boto3 not installed in venv — pip install boto3 for cloud tests",
                )
            )
        except Exception as e:
            out.append(_check("bedrock_list_embedding_models", False, str(e)[:200]))

    return out


def test_dag_runtime() -> list[dict[str, Any]]:
    """Exercise local DAG path as infra of the agent system itself."""
    out: list[dict[str, Any]] = []
    try:
        from orchestrate import dag_boot, dag_turn

        b = dag_boot()
        out.append(_check("dag_boot", bool(b.get("boot", b).get("ok", True)), f"run={b.get('boot', b).get('run_id')}"))
        t = dag_turn("infra readiness probe kafka", allow_crawl=False)
        out.append(
            _check(
                "dag_turn",
                bool(t.get("validate", {}).get("chain_ok")),
                f"hits={t.get('retrieve',{}).get('hit_count')} final={t.get('final_ok')}",
            )
        )
    except Exception as e:
        out.append(_check("dag_boot", False, str(e)[:200]))
        out.append(_check("dag_turn", False, "skipped"))

    try:
        from smart_discover import codex_dag_validate

        cv = codex_dag_validate(
            "Infra test: cite 2 Private Brain nodes with `id` (T#). No permission talk."
        )
        out.append(
            _check(
                "codex_exec_dag_node",
                bool(cv.get("ok") or (cv.get("citations_found") or 0) >= 1),
                f"cites={cv.get('citations_found')} rc={cv.get('returncode')} err={cv.get('error')}",
            )
        )
    except Exception as e:
        out.append(_check("codex_exec_dag_node", False, str(e)[:200]))
    return out


def run_tests() -> dict[str, Any]:
    ensure_tree()
    local = test_local()
    cloud = test_cloud()
    dag = test_dag_runtime()
    all_c = local + cloud + dag

    # readiness: all non-optional local+dag greens; cloud optional unless endpoints set
    def required(c: dict) -> bool:
        if c.get("optional") and not c["ok"]:
            # optional red only matters if endpoint was expected
            return True
        if c["name"] in ("neptune_tcp", "opensearch_http", "aws_creds_present", "bedrock_list_embedding_models"):
            # only required if endpoints configured
            neptune = os.environ.get("PB_NEPTUNE_ENDPOINT")
            os_ep = os.environ.get("PB_OPENSEARCH_ENDPOINT")
            if c["name"] == "neptune_tcp":
                return bool(neptune)
            if c["name"] == "opensearch_http":
                return bool(os_ep)
            if c["name"] in ("aws_creds_present", "bedrock_list_embedding_models"):
                return bool(neptune or os_ep)
        return True

    hard_fails = [c for c in all_c if required(c) and not c["ok"]]
    ready = len(hard_fails) == 0
    report = {
        "ts": utc_now(),
        "ready_for_use": ready,
        "hard_fail_count": len(hard_fails),
        "hard_fails": [c["name"] for c in hard_fails],
        "local": local,
        "cloud": cloud,
        "dag": dag,
        "summary": {
            "green": sum(1 for c in all_c if c["ok"]),
            "red": sum(1 for c in all_c if not c["ok"]),
            "total": len(all_c),
        },
    }
    write_json(STATE_DIR / "infra_test.json", report)
    audit(
        "infra_test",
        agent_id="infra",
        role="validator",
        result="ok" if ready else "fail",
        detail=f"ready={ready} fails={hard_fails}",
        props={"hard_fails": report["hard_fails"]},
    )
    return report


def repair() -> dict[str, Any]:
    """
    Perform work when tests are red.
    Local: rebuild tree, discover sessions, reindex, rate, hooks install, orchestrate boot.
    Cloud: cannot invent AWS resources; emit build jobs + try dual-write smoke if possible.
    """
    ensure_tree()
    before = run_tests()
    actions: list[dict[str, Any]] = []
    br = resolve_brain_root()

    def act(name: str, fn) -> None:
        try:
            result = fn()
            actions.append({"action": name, "ok": True, "result": result})
            audit("infra_repair", agent_id="infra", role="orchestrator", result="ok", detail=name)
        except Exception as e:
            actions.append({"action": name, "ok": False, "error": str(e)[:240]})
            audit("infra_repair", agent_id="infra", role="orchestrator", result="fail", detail=f"{name}: {e}"[:200])

    fails = set(before.get("hard_fails") or [])

    if "local_brain_tree" in fails or "local_scripts" in fails:
        actions.append(
            {
                "action": "require_install",
                "ok": False,
                "error": "Run Install-PrivateBrain.ps1 from package zip — scripts missing",
            }
        )

    if "local_hooks" in fails or "local_beast_profile" in fails:
        def fix_hooks():
            install = br / "scripts" / "install_hooks.py"
            if install.exists():
                subprocess.check_call([sys.executable, str(install)])
                return "install_hooks.py ran"
            # minimal hooks.json pointer
            return "install_hooks.py missing — re-copy package"

        act("repair_hooks", fix_hooks)

    if "local_corpus" in fails or "local_vectors" in fails or "local_sessions_tree" in fails:
        def rebuild():
            from brain_lib import build_snapshot
            from knowledge_rater import rate_all
            from smart_discover import run_discover_ingest
            from vector_manager import reindex_all

            d = run_discover_ingest(max_files=120, force=False, agent_id="infra-repair")
            # if still empty, seed is via brain_init
            st = status()
            if int(st.get("node_count") or 0) == 0:
                from brain_lib import seed_demo

                seed_demo()
            ri = reindex_all()
            rt = rate_all(persist=True)
            snap = build_snapshot().get("stats")
            return {"discover": d.get("ingested"), "reindex": ri, "rating_avg": rt.get("avg"), "snap": snap}

        act("repair_knowledge_pipeline", rebuild)

    if "local_audit_chain" in fails:
        def fix_chain():
            # cannot rewrite history; emit new genesis event and verify tip moves
            audit("chain_repair_marker", agent_id="infra", role="security_auditor", result="ok", detail="marker")
            return verify_chain()

        act("repair_audit_marker", fix_chain)

    if "dag_boot" in fails or "dag_turn" in fails:
        def fix_dag():
            from orchestrate import dag_boot, dag_turn

            b = dag_boot()
            t = dag_turn("repair probe", allow_crawl=False)
            return {"boot": b.get("boot", {}).get("ok"), "hits": t.get("retrieve", {}).get("hit_count")}

        act("repair_dag_runtime", fix_dag)

    if "codex_exec_dag_node" in fails:
        def fix_codex():
            from smart_discover import codex_dag_validate

            return codex_dag_validate("Repair validation: cite 2 nodes with tiers.")

        act("repair_codex_validate", fix_codex)

    # Cloud repair: only smoke if endpoints exist
    neptune = os.environ.get("PB_NEPTUNE_ENDPOINT")
    os_ep = os.environ.get("PB_OPENSEARCH_ENDPOINT")
    if neptune or os_ep:
        def cloud_smoke():
            # placeholder dual-write smoke — real writers land when clients added
            return {
                "note": "Cloud endpoints set; dual-write clients not yet implemented — validate IAM/VPC connectivity next",
                "neptune": bool(neptune),
                "opensearch": bool(os_ep),
                "next": [
                    "Implement neptune openCypher UPSERT client behind backends.py",
                    "Implement OpenSearch bulk index for Titan vectors",
                    "Re-run infra_test.py full",
                ],
            }

        act("cloud_dual_write_prep", cloud_smoke)
    else:
        actions.append(
            {
                "action": "cloud_build_checklist",
                "ok": True,
                "result": {
                    "mode": "build",
                    "steps": [
                        "Survey existing VPC in gov-region-1",
                        "Prefer managed Neptune + managed OpenSearch k-NN + Bedrock Titan",
                        "Set PB_NEPTUNE_ENDPOINT and PB_OPENSEARCH_ENDPOINT when live",
                        "Flip config/backend.yaml graph/vectors/embeddings",
                        "Keep dual_write_filesystem=true",
                    ],
                },
            }
        )

    after = run_tests()
    report = {
        "ts": utc_now(),
        "before_ready": before.get("ready_for_use"),
        "after_ready": after.get("ready_for_use"),
        "before_fails": before.get("hard_fails"),
        "after_fails": after.get("hard_fails"),
        "actions": actions,
        "after": after,
    }
    write_json(STATE_DIR / "infra_repair.json", report)
    audit(
        "infra_repair_complete",
        agent_id="infra",
        role="orchestrator",
        result="ok" if after.get("ready_for_use") else "partial",
        detail=f"before={before.get('ready_for_use')} after={after.get('ready_for_use')}",
    )
    return report


def full() -> dict[str, Any]:
    t = run_tests()
    if t.get("ready_for_use"):
        return {"ready_for_use": True, "tested": t, "repaired": None, "message": "infra ready — no repair needed"}
    r = repair()
    return {
        "ready_for_use": r.get("after_ready"),
        "tested_before": t,
        "repaired": r,
        "message": "repair attempted" if not t.get("ready_for_use") else "ready",
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["test", "repair", "full"])
    args = ap.parse_args()
    if args.cmd == "test":
        out = run_tests()
    elif args.cmd == "repair":
        out = repair()
    else:
        out = full()
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ready_for_use") or out.get("after_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
