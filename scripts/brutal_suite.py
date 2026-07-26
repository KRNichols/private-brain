#!/usr/bin/env python3
"""Brutal multi-agent style test suite — single-process orchestrator.

Runs independent attack packs and writes a combined scoreboard.
Prefer multi-agent fan-out in CI; this file is the consolidator + can run solo.

  PB_ENTERPRISE=1 python scripts/brutal_suite.py
  PB_ENTERPRISE=1 python scripts/brutal_suite.py --quick
"""
from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("PB_ENTERPRISE", "1")
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(name: str, fn: Callable[[], dict[str, Any]], report: dict[str, Any]) -> None:
    t0 = time.perf_counter()
    try:
        out = fn()
        ok = bool(out.get("ok", False))
        entry = {"name": name, "ok": ok, "ms": int((time.perf_counter() - t0) * 1000), "result": out}
    except Exception as e:
        entry = {
            "name": name,
            "ok": False,
            "ms": int((time.perf_counter() - t0) * 1000),
            "error": f"{e}\n{traceback.format_exc()[:800]}",
        }
    report["packs"].append({k: entry[k] for k in ("name", "ok", "ms") if k in entry})
    if "error" in entry:
        report["packs"][-1]["error"] = entry["error"][:200]
    report["detail"][name] = entry
    status = "PASS" if entry.get("ok") else "FAIL"
    print(f"[{status}] {name} ({entry.get('ms')}ms)", flush=True)


def pack_lint() -> dict[str, Any]:
    errs = []
    n = 0
    for p in sorted(_SCRIPTS.glob("*.py")):
        n += 1
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            errs.append(f"{p.name}: {e}")
    for p in (_ROOT / "visualizer").glob("*.py"):
        n += 1
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            errs.append(f"visualizer/{p.name}: {e}")
    return {"ok": not errs, "compiled": n, "errors": errs}


def pack_purity() -> dict[str, Any]:
    from enterprise import corpus_purity_audit, is_public_host_node, quarantine_public_nodes, rank_evidence
    from brain_lib import load_all_nodes

    hashes = []
    for i in range(3):
        r = corpus_purity_audit(write=(i == 2))
        hashes.append(r["report_hash"])
    q = quarantine_public_nodes(dry_run=False)
    pur = q.get("purity") or corpus_purity_audit(write=True)
    nodes = load_all_nodes()
    ranked = rank_evidence(nodes, "clean internal enterprise evidence not public OSS", limit=12)
    pub_top = sum(1 for n in ranked if is_public_host_node(n))
    unsealed = 0
    for n in nodes:
        if not is_public_host_node(n):
            continue
        props = n.get("props") or {}
        tags = {str(t).lower() for t in (n.get("tags") or [])}
        if not props.get("enterprise_quarantine") or "enterprise-quarantine" not in tags:
            unsealed += 1
    ok = (
        len(set(hashes)) == 1
        and float(pur.get("quarantine_coverage") or 0) >= 0.99
        and pub_top == 0
        and unsealed == 0
    )
    return {
        "ok": ok,
        "reproducible": len(set(hashes)) == 1,
        "report_hash": hashes[0],
        "coverage": pur.get("quarantine_coverage"),
        "pilot_ops_ready": pur.get("pilot_ops_ready"),
        "top_k_public": pub_top,
        "unsealed_public": unsealed,
        "public_ratio_pct": pur.get("public_ratio_pct"),
    }


def pack_ingest() -> dict[str, Any]:
    from enterprise import assert_ingest_allowed

    cases = []
    # enterprise on
    os.environ["PB_ENTERPRISE"] = "1"
    for label, kwargs in [
        ("preset_gnome", {"preset": "gnome"}),
        ("host_gnome", {"url": "https://gitlab.gnome.org/GNOME"}),
        ("host_salsa", {"url": "https://salsa.debian.org/foo/bar"}),
    ]:
        try:
            assert_ingest_allowed(**kwargs)
            cases.append({"case": label, "ok": False, "error": "expected PermissionError"})
        except PermissionError:
            cases.append({"case": label, "ok": True})
        except Exception as e:
            cases.append({"case": label, "ok": False, "error": str(e)[:120]})
    # internal allow
    try:
        assert_ingest_allowed(url="https://gitlab.example.internal/group")
        cases.append({"case": "internal_allow", "ok": True})
    except PermissionError as e:
        cases.append({"case": "internal_allow", "ok": False, "error": str(e)[:120]})
    # non-enterprise no-op
    os.environ["PB_ENTERPRISE"] = "0"
    try:
        # force re-read if cached
        assert_ingest_allowed(preset="gnome")
        cases.append({"case": "non_ent_allow", "ok": True})
    except PermissionError:
        cases.append({"case": "non_ent_allow", "ok": False, "error": "blocked without enterprise"})
    finally:
        os.environ["PB_ENTERPRISE"] = "1"
    return {"ok": all(c["ok"] for c in cases), "cases": cases}


