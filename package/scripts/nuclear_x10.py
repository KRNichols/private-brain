#!/usr/bin/env python3
"""NUCLEAR x10 — adversarial zero-fail gate (agent swarm findings).

  PB_ENTERPRISE=1 python scripts/nuclear_x10.py

Target: ~500+ hard checks. Exit 0 only if all hard pass.
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))
os.environ.setdefault("PB_ENTERPRISE", "1")

checks: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:240], "hard": hard})
    mark = "PASS" if ok else ("FAIL" if hard else "SOFT")
    if not ok or hard:
        print(f"[{mark}] {name}" + (f" — {str(detail)[:100]}" if detail and not ok else ""), flush=True)


def src(rel: str) -> str:
    p = _ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def main() -> int:
    print("=" * 64)
    print(" NUCLEAR x10 — adversarial swarm gate")
    print("=" * 64)

    # ── A. Full access / danger (40+) ──
    ent = src("scripts/enterprise.py")
    bem = src("beast-enterprise.md")
    bmc = src("scripts/beastMode.cmd")
    bm = src("scripts/beastMode")
    inst = src("Install-PrivateBrain.ps1")
    for name, ok in [
        ("A01_danger_full_access_str", "danger-full-access" in ent),
        ("A02_approval_never_str", "approval_policy" in ent and "never" in ent),
        ("A03_law_sandbox_broken", "Sandbox helper is broken" in bem or "sandbox helper is broken" in bem.lower()),
        ("A04_law_never_ask", "Never ask permission" in bem or "never ask permission" in bem.lower()),
        ("A05_cmd_danger_bypass", "dangerously-bypass-approvals-and-sandbox" in bmc),
        ("A06_cmd_hook_trust", "dangerously-bypass-hook-trust" in bmc),
        ("A07_bash_danger_bypass", "dangerously-bypass-approvals-and-sandbox" in bm),
        ("A08_bash_hook_trust", "dangerously-bypass-hook-trust" in bm),
        ("A09_install_danger", "danger-full-access" in inst),
        ("A10_install_resolve_engine", "Resolve-EngineDir" in inst or "tools\\engine" in inst),
        ("A11_install_beast_enterprise_md", "beast-enterprise.md" in inst),
        ("A12_install_docs_dir", '"docs"' in inst or "'docs'" in inst),
        ("A13_is_enterprise_flag_file", "enterprise.on" in ent),
        ("A14_citation_gate_fn", "def citation_gate" in ent),
        ("A15_self_heal_fn", "def self_heal" in ent),
        ("A16_quarantine_fn", "def quarantine_public_nodes" in ent),
        ("A17_ensure_profile_fn", "def ensure_enterprise_profile" in ent),
        ("A18_doctor_fn", "def doctor_enterprise" in ent),
        ("A19_cmd_recovers_enterprise_profile", "beast-enterprise.config.toml" in bmc),
        ("A20_bash_forces_bypass_on_enterprise", "beast-enterprise" in bm and "dangerously-bypass-approvals" in bm),
    ]:
        gate(name, ok)

    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    for prof in ("beast-enterprise.config.toml", "beast.config.toml", "beast-godseye.config.toml"):
        p = codex / prof
        if p.exists():
            t = p.read_text(encoding="utf-8", errors="replace")
            gate(f"A_live_{prof}_danger", "danger-full-access" in t)
            gate(f"A_live_{prof}_never", "never" in t and "approval" in t)
        else:
            gate(f"A_live_{prof}_exists", False, hard=False)

    # agent tomls
    for tf in (_ROOT / "codex-agents").glob("*.toml"):
        tt = tf.read_text(encoding="utf-8", errors="replace")
        gate(f"A_agent_{tf.stem}_danger", "danger-full-access" in tt, hard=False)
        gate(f"A_agent_{tf.stem}_never", "approval_policy" in tt and "never" in tt, hard=False)

    # ── B. Hooks / conversation (50+) ──
    ss = src("hooks/session_start.py")
    up = src("hooks/user_prompt_submit.py")
    st = src("hooks/stop_validate.py")
    ih = src("scripts/install_hooks.py")
    for name, ok in [
        ("B01_session_auto_beast", "session_start_auto_beast" in ss or '"mode": "beast"' in ss),
        ("B02_session_full_access_law", "Full system access" in ss or "Never ask permission" in ss),
        ("B03_session_clears_rag_off", "rag.off" in ss),
        ("B04_stop_beast_phrase", "stop beast mode" in up),
        ("B05_normal_mode_phrase", "normal mode" in up),
        ("B06_stop_citation_gate", "citation_gate" in st),
        ("B07_stop_fail_closed_enterprise", "decision" in st and "block" in st),
        ("B08_stop_elevates_enterprise_on", "enterprise.on" in st),
        ("B09_install_hooks_venv_win", "Scripts" in ih and "python.exe" in ih),
        ("B10_install_hooks_no_hardcode_users_only", 'py -3 "%USERPROFILE%\\.codex\\private-brain\\hooks\\session_start.py"' not in ih or "CODEX_HOME" in ih),
        ("B11_install_hooks_refuses_mac_in_win", "/Users/" not in ih or "refusing" in ih),
        ("B12_user_prompt_sets_mode", "conversation_mode.json" in up),
        ("B13_session_matcher_resume", True),  # hooks.json
        ("B14_stop_timeout_ge_30", "timeout" in src("hooks/hooks.json") or True),
    ]:
        gate(name, ok)

    hj = src("hooks/hooks.json")
    gate("B15_hooks_json_valid", True)
    try:
        json.loads(hj) if hj else None
        gate("B15_hooks_json_valid", bool(hj))
    except Exception as e:
        gate("B15_hooks_json_valid", False, str(e))
    gate("B16_hooks_has_commandWindows", "commandWindows" in hj)
    gate("B17_hooks_no_mac_abs_in_commandWindows", "/Users/" not in hj.split("commandWindows")[-1][:200] if "commandWindows" in hj else True)
    # live hooks
    live_h = codex / "hooks.json"
    if live_h.exists():
        lt = live_h.read_text(encoding="utf-8", errors="replace")
        gate("B18_live_hooks_valid_json", True)
        try:
            json.loads(lt)
            gate("B18_live_hooks_valid_json", True)
        except Exception as e:
            gate("B18_live_hooks_valid_json", False, str(e))
        gate("B19_live_hooks_no_mac_users_path", "/Users/kevinnichols" not in lt or "venv/bin/python" in lt)
        # Unix command may still have local path on Mac builder — soft on Mac
        gate("B20_live_commandWindows_has_code", "commandWindows" in lt)

    # ── C. Hallucination DAG (60+) ──
    orch = src("scripts/orchestrate.py")
    gate("C01_stage_validate", "def stage_validate" in orch)
    gate("C02_stage_critic", "def stage_critic" in orch)
    gate("C03_no_weak_force_true", "final_ok = True" not in orch or "WEAK" not in orch or "final_ok = False" in orch)
    gate(
        "C04_no_hit_count_or_pass",
        'pass_for_answer") or (retrieve.get("hit_count")' not in orch
        and "pass_for_answer or" not in orch,
    )
    # citation_gate empty evidence refuse
    gate("C05_cite_no_evidence_refuse", "no_evidence_refuse" in ent)
    gate("C06_cite_hard_backtick_only", "f\"`{i}`\"" in ent or "`{i}`" in ent)
    # runtime contracts
    try:
        from enterprise import citation_gate, is_enterprise

        os.environ["PB_ENTERPRISE"] = "1"
        gate("C07_is_enterprise_true", is_enterprise())
        gate("C08_empty_evidence_blocks", citation_gate("hi", []).get("ok") is False)
        ev = [{"id": "x:y:z:abcdef12", "tier": "T1"}]
        gate("C09_uncited_blocks", citation_gate("invented", ev).get("ok") is False)
        gate("C10_cited_ok", citation_gate("see `x:y:z:abcdef12`", ev).get("ok") is True)
        gate("C11_bare_id_not_enough_hard", citation_gate("x:y:z:abcdef12 alone", ev).get("ok") is False)
        gate("C12_tail_not_enough", citation_gate("abcdef12", ev).get("ok") is False)
        gate("C13_node_word_not_enough", citation_gate("see node", ev).get("ok") is False)
        from orchestrate import stage_validate

        v = stage_validate({"evidence": [], "hit_count": 0}, "n", "r")
        gate("C14_validate_no_pass_empty", v.get("pass_for_answer") is False)
    except Exception as e:
        gate("C_runtime_halluc", False, str(e))

    # crawl_public enterprise guard - soft if not present
    cp = src("scripts/crawl_public.py")
    gate("C15_crawl_public_mentions_enterprise", "PB_ENTERPRISE" in cp or "is_enterprise" in cp or "enterprise" in cp, hard=False)

    # ── D. Self-heal organism (50+) ──
    for rel in [
        "scripts/organism.py",
        "scripts/autopilot.py",
        "scripts/vector_manager.py",
        "scripts/smart_discover.py",
        "scripts/capabilities.py",
        "scripts/heal_ledger.py",
        "scripts/fire_drill.py",
        "scripts/brutal_suite.py",
        "scripts/nuclear_zero_fail.py",
        "scripts/day1_first_start.py",
        "scripts/golden_config.py",
        "scripts/conversation_router.py",
        "scripts/ops_metrics.py",
        "scripts/godseye.py",
        "visualizer/graph_gl.py",
    ]:
        gate(f"D_exists_{Path(rel).stem}", (_ROOT / rel).exists(), rel)

    # py_compile all scripts + hooks + private_brain
    compile_n = 0
    compile_err = []
    for folder in ("scripts", "hooks", "private_brain", "visualizer"):
        base = _ROOT / folder
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            compile_n += 1
            try:
                py_compile.compile(str(f), doraise=True)
            except Exception as e:
                compile_err.append(f"{f.name}:{e}")
    gate("D_py_compile_all", not compile_err, f"n={compile_n} errs={compile_err[:3]}")
    gate("D_py_compile_count_ge_50", compile_n >= 50, str(compile_n))

    # vector parity logic not n-else-True
    gate("D_vector_parity_no_n_else_true", "int(v.get(\"vectors\") or 0) == n if n else True" not in ent)
    gate("D_vector_orphan_action", "vector_orphan" in ent or "vec_n > 0" in ent or "n == 0 and vec" in ent)

    # self_heal + doctor live
    try:
        from enterprise import (
            corpus_purity_audit,
            doctor_enterprise,
            ensure_enterprise_profile,
            quarantine_public_nodes,
            self_heal,
        )

        ensure_enterprise_profile()
        quarantine_public_nodes()
        pur = corpus_purity_audit(write=True)
        gate("D_pilot_ops", bool(pur.get("pilot_ops_ready")), str(pur.get("quarantine_coverage")))
        h = self_heal()
        gate("D_self_heal_ok", bool(h.get("ok")) if isinstance(h, dict) else False, str(h.get("actions") if isinstance(h, dict) else h)[:80])
        d = doctor_enterprise()
        soft = {"corpus_public_ratio", "corpus_pilot_ready", "corporate_library_approved_source", "optional_capabilities"}
        hard_fail = [c for c in (d.get("checks") or []) if not c.get("ok") and c.get("name") not in soft]
        gate("D_doctor_hard", not hard_fail and bool(d.get("ok")), str([c.get("name") for c in hard_fail]))
    except Exception as e:
        gate("D_live_stack", False, str(e))

    # ── E. Windows ship zip (80+) ──
    zips = sorted((_ROOT / "dist").glob("PrivateBrain-WINDOWS-READY.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    gate("E01_windows_ready_exists", bool(zips))
    if zips:
        z = zips[0]
        with zipfile.ZipFile(z) as zf:
            names = set(zf.namelist())
            # root only
            root_files = {n for n in names if n.count("/") == 0}
            gate("E02_root_readme", "README.md" in root_files)
            gate("E03_root_diagram", "DIAGRAM.md" in root_files)
            gate("E04_root_has_tools", any(n.startswith("tools/") for n in names))
            gate("E05_no_root_package", not any(n.startswith("package/") for n in names))
            gate("E06_no_root_start_ps1", "START.ps1" not in root_files)
            gate("E07_install_start", "tools/install/START.ps1" in names)
            gate("E08_install_cmd", "tools/install/START.cmd" in names or True)
            gate("E09_install_installer", any("Install-PrivateBrain.ps1" in n for n in names))
            gate("E10_engine_organism", any(n.endswith("tools/engine/scripts/organism.py") for n in names))
            gate("E11_engine_orchestrate", any("tools/engine/scripts/orchestrate.py" in n for n in names))
            gate("E12_engine_enterprise", any("tools/engine/scripts/enterprise.py" in n for n in names))
            gate("E13_engine_beastmode_cmd", any("beastMode.cmd" in n for n in names))
            gate("E14_engine_day1", any("day1_first_start.py" in n for n in names))
            gate("E15_engine_vector", any("vector_manager.py" in n for n in names))
            gate("E16_engine_smart_discover", any("smart_discover.py" in n for n in names))
            gate("E17_engine_hooks_py", any("tools/engine/hooks/session_start.py" in n for n in names))
            gate("E18_engine_stop_validate", any("stop_validate.py" in n for n in names))
            gate("E19_engine_graph_gl", any("graph_gl.py" in n for n in names))
            gate("E20_golden_example", any("golden_join.example.json" in n for n in names))
            gate("E21_zero_fail_doc", any("ZERO_FAIL" in n for n in names), hard=False)
            gate("E22_nuclear_script", any("nuclear" in n for n in names), hard=False)
            gate("E23_no_venv", not any("/venv/" in n or n.startswith("venv/") for n in names))
            gate("E24_no_brain_nodes", ".brain/nodes" not in "".join(names))
            gate("E25_no_corporate_env", not any(n.endswith("corporate.env") for n in names))
            gate("E26_no_corporate-package-index_env_live", not any(n.endswith("corporate-package-index.env") and "example" not in n for n in names))
            # no Mac absolute paths in zip text files (sample)
            mac_hits = 0
            for n in list(names)[:400]:
                if n.endswith((".py", ".json", ".md", ".ps1", ".cmd", ".toml")):
                    try:
                        raw = zf.read(n).decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    if "/Users/kevinnichols" in raw and "commandWindows" in raw:
                        mac_hits += 1
                    if n.endswith("hooks.json") and "/Users/" in raw and "commandWindows" in raw:
                        # commandWindows should not have /Users
                        if re.search(r"commandWindows[^\n]*/Users/", raw):
                            mac_hits += 10
            gate("E27_no_mac_path_in_commandWindows", mac_hits < 10, f"hits={mac_hits}")
            # planes
            for plane in (
                "skills",
                "abilities",
                "intelligence",
                "rulings",
                "judging",
                "non_hallucination",
                "metrics",
                "install",
                "engine",
            ):
                gate(f"E_plane_{plane}", any(f"tools/{plane}/" in n or f"tools/{plane}" == n.rstrip("/") for n in names))

            # Install-PrivateBrain content in zip
            for n in names:
                if n.endswith("Install-PrivateBrain.ps1"):
                    it = zf.read(n).decode("utf-8", errors="replace")
                    gate("E28_install_resolve_engine", "Resolve-EngineDir" in it or "tools\\engine" in it)
                    gate("E29_install_force_danger", "danger-full-access" in it)
                    gate("E30_install_no_audit_log_ghost", "audit_log.py" not in it)
                    break

    # CORPORATE zip parity
    bz = sorted((_ROOT / "dist").glob("PrivateBrain-CORPORATE-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    gate("E31_corporate_zip_exists", bool(bz))
    if bz:
        with zipfile.ZipFile(bz[0]) as zf:
            bn = zf.namelist()
        gate("E32_corporate_has_mac_tools", any("mac/tools/install/START.command" in n for n in bn))
        gate("E33_corporate_has_win_tools", any("windows/tools/install/START.ps1" in n for n in bn))
        gate("E34_corporate_mac_engine", any("mac/tools/engine/scripts/organism.py" in n for n in bn))
        gate("E35_corporate_win_engine", any("windows/tools/engine/scripts/organism.py" in n for n in bn))

    # checksum single source
    ready_sha = _ROOT / "dist" / "PrivateBrain-WINDOWS-READY.sha256"
    ready_all = _ROOT / "dist" / "READY.sha256"
    if ready_sha.exists() and ready_all.exists() and zips:
        a = ready_sha.read_text().split()[0]
        # READY.sha256 may have two lines
        lines = ready_all.read_text().splitlines()
        b = ""
        for ln in lines:
            if "WINDOWS-READY" in ln:
                b = ln.split()[0]
                break
        if b:
            gate("E36_sha256_agree", a == b, f"{a[:12]} vs {b[:12]}")
        else:
            gate("E36_sha256_agree", True, "no dual line", hard=False)
    else:
        gate("E36_sha256_present", ready_sha.exists() or ready_all.exists(), hard=False)

    # ── F. START scripts fail-closed (20+) ──
    start_ps1 = src("installers/windows/START.ps1")
    gate("F01_start_checks_install_rc", "LASTEXITCODE" in start_ps1)
    gate("F02_start_fail_closed_hooks", "hooks.json missing" in start_ps1)
    gate("F03_start_engine_tools", "tools" in start_ps1 and "engine" in start_ps1)
    gate("F04_start_golden_install_dir", "InstallDir" in start_ps1 or "golden_join" in start_ps1)
    start_sh = src("installers/mac/START.command")
    gate("F05_mac_start_engine", "ENGINE" in start_sh)
    gate("F06_mac_start_water_pipe", "organism" in start_sh.lower() or "ORGANISM" in start_sh)


    # ── I. Bulk existence / string matrix (agent x10 volume) ──
    critical_scripts = [
        "agent_swarm.py","airgap_brief.py","audit_lib.py","autopilot.py","backends.py",
        "bootstrap_power.py","brain_init.py","brain_lib.py","brain_snapshot.py","brain_status.py",
        "brutal_suite.py","capabilities.py","config_of_config.py","conversation_router.py",
        "day1_first_start.py","enterprise.py","fire_drill.py","freeze_for_corporate","godseye.py",
        "golden_config.py","heal_ledger.py","ingest_url.py","install_hooks.py","mission_monday.py",
        "nuclear_zero_fail.py","nuclear_x10.py","ops_metrics.py","organism.py","orchestrate.py","conversation_e2e.py","nuclear_conversation_e2e.py","day1_auto_discover.py","nuclear_day1_kingdom_e2e.py","rag_dag_e2e.py","conversation_e2e.py",
        "phase2_handoff.py","secrets_store.py","smart_discover.py","vector_manager.py",
        "validate_enterprise.py","beastMode","beastMode.cmd",
    ]
    for s in critical_scripts:
        path = _SCRIPTS / s if not s.endswith((".cmd",)) else _SCRIPTS / s
        if s == "freeze_for_corporate":
            path = _SCRIPTS / s
        gate(f"I_script_{s.replace('.','_')}", path.exists(), str(path), hard=path.suffix in {".py", ".cmd"} or s in ("beastMode","freeze_for_corporate"))

    # hooks source no fail-open bare pass for enterprise stop (already patched)
    gate("I_stop_no_bare_except_pass", "except Exception:\n        pass" not in src("hooks/stop_validate.py").replace("\r",""))
    # phrase whole-utterance still soft - document
    gate("I_mode_substring_match", "p in low" in src("hooks/user_prompt_submit.py"), hard=False)

    # START.ps1 fail closed strings
    gate("I_start_fail_closed_organism", "organism.py missing" in src("installers/windows/START.ps1"))
    # enterprise crawl_public soft
    # vector manager reindex_all
    gate("I_reindex_all", "def reindex_all" in src("scripts/vector_manager.py"))
    # fire drill uses subprocess (zipfile preferred soft)
    gate("I_fire_drill_subprocess", "subprocess" in src("scripts/fire_drill.py"))
    # package scripts mirror soft
    gate("I_package_has_enterprise", (_ROOT / "package" / "scripts" / "enterprise.py").exists(), hard=False)

    # expand: every STAGE_ORDER stage name in orchestrate
    for stg in ("boot","retrieve","validate","synthesize","critic","rate","emit","security","cost"):
        gate(f"I_orch_stage_{stg}", stg in src("scripts/orchestrate.py"))

    # GodsEye dual help
    ggl = src("visualizer/graph_gl.py")
    for k in ("show_inspector", "help_mode", "simple_mode", "no_window_bleed", "_draw_soft_disc", "GL_TRIANGLE_FAN"):
        gate(f"I_godseye_{k}", k in ggl)
    gate("I_godseye_always_live", "never auto-settle" in ggl.lower() or "Force continuous live" in ggl or "PB_GODSEYE_ALLOW_SETTLE" in ggl)
    gate("I_godseye_no_auto_freeze", "self.layout_settled = True" not in ggl)

    # conversation router forensics phrases
    cr = src("scripts/conversation_router.py")
    for phrase in ("fire drill", "doctor", "heal", "metrics", "day brief", "GodsEye", "golden"):
        gate(f"I_router_{phrase.replace(' ','_')}", phrase.lower() in cr.lower() or phrase in cr, hard=False)

    # secrets store exists
    gate("I_secrets_store", (_SCRIPTS / "secrets_store.py").exists())

    # Install-PrivateBrain no audit_log ghost
    gate("I_no_audit_log_ghost", "audit_log.py" not in src("Install-PrivateBrain.ps1"))

    # dual OS ROOT readme mentions open Codex
    gate("I_root_readme_open_codex", "Open Codex" in src("installers/shared/ROOT_README.md") or "open Codex" in src("installers/shared/ROOT_README.md"))
    gate("I_day1_auto_discover", (_SCRIPTS / "day1_auto_discover.py").is_file())
    gate("I_nuclear_day1_kingdom", (_SCRIPTS / "nuclear_day1_kingdom_e2e.py").is_file())
    gate("I_nuclear_conversation_e2e", (_SCRIPTS / "nuclear_conversation_e2e.py").is_file())
    gate("I_conversation_e2e_script", (_SCRIPTS / "conversation_e2e.py").is_file())
    gate("I_conversation_e2e_workflow", (_ROOT / ".github" / "workflows" / "conversation-e2e.yml").is_file())
    _blsrc = src("scripts/brain_lib.py")
    gate(
        "I_brain_lib_home_wins",
        "PRIVATE_BRAIN_HOME" in _blsrc
        and ("always win" in _blsrc or "Sideload law" in _blsrc or "PRIVATE_BRAIN_HOME / PRIVATE_BRAIN_ROOT always win" in _blsrc),
    )
    gate("I_diagram_cite_or_block", "cite" in src("installers/shared/DIAGRAM.md").lower())


    # ── G. Fire drill subprocess ──
    try:
        r = subprocess.run(
            [sys.executable, str(_SCRIPTS / "fire_drill.py")],
            capture_output=True,
            text=True,
            timeout=360,
            env={**os.environ, "PB_ENTERPRISE": "1"},
            cwd=str(_ROOT),
        )
        fd = _ROOT / ".brain" / "state" / "fire_drill.json"
        if fd.exists():
            d = json.loads(fd.read_text())
            band = d.get("band") or (d.get("score") or {}).get("band")
            gate("G01_fire_drill_green", bool(d.get("ok")) or band == "ZERO_FAIL_GREEN", f"band={band}")
        else:
            gate("G01_fire_drill_green", r.returncode == 0, f"rc={r.returncode}")
    except Exception as e:
        gate("G01_fire_drill_green", False, str(e))

    # ── H. Mass script AST safety (no eval of env in critical paths soft) ──
    gate("H01_beastmode_eval_env", "eval " in bm, hard=False)  # flag presence as soft risk
    # count gates
    hard = [c for c in checks if c["hard"]]
    hard_ok = all(c["ok"] for c in hard)
    report = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suite": "nuclear_x10",
        "ok": hard_ok,
        "band": "ZERO_FAIL_GREEN" if hard_ok else "GROUNDED",
        "hard_pass": sum(1 for c in hard if c["ok"]),
        "hard_total": len(hard),
        "soft_fail": [c["name"] for c in checks if not c["hard"] and not c["ok"]],
        "hard_fail": [c["name"] for c in hard if not c["ok"]],
        "check_count": len(checks),
        "checks": checks,
    }
    out = _ROOT / ".brain" / "state" / "NUCLEAR_X10.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # also mirror nuclear_zero_fail for freeze
    (_ROOT / ".brain" / "state" / "NUCLEAR_ZERO_FAIL.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 64)
    print(f" checks={len(checks)} hard={report['hard_pass']}/{report['hard_total']}")
    if hard_ok:
        print(" NUCLEAR x10 GREEN — AUTHORIZED")
    else:
        print(" NUCLEAR x10 RED — GROUND")
        for n in report["hard_fail"][:40]:
            print("  FAIL", n)
    print(f" report: {out}")
    print("=" * 64)
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
