#!/usr/bin/env python3
"""Enterprise validation harness — multi-agent, reproducible purity, audit, lint.

Step order (fixed):
  lint → swarm(16) → concert → quarantine → purity_repro×3 → retrieve_hygiene
  → vector reindex → audit_chain → doctor → sap_pack

After graph writers (swarm/concert) we always re-quarantine and reindex so
doctor vector_parity + corpus_pilot_ops stay green.

Exit 0 when hard_ok (ops-ready). soft pilot_ready (raw public host ratio <15%)
is reported but does NOT fail hard_ok until internal re-ingest.

Usage:
  PB_ENTERPRISE=1 python validate_enterprise.py
  PB_ENTERPRISE=1 python validate_enterprise.py --agents 16 --purity-runs 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure scripts on path when invoked as file
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_ROOT = _SCRIPTS.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("PB_ENTERPRISE", "1")

# Fixed pipeline order (writers → seal hygiene → seals/readiness)
STEP_ORDER = (
    "lint",
    "swarm",
    "concert",
    "quarantine",
    "purity_repro",
    "retrieve_hygiene",
    "vector_reindex",
    "audit_chain",
    "doctor",
    "sap_pack",
)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _step(name: str, fn, report: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        out = fn()
        ok = bool(out.get("ok", True)) if isinstance(out, dict) else True
        entry = {
            "name": name,
            "ok": ok,
            "ms": int((time.perf_counter() - t0) * 1000),
            "result": out,
        }
    except Exception as e:
        entry = {
            "name": name,
            "ok": False,
            "ms": int((time.perf_counter() - t0) * 1000),
            "error": str(e)[:400],
        }
    report["steps"].append({k: entry[k] for k in ("name", "ok", "ms") if k in entry})
    if "error" in entry:
        report["steps"][-1]["error"] = entry["error"]
    report["detail"][name] = entry
    return entry


def step_lint() -> dict[str, Any]:
    targets = [
        _SCRIPTS / "enterprise.py",
        _SCRIPTS / "orchestrate.py",
        _SCRIPTS / "agent_swarm.py",
        _SCRIPTS / "validate_enterprise.py",
        _SCRIPTS / "vector_manager.py",
        _SCRIPTS / "audit_lib.py",
    ]
    compiled: list[str] = []
    errors: list[str] = []
    for p in targets:
        if not p.exists():
            continue
        try:
            py_compile.compile(str(p), doraise=True)
            compiled.append(p.name)
        except Exception as e:
            errors.append(f"{p.name}: {e}")
    # optional ruff if present
    ruff_ok = None
    ruff = _ROOT / "venv" / "bin" / "ruff"
    if ruff.exists():
        r = subprocess.run(
            [str(ruff), "check", str(_SCRIPTS / "enterprise.py"), str(_SCRIPTS / "validate_enterprise.py")],
            capture_output=True,
            text=True,
        )
        ruff_ok = r.returncode == 0
        if not ruff_ok:
            errors.append(f"ruff: {(r.stdout or r.stderr)[:300]}")
    return {
        "ok": not errors,
        "compiled": compiled,
        "ruff_ok": ruff_ok,
        "errors": errors,
    }


def step_quarantine() -> dict[str, Any]:
    """Re-quarantine public hosts (always after writers)."""
    from enterprise import quarantine_public_nodes

    return quarantine_public_nodes(dry_run=False)


def step_purity_repro(n: int = 3) -> dict[str, Any]:
    from enterprise import corpus_purity_audit

    hashes: list[str] = []
    reports: list[dict[str, Any]] = []
    for i in range(n):
        # write only on last pass to reduce audit noise; hashes must match either way
        r = corpus_purity_audit(write=(i == n - 1))
        hashes.append(str(r.get("report_hash") or ""))
        reports.append(
            {
                "i": i,
                "public_ratio_pct": r.get("public_ratio_pct"),
                "quarantined_nodes": r.get("quarantined_nodes"),
                "quarantine_coverage": r.get("quarantine_coverage"),
                "pilot_ops_ready": r.get("pilot_ops_ready"),
                "pilot_ready": r.get("pilot_ready"),
                "report_hash": r.get("report_hash"),
            }
        )
    unique = set(hashes)
    return {
        "ok": len(unique) == 1 and bool(hashes[0]),
        "runs": n,
        "reproducible": len(unique) == 1,
        "report_hash": hashes[0] if hashes else None,
        "reports": reports,
    }


def step_vector_reindex(*, reindex: bool = True) -> dict[str, Any]:
    """Always reindex after writers so doctor vector_parity is green."""
    from brain_lib import status
    from vector_manager import status as vs

    st = status() or {}
    v = vs() or {}
    n_before = int(st.get("node_count") or 0)
    vec_before = int(v.get("vectors") or 0)
    reindexed = False
    reindex_error = None
    attempts = 0
    if reindex:
        from vector_manager import reindex_all

        # Up to 5 attempts: concurrent watcher/concert can leave brief lag.
        for attempt in range(5):
            attempts = attempt + 1
            try:
                r = reindex_all() or {}
                if r.get("error"):
                    reindex_error = str(r.get("error"))[:200]
                    time.sleep(0.4 * attempt)
                    continue
                reindexed = True
                st = status() or {}
                v = vs() or {}
                n = int(st.get("node_count") or 0)
                vec = int(v.get("vectors") or 0)
                if n > 0 and n == vec:
                    break
                # Brief settle for mid-flight node writers (watcher_loop etc.)
                time.sleep(0.5 * attempt)
            except Exception as e:
                reindex_error = str(e)[:200]
                reindexed = False
                time.sleep(0.4 * attempt)
        st = status() or {}
        v = vs() or {}
    n = int(st.get("node_count") or 0)
    vec = int(v.get("vectors") or 0)
    out = {
        "ok": n > 0 and n == vec,
        "nodes": n,
        "vectors": vec,
        "nodes_before": n_before,
        "vectors_before": vec_before,
        "reindexed": reindexed,
        "attempts": attempts,
    }
    if reindex_error and not out["ok"]:
        out["reindex_error"] = reindex_error
    return out


def step_retrieve_hygiene() -> dict[str, Any]:
    """Ensure enterprise rank_evidence returns zero public hosts when clean pool exists."""
    from brain_lib import load_all_nodes
    from enterprise import is_public_host_node, rank_evidence

    nodes = load_all_nodes()
    ranked = rank_evidence(
        nodes,
        prompt="enterprise pilot clean internal evidence not public OSS",
        limit=12,
    )
    public_hits = [str(n.get("id")) for n in ranked if is_public_host_node(n)]
    clean = sum(1 for n in nodes if not is_public_host_node(n))
    return {
        "ok": len(public_hits) == 0 or clean < 6,
        "top_k": len(ranked),
        "top_k_public": len(public_hits),
        "clean_pool": clean,
        "sample_ids": [str(n.get("id")) for n in ranked[:6]],
        "public_ids": public_hits[:6],
    }


def step_swarm(n_agents: int = 16) -> dict[str, Any]:
    from agent_swarm import sweep

    # PB_SWARM_AGENTS defaults to 0 in beastMode; never run with 0 workers.
    n_agents = max(1, int(n_agents or 16))
    run_id = f"validate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    r = sweep(
        "Validate enterprise purity: prefer non-public evidence; cite clean nodes.",
        n_agents=n_agents,
        run_id=run_id,
    )
    ok_c = int(r.get("ok_count") or 0)
    n = int(r.get("n_agents") or n_agents)
    return {
        "ok": ok_c == n and n > 0,
        "ok_count": ok_c,
        "n_agents": n,
        "total_writes": r.get("total_writes"),
        "run_id": run_id,
        "ms": r.get("ms") or r.get("elapsed_ms"),
    }


def step_concert() -> dict[str, Any]:
    py = os.environ.get("VENV_PY") or str(_ROOT / "venv" / "bin" / "python3")
    if not Path(py).exists():
        py = sys.executable
    cmd = [
        py,
        str(_SCRIPTS / "orchestrate.py"),
        "concert",
        "--prompt",
        "Cite 2 clean internal-or-synthetic nodes not public OSS. Use node_id.",
        "--json",
    ]
    env = os.environ.copy()
    env["PB_ENTERPRISE"] = "1"
    env["PYTHONPATH"] = f"{_SCRIPTS}:{_ROOT}"
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    text = (p.stdout or "") + (p.stderr or "")
    try:
        d = json.loads(text[text.index("{") :])
    except Exception:
        return {"ok": False, "error": "no_json", "raw": text[:400], "rc": p.returncode}
    from enterprise import is_public_host_node
    from brain_lib import load_all_nodes

    by_id = {str(n.get("id")): n for n in load_all_nodes()}
    ev = (d.get("retrieve") or {}).get("evidence") or []
    public_ids: list[str] = []
    for e in ev:
        nid = str(e.get("id") or "")
        # Prefer full node from disk; fall back to evidence stub with uri.
        node = by_id.get(nid)
        if node is None:
            node = {
                "id": nid,
                "uri": e.get("uri") or "",
                "source": e.get("source"),
                "tags": e.get("tags") or [],
                "props": e.get("props") or {},
            }
        if is_public_host_node(node):
            public_ids.append(nid)
    public_ev = len(public_ids)
    return {
        "ok": bool(d.get("final_ok")) and public_ev == 0,
        "final_ok": d.get("final_ok"),
        "band": (d.get("rate") or {}).get("band"),
        "evidence_n": len(ev),
        "evidence_public": public_ev,
        "public_ids": public_ids[:6],
        "sample": [
            {"id": e.get("id"), "source": e.get("source"), "title": str(e.get("title") or "")[:48]}
            for e in ev[:6]
        ],
    }


def step_audit_chain() -> dict[str, Any]:
    from audit_lib import verify_chain

    ch = verify_chain() or {}
    return {
        "ok": bool(ch.get("ok")),
        "events": ch.get("events_checked") or ch.get("events"),
        "detail": {k: ch.get(k) for k in ("ok", "events_checked", "last_hash", "path") if k in ch},
    }


def step_doctor() -> dict[str, Any]:
    from enterprise import doctor_enterprise

    d = doctor_enterprise()
    return {"ok": bool(d.get("ok")), "checks": d.get("checks"), "warnings": d.get("warnings")}


def step_sap() -> dict[str, Any]:
    from enterprise import build_sap_pack

    p = build_sap_pack()
    manifest = p.get("manifest") if isinstance(p.get("manifest"), dict) else {}
    pur = (manifest or {}).get("corpus_purity") or p.get("corpus_purity")
    path = p.get("zip") or p.get("dir") or p.get("path") or p.get("dest") or ""
    ok = bool(p.get("ok", True)) and bool(path or manifest)
    return {
        "ok": ok,
        "path": path,
        "dir": p.get("dir"),
        "zip": p.get("zip"),
        "corpus_purity": pur,
        "manifest_keys": list(manifest.keys())[:20] if manifest else list(p.keys())[:20],
    }


def _write_summary(report: dict[str, Any], out_dir: Path) -> Path:
    """Human-readable summary for beastMode / operators."""
    pur = (report.get("detail") or {}).get("purity_repro", {}).get("result") or {}
    soft = report.get("soft") or {}
    lines = [
        f"ts={report.get('ts')}",
        f"hard_ok={report.get('hard_ok')}",
        f"ok={report.get('ok')}",
        f"report_hash={soft.get('report_hash') or pur.get('report_hash')}",
        f"fingerprint={report.get('fingerprint')}",
        f"pilot_ready(soft)={soft.get('pilot_ready')}",
        f"pilot_ops_ready={soft.get('pilot_ops_ready')}",
        f"public_ratio_pct={soft.get('public_ratio_pct')}",
        "order=" + " → ".join(STEP_ORDER),
        "steps:",
    ]
    for s in report.get("steps") or []:
        lines.append(f"  - {s.get('name')}: ok={s.get('ok')} ms={s.get('ms')}")
    doc = ((report.get("detail") or {}).get("doctor") or {}).get("result") or {}
    fails = [c for c in (doc.get("checks") or []) if not c.get("ok")]
    if fails:
        lines.append("doctor_fails:")
        for c in fails:
            lines.append(f"  - {c.get('name')}: {c.get('detail')}")
    path = out_dir / "validate_enterprise_summary.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Private Brain enterprise multi-agent validation")
    # Note: env PB_SWARM_AGENTS may be "0" (beastMode default); treat <=0 as 16.
    _env_agents = int(os.environ.get("PB_SWARM_AGENTS") or 16)
    ap.add_argument("--agents", type=int, default=16 if _env_agents <= 0 else _env_agents)
    ap.add_argument("--purity-runs", type=int, default=3)
    ap.add_argument("--skip-swarm", action="store_true")
    ap.add_argument("--skip-concert", action="store_true")
    ap.add_argument("--no-reindex", action="store_true")
    args = ap.parse_args()
    if int(args.agents) <= 0:
        args.agents = 16

    report: dict[str, Any] = {
        "ts": _ts(),
        "program": "validate_enterprise",
        "enterprise": os.environ.get("PB_ENTERPRISE"),
        "order": list(STEP_ORDER),
        "steps": [],
        "detail": {},
        "ok": False,
        "hard_ok": False,
        "soft": {},
    }

    # Fixed order: lint → swarm → concert → quarantine → purity×3 → retrieve
    # → vector reindex → audit_chain → doctor → sap_pack
    # Writers first; always re-quarantine + reindex after writers.
    _step("lint", step_lint, report)
    if not args.skip_swarm:
        _step("swarm", lambda: step_swarm(args.agents), report)
    if not args.skip_concert:
        _step("concert", step_concert, report)
    # Seal after writers
    _step("quarantine", step_quarantine, report)
    _step("purity_repro", lambda: step_purity_repro(args.purity_runs), report)
    _step("retrieve_hygiene", step_retrieve_hygiene, report)
    # Always reindex after writers (unless --no-reindex)
    _step("vector_reindex", lambda: step_vector_reindex(reindex=not args.no_reindex), report)
    _step("audit_chain", step_audit_chain, report)
    _step("doctor", step_doctor, report)
    _step("sap_pack", step_sap, report)

    # Hard gates (ops ready). soft pilot_ready is intentionally NOT a hard gate.
    hard_names = {
        "lint",
        "quarantine",
        "purity_repro",
        "vector_reindex",
        "retrieve_hygiene",
        "audit_chain",
        "doctor",
        "sap_pack",
    }
    if not args.skip_swarm:
        hard_names.add("swarm")
    if not args.skip_concert:
        hard_names.add("concert")

    hard_ok = all(
        s.get("ok") for s in report["steps"] if s.get("name") in hard_names
    )
    pur = (report["detail"].get("purity_repro") or {}).get("result") or {}
    last_pur = (pur.get("reports") or [{}])[-1] if pur.get("reports") else {}
    report["hard_ok"] = hard_ok
    report["soft"] = {
        "pilot_ready": last_pur.get("pilot_ready"),
        "pilot_ops_ready": last_pur.get("pilot_ops_ready"),
        "public_ratio_pct": last_pur.get("public_ratio_pct"),
        "report_hash": pur.get("report_hash"),
        "note": (
            "hard_ok ignores soft pilot_ready; pilot_ready needs internal re-ingest; "
            "pilot_ops_ready is quarantine+retrieve hygiene"
        ),
    }
    report["ok"] = hard_ok  # package/run ready = hard ops gates only
    report["report_hash"] = pur.get("report_hash")
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            {
                "steps": [(s["name"], s["ok"]) for s in report["steps"]],
                "report_hash": pur.get("report_hash"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    # persist + audit + summary
    out_dir = _ROOT / ".brain" / "state"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "validate_enterprise.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["path"] = str(out_path)
    summary_path = _write_summary(report, out_dir)
    report["summary_path"] = str(summary_path)
    try:
        from audit_lib import audit

        audit(
            "validate_enterprise",
            agent_id="validate",
            role="auditor",
            result="ok" if hard_ok else "fail",
            detail=f"hard_ok={hard_ok} hash={pur.get('report_hash', '')[:16]} steps={len(report['steps'])}",
            props={
                "hard_ok": hard_ok,
                "fingerprint": report["fingerprint"],
                "report_hash": pur.get("report_hash"),
                "pilot_ops_ready": last_pur.get("pilot_ops_ready"),
                "pilot_ready": last_pur.get("pilot_ready"),
            },
        )
    except Exception:
        pass

    print(json.dumps(report, indent=2, default=str))
    return 0 if hard_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