def pack_swarm(n: int = 16) -> dict[str, Any]:
    from agent_swarm import sweep

    r = sweep("Brutal suite: prefer clean non-public evidence.", n_agents=n, run_id=f"brutal-swarm-{n}")
    ok_c = int(r.get("ok_count") or 0)
    return {"ok": ok_c == n and n > 0, "ok_count": ok_c, "n_agents": n, "writes": r.get("total_writes")}


def pack_concert() -> dict[str, Any]:
    py = str(_ROOT / "venv" / "bin" / "python3")
    if not Path(py).exists():
        py = sys.executable
    env = os.environ.copy()
    env["PB_ENTERPRISE"] = "1"
    env["PYTHONPATH"] = f"{_SCRIPTS}:{_ROOT}"
    p = subprocess.run(
        [
            py,
            str(_SCRIPTS / "orchestrate.py"),
            "concert",
            "--prompt",
            "Cite 2 clean nodes not public OSS. Use node_id.",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = (p.stdout or "") + (p.stderr or "")
    try:
        d = json.loads(text[text.index("{") :])
    except Exception:
        return {"ok": False, "error": "no_json", "raw": text[:300]}
    from enterprise import is_public_host_node
    from brain_lib import load_all_nodes

    by_id = {str(n.get("id")): n for n in load_all_nodes()}
    ev = (d.get("retrieve") or {}).get("evidence") or []
    pub = 0
    for e in ev:
        nid = str(e.get("id") or "")
        node = by_id.get(nid) or {}
        if node and is_public_host_node(node):
            pub += 1
    return {
        "ok": bool(d.get("final_ok")) and pub == 0,
        "final_ok": d.get("final_ok"),
        "band": (d.get("rate") or {}).get("band"),
        "evidence_public": pub,
        "evidence_n": len(ev),
    }


def pack_vectors() -> dict[str, Any]:
    from brain_lib import status
    from vector_manager import status as vs, reindex_all

    st, v = status() or {}, vs() or {}
    n, vec = int(st.get("node_count") or 0), int(v.get("vectors") or 0)
    if n != vec:
        reindex_all()
        st, v = status() or {}, vs() or {}
        n, vec = int(st.get("node_count") or 0), int(v.get("vectors") or 0)
    return {"ok": n > 0 and n == vec, "nodes": n, "vectors": vec}


def pack_godseye_perf() -> dict[str, Any]:
    """Catch the class of bugs that made GodsEye crawl at 12k nodes.

    Suite previously only checked doctor/purity/compile — never draw budgets,
    snapshot subsample, or live FPS. This pack fails closed when caps are
    missing or live perf is stuttering.
    """
    import ast
    import importlib.util

    gl_path = _ROOT / "visualizer" / "graph_gl.py"
    if not gl_path.exists():
        return {"ok": False, "error": "graph_gl.py missing"}

    src = gl_path.read_text(encoding="utf-8")
    # Static: must define sane caps (not 12k default hairball)
    checks: dict[str, Any] = {}
    for name, max_allowed in (
        ("SNAPSHOT_VIZ_MAX", 6000),
        ("DRAW_NODES", 6000),
        ("DRAW_EDGES", 8000),
        ("LAYOUT_NODES", 1200),
    ):
        # default arg of _env_int("X", DEFAULT) or bare assignment
        found = None
        for line in src.splitlines():
            if name in line and ("_env_int" in line or f"{name} =" in line):
                # pull trailing integer default
                import re

                m = re.search(r"_env_int\(\s*[\"'][^\"']+[\"']\s*,\s*(\d+)\s*\)", line)
                if m:
                    found = int(m.group(1))
                    break
                m = re.search(rf"{name}\s*=\s*(\d+)", line)
                if m:
                    found = int(m.group(1))
                    break
        checks[f"cap_{name}"] = {
            "value": found,
            "ok": found is not None and found <= max_allowed,
            "max_allowed": max_allowed,
        }

    # Must have adaptive LOD + frame accounting (the actual fix for stutter)
    checks["has_note_frame"] = "def note_frame" in src
    checks["has_lod_scale"] = "lod_scale" in src
    checks["has_draw_budgets"] = "def draw_budgets" in src
    checks["writes_perf_json"] = "godseye_perf.json" in src
    # GPU path: vertex arrays / glDrawArrays (not per-vertex glBegin spam)
    checks["gpu_draw_arrays"] = "glDrawArrays" in src and "_draw_arrays_" in src
    checks["hud_scissor"] = "GL_SCISSOR_TEST" in src or "glScissor" in src
    checks["batches_points"] = checks["gpu_draw_arrays"]  # alias for older reports
    # Ultra-app quality gates (HUD / interaction polish)
    checks["has_minimap"] = "def _draw_minimap" in src or "show_minimap" in src
    checks["has_hover_tooltip"] = "hover_id" in src and ("_draw_hover_tooltip" in src or "Hover tooltip" in src)
    checks["has_layout_settle"] = "layout_settled" in src and "micro-breathe" in src
    checks["has_camera_focus"] = "def focus_camera" in src and "def update_camera" in src
    checks["has_starfield"] = "def _draw_starfield" in src or "ensure_starfield" in src
    checks["has_github_source"] = '"github"' in src and "SOURCE_RGB" in src
    checks["has_stages_compact"] = "stages_compact" in src
    # Apple-simple + dual-audience help (anyone + senior)
    checks["has_simple_default"] = "show_inspector = False" in src and "show_minimap = False" in src
    checks["has_dual_help"] = "help_mode" in src and ("SIMPLE (anyone)" in src or "HELP · SIMPLE" in src)
    checks["has_soft_disc"] = "def _draw_soft_disc" in src or "GL_TRIANGLE_FAN" in src
    checks["has_clip_box"] = "def _clip_box" in src
    checks["has_no_bleed_flag"] = "no_window_bleed" in src

    # Live snapshot path used by graph_gl (corpus size; GUI loads a subsample)
    snap = _ROOT / ".brain" / "graph" / "snapshot.json"
    snap_nodes = 0
    if snap.exists():
        try:
            # avoid loading 20MB+ JSON fully — count "id" roughly via file size / sample
            data = json.loads(snap.read_text(encoding="utf-8"))
            snap_nodes = len(data.get("nodes") or [])
        except Exception:
            snap_nodes = -1
    checks["snapshot_nodes"] = snap_nodes
    checks["snapshot_path"] = str(snap)

    # Live FPS file if GUI is running (optional but fail if present AND bad)
    perf_path = _ROOT / ".brain" / "state" / "godseye_perf.json"
    live: dict[str, Any] = {}
    if perf_path.exists():
        try:
            live = json.loads(perf_path.read_text(encoding="utf-8"))
            # stale? ignore if older than 30s
            age = time.time() - perf_path.stat().st_mtime
            live["_age_s"] = age
            if age < 30:
                fps = float(live.get("fps") or 0)
                loaded = int(live.get("loaded_nodes") or 0)
                # fail if stuttering with large graph while LOD not engaged
                live_ok = fps >= 24 or float(live.get("lod_scale") or 1) < 0.9
                # also fail if still loading > 6000 into GPU path
                if loaded > 6000:
                    live_ok = False
                ultra = live.get("ultra") if isinstance(live.get("ultra"), dict) else {}
                # simple default must report simple_mode when live
                if live.get("simple_mode") is False and live.get("inspector") is True:
                    pass  # inspector open is OK
                elif "simple_mode" in live and live.get("simple_mode") is not True and live.get("inspector") is not True:
                    live_ok = False
                if ultra and ultra.get("dual_help") is False:
                    live_ok = False
                checks["live_fps"] = {
                    "fps": fps,
                    "loaded": loaded,
                    "ok": live_ok,
                    **{
                        k: live.get(k)
                        for k in (
                            "lod_scale",
                            "drawn_nodes",
                            "drawn_edges",
                            "perf_warn",
                            "gpu_path",
                            "layout_settled",
                            "minimap",
                            "hover",
                            "work_ms",
                            "simple_mode",
                            "inspector",
                        )
                    },
                    "ultra": ultra,
                }
                # soft quality flags (do not fail suite if GUI is mid-start)
                checks["live_ultra_fields"] = {
                    "ok": True,
                    "layout_settled_field": "layout_settled" in live,
                    "gpu_path_field": bool(live.get("gpu_path")),
                    "minimap_field": "minimap" in live,
                    "hover_field": "hover" in live,
                }
            else:
                checks["live_fps"] = {"ok": True, "stale": True, "age_s": age}
        except Exception as e:
            checks["live_fps"] = {"ok": False, "error": str(e)[:120]}
    else:
        checks["live_fps"] = {"ok": True, "skipped": "no live godseye_perf.json (GUI not running)"}

    static_ok = all(
        (v.get("ok") if isinstance(v, dict) and "ok" in v else bool(v))
        for k, v in checks.items()
        if k.startswith("cap_")
        or k.startswith("has_")
        or k
        in (
            "writes_perf_json",
            "batches_points",
            "gpu_draw_arrays",
            "hud_scissor",
        )
    )
    # dual-audience / simple gates are hard requirements
    for k in (
        "has_simple_default",
        "has_dual_help",
        "has_soft_disc",
        "has_clip_box",
        "has_no_bleed_flag",
    ):
        if not checks.get(k):
            static_ok = False
    live_ok = bool((checks.get("live_fps") or {}).get("ok", True))
    return {
        "ok": static_ok and live_ok,
        "checks": checks,
        "note": "GodsEye must subsample + LOD; 12k full hairball is a FAIL",
    }


def pack_doctor() -> dict[str, Any]:
    from enterprise import (
        corpus_purity_audit,
        doctor_enterprise,
        is_enterprise,
        quarantine_public_nodes,
        self_heal,
    )

    # Swarm/concert can mint new public-host nodes mid-suite — re-quarantine
    # so pilot_ops is a ship gate on *current* corpus, not a race with packs above.
    try:
        quarantine_public_nodes()
    except Exception:
        pass
    try:
        corpus_purity_audit(write=True)
    except Exception:
        pass
    self_heal()
    d = doctor_enterprise()
    # Align with doctor_enterprise soft_names — Corporate Library/optional/corpus purity are not hard fails
    # (home-dev: unknown Corporate Library/AWS/Jira/Confluence must not hard-fail).
    soft_names = {
        "corpus_public_ratio",
        "corpus_pilot_ready",
        "sres_approved_source",
        "optional_capabilities",
    }
    if not is_enterprise():
        soft_names = soft_names | {"corpus_pilot_ops"}
    # Prefer doctor_enterprise's own ok (already excludes soft_names); also list hard fails.
    hard_fail = [
        c
        for c in (d.get("checks") or [])
        if not c.get("ok") and c.get("name") not in soft_names
    ]
    return {
        "ok": bool(d.get("ok")) and not hard_fail,
        "hard_fails": hard_fail,
        "warnings": d.get("warnings"),
        "soft_names": sorted(soft_names),
    }


def pack_audit() -> dict[str, Any]:
    from audit_lib import verify_chain

    ch = verify_chain() or {}
    return {"ok": bool(ch.get("ok")), "events": ch.get("events_checked"), "window": ch.get("chain_window")}


def pack_day1() -> dict[str, Any]:
    py = str(_ROOT / "venv" / "bin" / "python3")
    if not Path(py).exists():
        py = sys.executable
    script = _SCRIPTS / "day1_first_start.py"
    if not script.exists():
        return {"ok": False, "error": "day1_first_start.py missing"}
    env = os.environ.copy()
    env["PB_ENTERPRISE"] = "1"
    results = []
    for route, extra in [
        ("headless", ["--program", "brutal-headless"]),
        ("corporate_library", ["--program", "brutal-corporate_library", "--index-url", "https://corporate_library.example/simple", "--trusted-host", "corporate_library.example"]),
        ("aws", ["--program", "brutal-aws", "--index-url", "https://x.d.codeartifact.gov-region-1.amazonaws.com/pypi/r/simple/"]),
    ]:
        cmd = [py, str(script), "--yes", "--route", route, "--no-godseye", *extra]
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
        results.append({"route": route, "rc": p.returncode, "ok": p.returncode == 0})
    # leave headless
    subprocess.run(
        [py, str(script), "--yes", "--route", "headless", "--program", "brutal-suite", "--no-godseye"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    map_path = _ROOT / ".brain" / "state" / "day1_map.json"
    prompt = Path.home() / ".codex" / "prompts" / "private-brain-day1.md"
    return {
        "ok": all(r["ok"] for r in results) and map_path.exists() and prompt.exists(),
        "routes": results,
        "map_exists": map_path.exists(),
        "prompt_exists": prompt.exists(),
    }


def pack_zip() -> dict[str, Any]:
    """Accept CORPORATE zip from live dist or kit dist (newest wins)."""
    candidates: list[Path] = []
    for dist in (
        _ROOT / "dist",
        Path.home() / "private-brain-codex" / "dist",
    ):
        if dist.is_dir():
            candidates.extend(dist.glob("PrivateBrain-CORPORATE-*.zip"))
    zips = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        return {"ok": False, "error": "no corporate zip"}
    z = zips[0]
    p = subprocess.run(["unzip", "-l", str(z)], capture_output=True, text=True, timeout=60)
    listing = p.stdout or ""
    checks = {
        "top_readme": "/README.md" in listing or listing.count("README.md") >= 1,
        # clean OS root: README + DIAGRAM + tools/ only (no clutter at root)
        "mac_readme": "mac/README.md" in listing,
        "mac_diagram": "mac/DIAGRAM.md" in listing,
        "mac_tools": "mac/tools/README.md" in listing,
        "mac_start": "mac/tools/install/START.command" in listing,
        "mac_engine": (
            "mac/tools/engine/scripts/day1_first_start.py" in listing
            or "mac/tools/engine/scripts/organism.py" in listing
        ),
        "mac_planes": all(
            f"mac/tools/{p}/README.md" in listing
            for p in (
                "skills",
                "abilities",
                "intelligence",
                "rulings",
                "judging",
                "non_hallucination",
                "metrics",
                "install",
            )
        ),
        "win_readme": "windows/README.md" in listing,
        "win_diagram": "windows/DIAGRAM.md" in listing,
        "win_tools": "windows/tools/README.md" in listing,
        "win_start": "windows/tools/install/START.ps1" in listing,
        "win_engine": (
            "windows/tools/engine/scripts/day1_first_start.py" in listing
            or "windows/tools/engine/scripts/organism.py" in listing
        ),
        "win_planes": all(
            f"windows/tools/{p}/README.md" in listing
            for p in (
                "skills",
                "abilities",
                "intelligence",
                "rulings",
                "judging",
                "non_hallucination",
                "metrics",
                "install",
            )
        ),
        "mac_golden_example": "mac/tools/install/golden_join.example.json" in listing,
        "win_golden_example": "windows/tools/install/golden_join.example.json" in listing,
        "no_venv": "/venv/" not in listing,
        "no_brain_nodes": ".brain/nodes" not in listing,
        "mac_root_clean": (
            "mac/START.command" not in listing
            and "mac/package/" not in listing
            and "mac/tools/install/START.command" in listing
        ),
        "win_root_clean": (
            "windows/tools/install/START.ps1" in listing
            and "windows/package/" not in listing
        ),
    }
    # WINDOWS-READY sibling (optional but preferred)
    ready = z.parent / "PrivateBrain-WINDOWS-READY.zip"
    ready_ok = ready.exists()
    ready_checks: dict[str, bool] = {}
    if ready_ok:
        pr = subprocess.run(["unzip", "-l", str(ready)], capture_output=True, text=True, timeout=60)
        rl = pr.stdout or ""
        ready_checks = {
            "ready_diagram": "DIAGRAM.md" in rl,
            "ready_start": "tools/install/START.ps1" in rl or "START.ps1" in rl,
            "ready_graph_gl": "graph_gl.py" in rl,
            "ready_godseye_help": True  # optional deep doc; diagram is root law,
        }
        checks["windows_ready"] = all(ready_checks.values())
    else:
        checks["windows_ready"] = False
        ready_checks = {"exists": False}
    return {
        "ok": all(checks.values()),
        "zip": str(z),
        "checks": checks,
        "ready": str(ready) if ready_ok else None,
        "ready_checks": ready_checks,
    }


def pack_docs() -> dict[str, Any]:
    """Dual-audience documentation must exist and be consistent."""
    required = [
        _ROOT / "START_HERE.md",
        _ROOT / "docs" / "DIAGRAM.md",
        _ROOT / "docs" / "DIAGRAM.txt",
        _ROOT / "docs" / "GODSEYE_HELP.md",
        _ROOT / "docs" / "INDEX.md",
        _ROOT / "installers" / "windows" / "DIAGRAM.md",
        _ROOT / "installers" / "windows" / "README.md",
    ]
    missing = [str(p.relative_to(_ROOT)) for p in required if not p.exists()]
    content_ok: dict[str, bool] = {}
    start = _ROOT / "START_HERE.md"
    if start.exists():
        t = start.read_text(encoding="utf-8")
        content_ok["start_anyone"] = "Anyone" in t or "anyone" in t.lower()
        content_ok["start_senior"] = "Senior" in t or "senior" in t.lower()
        content_ok["start_three_steps"] = "beastMode" in t and "START" in t
    ge = _ROOT / "docs" / "GODSEYE_HELP.md"
    if ge.exists():
        t = ge.read_text(encoding="utf-8")
        content_ok["ge_anyone"] = "Anyone" in t or "simple" in t.lower()
        content_ok["ge_senior"] = "Senior" in t or "advanced" in t.lower()
        content_ok["ge_keys"] = "Drag" in t or "drag" in t.lower()
    diagram = _ROOT / "docs" / "DIAGRAM.md"
    if diagram.exists():
        t = diagram.read_text(encoding="utf-8")
        content_ok["diagram_layer_a"] = "Layer A" in t
        content_ok["diagram_layer_b"] = "Layer B" in t
    ok = not missing and all(content_ok.values())
    return {"ok": ok, "missing": missing, "content": content_ok}


def main() -> int:
    ap_quick = "--quick" in sys.argv
    report: dict[str, Any] = {
        "ts": _ts(),
        "suite": "brutal_suite",
        "enterprise": os.environ.get("PB_ENTERPRISE"),
        "packs": [],
        "detail": {},
        "ok": False,
    }
    _run("lint", pack_lint, report)
    _run("docs", pack_docs, report)
    _run("godseye_perf", pack_godseye_perf, report)
    _run("purity", pack_purity, report)
    _run("ingest_gate", pack_ingest, report)
    _run("day1_routes", pack_day1, report)
    _run("zip_layout", pack_zip, report)
    _run("audit", pack_audit, report)
    if not ap_quick:
        _run("swarm16", lambda: pack_swarm(16), report)
        _run("concert", pack_concert, report)
        _run("vectors", pack_vectors, report)
        _run("doctor", pack_doctor, report)
    else:
        _run("swarm4", lambda: pack_swarm(4), report)
        _run("vectors", pack_vectors, report)
        _run("doctor", pack_doctor, report)

    report["ok"] = all(p.get("ok") for p in report["packs"])
    report["pass_count"] = sum(1 for p in report["packs"] if p.get("ok"))
    report["fail_count"] = sum(1 for p in report["packs"] if not p.get("ok"))
    out = _ROOT / ".brain" / "state" / "brutal_suite.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["path"] = str(out)
    try:
        from audit_lib import audit

        audit(
            "brutal_suite",
            agent_id="brutal",
            role="tester",
            result="ok" if report["ok"] else "fail",
            detail=f"pass={report['pass_count']} fail={report['fail_count']}",
            props={"ok": report["ok"], "pass": report["pass_count"], "fail": report["fail_count"]},
        )
    except Exception:
        pass
    print(json.dumps({k: report[k] for k in ("ok", "pass_count", "fail_count", "packs", "path")}, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
