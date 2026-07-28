#!/usr/bin/env python3
"""Canonical read-only E2E diagnostic — one JSON + concise human summary.

No network, crawl, ingestion, export rehash, source-body reads, GUI restart,
background process creation, or runtime mutation by default.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _codex() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser().resolve()


def _brain() -> Path:
    return Path(
        os.environ.get("PRIVATE_BRAIN_HOME") or (_codex() / "private-brain")
    ).expanduser().resolve()


def _load_json(path: Path) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"_error": "parse_failed", "path": str(path)}
    return None


def _run_json(argv: list[str], timeout: int = 60) -> Any:
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        raw = (r.stdout or "").strip()
        if not raw:
            return {"_error": "empty", "rc": r.returncode, "stderr": (r.stderr or "")[:200]}
        # last JSON object
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            return {"_error": "not_json", "rc": r.returncode, "tail": raw[-300:]}
    except Exception as e:
        return {"_error": str(e)[:200]}


def build_report() -> dict[str, Any]:
    codex = _codex()
    brain = _brain()
    scripts = brain / "scripts"
    state = brain / ".brain" / "state"
    py = sys.executable
    report: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": False,
        "classification": "unknown",
        "paths": {
            "CODEX_HOME": str(codex),
            "PRIVATE_BRAIN_HOME": str(brain),
            "hooks_json": str(codex / "hooks.json"),
        },
        "invalid_diagnostic_configuration": False,
    }

    # Path schema check
    if not brain.is_dir():
        report["invalid_diagnostic_configuration"] = True
        report["classification"] = "invalid_diagnostic_configuration"
        report["error"] = "PRIVATE_BRAIN_HOME missing"
        return report

    # Hooks
    hj = _load_json(codex / "hooks.json")
    wrappers = {
        "pb-session-start.cmd": (brain / "hooks" / "pb-session-start.cmd").is_file(),
        "pb-user-prompt-submit.cmd": (brain / "hooks" / "pb-user-prompt-submit.cmd").is_file(),
        "pb-stop-validate.cmd": (brain / "hooks" / "pb-stop-validate.cmd").is_file(),
    }
    hooks_ok = isinstance(hj, dict) and bool(hj.get("hooks")) and all(wrappers.values())
    # On non-Windows, .cmd may be installed but not required for runtime
    if not sys.platform.startswith("win"):
        hooks_ok = isinstance(hj, dict) and bool(hj.get("hooks"))
    report["hooks"] = {
        "hooks_json_present": isinstance(hj, dict),
        "wrappers": wrappers,
        "ok": hooks_ok,
    }

    # GodsEye — authoritative controller only
    ge_script = scripts / "godseye.py"
    if ge_script.is_file():
        ge = _run_json([py, str(ge_script), "status", "--json"], timeout=30)
    else:
        ge = {"_error": "godseye.py missing"}
    report["godseye"] = ge if isinstance(ge, dict) else {"_error": "bad_status"}

    # Doctor / audit / brain status — authoritative for vectors/corpus
    doctor = {}
    if (scripts / "enterprise.py").is_file():
        doctor = _run_json(
            [py, "-c", "from enterprise import doctor_enterprise; import json; print(json.dumps(doctor_enterprise(), default=str))"],
            timeout=90,
        )
    report["doctor"] = doctor if isinstance(doctor, dict) else {"_error": "doctor_failed"}

    # Standardize vector/corpus fields from doctor
    vec = {
        "node_count": None,
        "vector_count": None,
        "vector_parity": None,
        "public_ratio": None,
        "retrieval_ready": None,
    }
    if isinstance(doctor, dict):
        checks = doctor.get("checks") or doctor.get("results") or []
        if isinstance(checks, list):
            for c in checks:
                if not isinstance(c, dict):
                    continue
                name = c.get("name")
                detail = str(c.get("detail") or "")
                if name == "vector_parity":
                    vec["vector_parity"] = bool(c.get("ok"))
                    # parse nodes=N vectors=M
                    import re

                    m = re.search(r"nodes=(\d+)\s+vectors=(\d+)", detail)
                    if m:
                        vec["node_count"] = int(m.group(1))
                        vec["vector_count"] = int(m.group(2))
                if name == "corpus_public_ratio":
                    import re

                    m = re.search(r"([\d.]+)%", detail)
                    if m:
                        try:
                            vec["public_ratio"] = float(m.group(1)) / 100.0
                        except Exception:
                            pass
        for k in ("node_count", "nodes", "vector_count", "public_ratio"):
            if k in doctor and vec.get("node_count") is None and k == "node_count":
                vec["node_count"] = doctor.get(k)
        vec["retrieval_ready"] = bool(doctor.get("ok")) if "ok" in doctor else vec["vector_parity"]
    report["vector_corpus"] = vec

    # Audit
    audit = {}
    if (scripts / "audit_verify.py").is_file():
        audit = _run_json([py, str(scripts / "audit_verify.py"), "--json"], timeout=60)
        if isinstance(audit, dict) and audit.get("_error"):
            # try without --json
            try:
                r = subprocess.run(
                    [py, str(scripts / "audit_verify.py")],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                audit = {"rc": r.returncode, "tail": (r.stdout or r.stderr or "")[-400:]}
            except Exception as e:
                audit = {"_error": str(e)[:200]}
    report["audit"] = audit

    # Neo4J frozen metadata only (no rehash)
    neo = {
        "freeze": _load_json(state / "neoj_exports_freeze.json"),
        "reconciliation": _load_json(state / "neoj_exports_reconciliation.json"),
        "local_ingest": _load_json(state / "local_ingest_neoj_exports.json"),
    }
    # Correct false-positive path preservation if recon claims complete without paths
    recon = neo.get("reconciliation")
    if isinstance(recon, dict):
        # Prefer script if present
        if (scripts / "neoj_path_reconcile.py").is_file():
            fixed = _run_json([py, str(scripts / "neoj_path_reconcile.py"), "--json"], timeout=30)
            if isinstance(fixed, dict) and not fixed.get("_error"):
                neo["reconciliation_verified"] = fixed
    report["neo4j_metadata"] = neo

    # Graph source counts from status only
    graph = {}
    try:
        sys.path.insert(0, str(scripts))
        from brain_lib import status  # type: ignore

        st = status() or {}
        graph = {
            "node_count": st.get("node_count"),
            "edge_count": st.get("edge_count"),
        }
    except Exception as e:
        graph = {"error": str(e)[:120]}
    report["graph"] = graph

    # Product readiness (structured, not heuristic)
    if (scripts / "product_readiness.py").is_file():
        prod = _run_json([py, str(scripts / "product_readiness.py")], timeout=30)
    else:
        prod = {"_error": "product_readiness missing"}
    report["product"] = prod if isinstance(prod, dict) else {"_error": "bad"}

    # Classification
    core_ok = bool(
        (isinstance(doctor, dict) and doctor.get("ok") is not False)
        or (vec.get("vector_parity") is True)
    )
    ge_alive = False
    if isinstance(ge, dict):
        ge_alive = bool(ge.get("gui_running") or (ge.get("alive_count") or 0) > 0)
    product_ok = isinstance(prod, dict) and prod.get("installer_integration") is True

    degraded = []
    if not hooks_ok:
        degraded.append("hooks")
    if isinstance(ge, dict) and ge.get("enabled") and not ge_alive:
        degraded.append("godseye_not_running")
    if not product_ok:
        degraded.append("local_rag_product")

    if report.get("invalid_diagnostic_configuration"):
        report["classification"] = "invalid_diagnostic_configuration"
    elif core_ok and not degraded:
        report["classification"] = "HEALTHY"
        report["ok"] = True
    elif core_ok:
        report["classification"] = "DEGRADED_BUT_CORE_HEALTHY"
        report["ok"] = False
        report["degraded"] = degraded
    else:
        report["classification"] = "UNHEALTHY"
        report["ok"] = False
        report["degraded"] = degraded

    report["summary"] = (
        f"{report['classification']} · hooks={hooks_ok} · "
        f"godseye_alive={ge_alive} · product={product_ok} · "
        f"vector_parity={vec.get('vector_parity')} nodes={vec.get('node_count')}"
    )
    return report


def main() -> int:
    rep = build_report()
    print(json.dumps(rep, indent=2, default=str))
    print("\n=== SUMMARY ===")
    print(rep.get("summary") or rep.get("classification"))
    # Diagnostic always exits 0 unless invalid config hard-fail requested
    if rep.get("invalid_diagnostic_configuration") and os.environ.get("PB_E2E_STRICT") == "1":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
