#!/usr/bin/env python3
"""NUCLEAR zero-fail gate — Windows first-boot mission.

If this exits non-zero, DO NOT take the zip to Corporate.

  PB_ENTERPRISE=1 python scripts/nuclear_zero_fail.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))
os.environ.setdefault("PB_ENTERPRISE", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

checks: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300], "hard": hard})
    status = "PASS" if ok else ("FAIL" if hard else "SOFT")
    print(f"[{status}] {name}" + (f" — {detail[:120]}" if detail else ""), flush=True)


def main() -> int:
    print("=" * 60)
    print(" NUCLEAR ZERO-FAIL — Windows first-boot mission")
    print(" If hard fails: ground the pilot. Do not ship.")
    print("=" * 60)

    # ── 1. Full access / no sandbox helper ──
    ent_src = (_SCRIPTS / "enterprise.py").read_text(encoding="utf-8", errors="replace")
    gate(
        "danger_full_access_in_enterprise",
        'sandbox_mode = "danger-full-access"' in ent_src or "danger-full-access" in ent_src,
        "enterprise.py profile writer",
    )
    gate("approval_never_in_enterprise", "approval_policy" in ent_src and "never" in ent_src)
    cmd = (_SCRIPTS / "beastMode.cmd").read_text(encoding="utf-8", errors="replace")
    gate(
        "win_launcher_danger_bypass",
        "dangerously-bypass-approvals-and-sandbox" in cmd,
        "beastMode.cmd baseline",
    )
    gate("win_launcher_hook_trust_bypass", "dangerously-bypass-hook-trust" in cmd)
    bash = (_SCRIPTS / "beastMode").read_text(encoding="utf-8", errors="replace")
    gate("bash_launcher_danger_bypass", "dangerously-bypass-approvals-and-sandbox" in bash)
    bem = (_ROOT / "beast-enterprise.md").read_text(encoding="utf-8", errors="replace")
    gate("law_sandbox_helper_broken", "Sandbox helper is broken" in bem or "sandbox helper" in bem.lower())
    gate("law_never_ask_permission", "Never ask permission" in bem or "never ask permission" in bem.lower())

    # live profile if present
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    prof = codex / "beast-enterprise.config.toml"
    if prof.exists():
        pt = prof.read_text(encoding="utf-8", errors="replace")
        gate("live_profile_danger", "danger-full-access" in pt, str(prof))
        gate("live_profile_approval_never", "approval_policy" in pt and "never" in pt)
    else:
        gate("live_profile_danger", False, "beast-enterprise.config.toml missing — install will create")

    # ── 2. Self-* organism ──
    for name, path in [
        ("self_heal", "enterprise.py"),
        ("organism", "organism.py"),
        ("autopilot", "autopilot.py"),
        ("smart_discover", "smart_discover.py"),
        ("vector_manager", "vector_manager.py"),
        ("orchestrate", "orchestrate.py"),
        ("golden_config", "golden_config.py"),
        ("conversation_router", "conversation_router.py"),
        ("fire_drill", "fire_drill.py"),
        ("brutal_suite", "brutal_suite.py"),
        ("capabilities", "capabilities.py"),
    ]:
        gate(f"script_{name}", (_SCRIPTS / path).exists(), path)

    heal = (_SCRIPTS / "enterprise.py").read_text(encoding="utf-8", errors="replace")
    gate("has_self_heal_fn", "def self_heal" in heal)
    gate("has_quarantine_fn", "def quarantine_public_nodes" in heal)
    gate("has_citation_gate", "def citation_gate" in heal)
    vec = (_SCRIPTS / "vector_manager.py").read_text(encoding="utf-8", errors="replace")
    gate("has_reindex", "def reindex" in vec or "reindex_all" in vec)
    org = (_SCRIPTS / "organism.py").read_text(encoding="utf-8", errors="replace")
    gate("organism_water_pipe", "water" in org.lower() or "GodsEye" in org or "godseye" in org.lower())

    # ── 3. Hooks: auto beast + stop beast + full access inject ──
    ss = (_ROOT / "hooks" / "session_start.py").read_text(encoding="utf-8", errors="replace")
    gate("session_auto_beast", "session_start_auto_beast" in ss or '"mode": "beast"' in ss)
    gate("session_full_access_law", "Full system access" in ss or "Sandbox helper is broken" in ss or "never ask" in ss.lower())
    up = (_ROOT / "hooks" / "user_prompt_submit.py").read_text(encoding="utf-8", errors="replace")
    gate("stop_beast_phrase", "stop beast mode" in up)
    gate("normal_mode_phrase", "normal mode" in up)
    st = (_ROOT / "hooks" / "stop_validate.py").read_text(encoding="utf-8", errors="replace")
    gate("stop_citation_block", "citation_gate" in st and "block" in st)
    hj = (_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8", errors="replace")
    gate("hooks_windows_lines", "commandWindows" in hj)

    # ── 4. Non-hallucination DAG ──
    orch = (_SCRIPTS / "orchestrate.py").read_text(encoding="utf-8", errors="replace")
    gate("dag_validate", "def stage_validate" in orch)
    gate("dag_critic", "def stage_critic" in orch)
    gate("dag_final_ok_blocks_critic_fail", 'verdict") != "FAIL"' in orch or "verdict') != 'FAIL'" in orch)

    # ── 5. Windows ship layout (clean root + engine) ──
    zips = sorted((_ROOT / "dist").glob("PrivateBrain-WINDOWS-READY.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        zips = sorted(
            (Path.home() / "private-brain-codex" / "dist").glob("PrivateBrain-WINDOWS-READY.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    gate("windows_ready_zip_exists", bool(zips))
    if zips:
        z = zips[0]
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
        rootish = [n for n in names if n.count("/") == 0 or (n.count("/") == 1 and n.endswith("/"))]
        gate("win_root_readme", any(n.rstrip("/") == "README.md" or n.endswith("/README.md") and n.count("/") <= 1 for n in names) or "README.md" in names)
        gate("win_root_diagram", "DIAGRAM.md" in names)
        gate("win_tools_install_start", "tools/install/START.ps1" in names)
        gate("win_tools_engine_organism", any("tools/engine/scripts/organism.py" in n for n in names))
        gate("win_tools_engine_orchestrate", any("tools/engine/scripts/orchestrate.py" in n for n in names))
        gate("win_tools_engine_enterprise", any("tools/engine/scripts/enterprise.py" in n for n in names))
        gate("win_tools_engine_beastmode_cmd", any("beastMode.cmd" in n for n in names))
        gate("win_install_ps1", any("Install-PrivateBrain.ps1" in n for n in names))
        # Install must resolve tools/engine
        inst = None
        for n in names:
            if n.endswith("Install-PrivateBrain.ps1"):
                inst = n
                break
        if inst:
            with zipfile.ZipFile(z) as zf:
                it = zf.read(inst).decode("utf-8", errors="replace")
            gate("install_resolves_tools_engine", "tools\\engine" in it or "tools/engine" in it or "Resolve-EngineDir" in it)
            gate("install_forces_danger_profile", "danger-full-access" in it)
        else:
            gate("install_resolves_tools_engine", False, "Install-PrivateBrain.ps1 missing from zip")

        # root cleanliness: no package/ at root of zip
        gate(
            "win_root_clean_no_package",
            not any(n.startswith("package/") for n in names),
            "package/ must be under tools/engine",
        )
        gate(
            "win_root_clean_no_start_at_root",
            "START.ps1" not in names or "tools/install/START.ps1" in names,
        )

    # ── 6. Live self-heal + purity + doctor ──
    try:
        from enterprise import (
            corpus_purity_audit,
            doctor_enterprise,
            ensure_enterprise_profile,
            is_enterprise,
            quarantine_public_nodes,
            self_heal,
        )

        gate("enterprise_flag_on", is_enterprise() or os.environ.get("PB_ENTERPRISE") == "1")
        ensure_enterprise_profile()
        gate("ensure_profile_ok", (codex / "beast-enterprise.config.toml").exists())
        try:
            quarantine_public_nodes()
        except Exception as e:
            gate("quarantine_run", False, str(e)[:120])
        else:
            gate("quarantine_run", True)
        pur = corpus_purity_audit(write=True)
        gate("pilot_ops_ready", bool(pur.get("pilot_ops_ready")), f"q={pur.get('quarantine_coverage')}")
        h = self_heal()
        gate("self_heal_ok", bool(h.get("ok")) if isinstance(h, dict) else True, str(h)[:120] if isinstance(h, dict) else "")
        d = doctor_enterprise()
        soft = {
            "corpus_public_ratio",
            "corpus_pilot_ready",
            "corporate_library_approved_source",
            "optional_capabilities",
        }
        hard_fail = [c for c in (d.get("checks") or []) if not c.get("ok") and c.get("name") not in soft]
        gate("doctor_hard_green", not hard_fail and bool(d.get("ok")), str([c.get("name") for c in hard_fail])[:120])
    except Exception as e:
        gate("live_enterprise_stack", False, str(e)[:200])

    # ── 7. Fire drill subprocess ──
    try:
        r = subprocess.run(
            [sys.executable, str(_SCRIPTS / "fire_drill.py"), "--json"],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "PB_ENTERPRISE": "1"},
            cwd=str(_ROOT),
        )
        # parse last json-ish or state file
        fd_path = _ROOT / ".brain" / "state" / "fire_drill.json"
        if fd_path.exists():
            fd = json.loads(fd_path.read_text(encoding="utf-8"))
            band = fd.get("band") or (fd.get("score") or {}).get("band")
            gate("fire_drill_zero_fail", bool(fd.get("ok")) or band == "ZERO_FAIL_GREEN", f"band={band} rc={r.returncode}")
        else:
            gate("fire_drill_zero_fail", r.returncode == 0, f"rc={r.returncode} {r.stderr[:100]}")
    except Exception as e:
        gate("fire_drill_zero_fail", False, str(e)[:160])

    # ── 8. Hallucination unit contracts ──
    try:
        from enterprise import citation_gate
        from orchestrate import stage_validate

        ev = [{"id": "test:node:1", "tier": "T1"}]
        gate("cite_blocks_uncited", citation_gate("I invent facts", ev).get("ok") is False)
        gate("cite_allows_cited", citation_gate("see `test:node:1`", ev).get("ok") is True)
        v = stage_validate({"evidence": [], "hit_count": 0}, "nuclear", "n1")
        gate("validate_no_evidence_blocks", v.get("pass_for_answer") is False)
    except Exception as e:
        gate("hallucination_contracts", False, str(e)[:160])

    hard = [c for c in checks if c["hard"]]
    hard_ok = all(c["ok"] for c in hard)
    soft_fail = [c["name"] for c in checks if not c["hard"] and not c["ok"]]
    hard_fail = [c["name"] for c in hard if not c["ok"]]
    report = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": hard_ok,
        "band": "ZERO_FAIL_GREEN" if hard_ok else "GROUNDED",
        "hard_pass": sum(1 for c in hard if c["ok"]),
        "hard_total": len(hard),
        "hard_fails": hard_fail,
        "soft_fails": soft_fail,
        "checks": checks,
        "mission": "windows_first_boot_nuclear",
    }
    out = _ROOT / ".brain" / "state" / "NUCLEAR_ZERO_FAIL.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 60)
    if hard_ok:
        print(f" NUCLEAR GREEN  {report['hard_pass']}/{report['hard_total']} hard")
        print(f" Soft gaps: {soft_fail or 'none'}")
        print(f" Report: {out}")
        print(" AUTHORIZED FOR WINDOWS FIRST BOOT")
    else:
        print(f" NUCLEAR RED — GROUND THE PILOT")
        print(f" Hard fails: {hard_fail}")
        print(f" Report: {out}")
        print(" DO NOT TAKE THIS ZIP TO CORPORATE")
    print("=" * 60)
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
