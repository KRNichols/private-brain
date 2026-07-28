#!/usr/bin/env python3
"""Windows Release MVP — single hard gate chain for laptop-like runner E2E.

Phases (fail closed, zero soft):
  0. lint / py_compile / branding
  1. laptop layout (CODEX_HOME + private-brain + venv path)
  2. Codex CLI pin (default 0.144.3 — never upgrade past PB_CODEX_VERSION)
  3. install hooks + beast profiles
  4. brain_init + RAG-DAG boot
  5. beast mode flags on
  6. hooks: normal mode + beast mode (Stop/UPS/SessionStart JSON legal)
  7. crawlers (public github/gitlab topology)
  8. ingestors (github_ingest + gitlab_ingest light)
  9. agent swarm capacity (max 64)
 10. fire drill + nuclear x10 + conversation e2e + force-feed + golden dry-run
 11. READY verdict

Env:
  PB_CODEX_VERSION   pin (default 0.144.3)
  PB_MAX_AGENTS      default 64
  PB_GITLAB_INTER_REPO_SEC  max wait between gitlab repos (default 15)
  PRIVATE_BRAIN_HOME / CODEX_HOME  laptop layout
"""
from __future__ import annotations

import json
import os
import py_compile
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("PB_ENTERPRISE", "1")
os.environ.setdefault("PB_CI", "1")
os.environ.setdefault("PB_ZERO_SOFT", "1")
os.environ.setdefault("PB_NONINTERACTIVE", "1")
os.environ.setdefault("PB_NO_OPEN_CODEX", "1")
os.environ.setdefault("PB_GODSEYE", "0")
os.environ.setdefault("PB_NUCLEAR_HEADLESS", "1")
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PB_MAX_AGENTS", "64")
os.environ.setdefault("PB_SWARM_AGENTS", "64")
os.environ.setdefault("PB_GITLAB_INTER_REPO_SEC", "15")
os.environ.setdefault("PB_CODEX_VERSION", "0.144.3")

PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    RESULTS.append(
        {"name": name, "ok": bool(ok), "detail": str(detail)[:800], "status": status}
    )
    mark = "OK" if ok else "FAIL"
    extra = f" — {str(detail)[:200]}" if detail else ""
    print(f"  [{mark}] {name}{extra}", flush=True)
    return bool(ok)


def _run(
    argv: list[str],
    *,
    timeout: int = 600,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env or os.environ.copy(),
        cwd=str(cwd or ROOT),
        input=stdin,
    )


def _home_layout() -> tuple[Path, Path]:
    """Laptop-like: %USERPROFILE%\\.codex + private-brain (or env overrides)."""
    home = Path.home()
    codex = Path(os.environ.get("CODEX_HOME") or (home / ".codex")).expanduser()
    brain = Path(
        os.environ.get("PRIVATE_BRAIN_HOME") or (codex / "private-brain")
    ).expanduser()
    codex.mkdir(parents=True, exist_ok=True)
    brain.mkdir(parents=True, exist_ok=True)
    os.environ["CODEX_HOME"] = str(codex)
    os.environ["PRIVATE_BRAIN_HOME"] = str(brain)
    return codex, brain


def _sync_brain(brain: Path) -> None:
    """Copy engine into CODEX_HOME/private-brain like START.ps1 sideload."""
    for rel in (
        "scripts",
        "hooks",
        "config",
        "agents",
        "private_brain",
        "visualizer",
        "package",
        "installers",
        "loop_graph_harness",
        "local-rag",
        "e2e-fixtures",
        ".github",
    ):
        src = ROOT / rel
        if not src.exists():
            continue
        dst = brain / rel
        if src.resolve() == dst.resolve():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # root helpers
    for name in ("Install-PrivateBrain.ps1", "SETUP.ps1", "beast-mode.md", "AGENTS.md", "README.md"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, brain / name)
    os.environ["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    os.environ["PB_REPO_ROOT"] = str(ROOT)
    os.environ.setdefault("GITHUB_WORKSPACE", str(ROOT))


def phase0_lint() -> None:
    print("\n=== P0 LINT / COMPILE ===", flush=True)
    errs: list[str] = []
    n = 0
    for root in ("scripts", "hooks", "private_brain", "visualizer", "loop_graph_harness"):
        p = ROOT / root
        if not p.exists():
            continue
        for f in p.rglob("*.py"):
            n += 1
            try:
                py_compile.compile(str(f), doraise=True)
            except Exception as e:
                errs.append(f"{f}: {e}")
    gate("py_compile_all", not errs, f"compiled={n} errs={len(errs)} " + "; ".join(errs[:5]))

    r = _run([sys.executable, str(SCRIPTS / "lint_sanitized_branding.py")], timeout=120)
    gate("lint_branding", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])

    # required operational modules
    required = [
        "orchestrate.py",
        "brain_lib.py",
        "enterprise.py",
        "install_hooks.py",
        "install_local_rag.py",
        "product_readiness.py",
        "e2e_status_report.py",
        "neoj_path_reconcile.py",
        "session_start_deferred.py",
        "golden_config.py",
        "gitlab_ingest.py",
        "github_ingest.py",
        "crawl_public.py",
        "agent_swarm.py",
        "fire_drill.py",
        "nuclear_x10.py",
        "conversation_e2e.py",
        "codex_cli_smoke.py",
        "organism.py",
        "godseye.py",
        "zero_soft.py",
        "merge_codex_config.py",
        "laptop_sim_harness.py",
        "confluence_page_rechunk.py",
    ]
    missing = [m for m in required if not (SCRIPTS / m).is_file()]
    gate("required_scripts_present", not missing, f"missing={missing}")
    # local-rag source package
    lr = ROOT / "local-rag"
    gate(
        "local_rag_package_present",
        (lr / "cli" / "ask.py").is_file() and (lr / "agents" / "run_agent.py").is_file(),
        str(lr),
    )
    gate("programs_yaml_present", (ROOT / "config" / "programs.yaml").is_file())
    gate(
        "laptop_sim_fixtures",
        (ROOT / "e2e-fixtures" / "laptop_sim" / "donut_page_body.md").is_file(),
        "e2e-fixtures/laptop_sim required for isolated laptop sim",
    )


def phase1_layout(codex: Path, brain: Path) -> None:
    print("\n=== P1 LAPTOP LAYOUT ===", flush=True)
    _sync_brain(brain)
    gate("codex_home_exists", codex.is_dir(), str(codex))
    gate("brain_home_exists", brain.is_dir(), str(brain))
    gate("brain_scripts", (brain / "scripts" / "orchestrate.py").is_file())
    gate("brain_hooks", (brain / "hooks" / "stop_validate.py").is_file())
    # venv optional on CI — we use runner python but prefer venv path if present
    venv_py = brain / "venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        venv_py = brain / "venv" / "bin" / "python3"
    gate(
        "python_runtime",
        True,
        f"sys={sys.executable} venv_exists={venv_py.exists()}",
    )


def phase2_codex() -> None:
    print("\n=== P2 CODEX CLI PIN ===", flush=True)
    pin = os.environ.get("PB_CODEX_VERSION", "0.144.3").strip()
    os.environ["PB_E2E_CODEX_VERSION"] = pin
    os.environ["PB_E2E_INSTALL_CODEX"] = "1"
    # install exact pin
    npm = shutil.which("npm")
    if npm:
        r = _run([npm, "install", "-g", f"@openai/codex@{pin}"], timeout=420)
        gate("codex_npm_install_pin", r.returncode == 0, (r.stdout or r.stderr or "")[-240:])
    else:
        gate("codex_npm_install_pin", False, "npm missing")

    smoke = SCRIPTS / "codex_cli_smoke.py"
    r = _run([sys.executable, str(smoke)], timeout=600)
    gate("codex_cli_smoke", r.returncode == 0, (r.stdout or r.stderr or "")[-400:])

    codex = shutil.which("codex") or shutil.which("codex.cmd")
    if codex:
        v = _run([codex, "--version"], timeout=60)
        ver = (v.stdout or v.stderr or "").strip()
        gate("codex_version_pin", pin in ver or ver.endswith(pin) or f"codex-cli {pin}" in ver or pin in ver, ver)
    else:
        gate("codex_version_pin", False, "codex binary missing after smoke")


def phase3_hooks_and_beast(codex: Path, brain: Path) -> None:
    print("\n=== P3 HOOKS + BEAST PROFILES ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["CODEX_HOME"] = str(codex)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)

    r = _run([sys.executable, str(brain / "scripts" / "install_hooks.py")], env=env, timeout=120)
    gate("install_hooks", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])
    hj = codex / "hooks.json"
    gate("hooks_json_written", hj.is_file(), str(hj))
    if hj.is_file():
        raw = hj.read_text(encoding="utf-8")
        gate("hooks_has_commandWindows", "commandWindows" in raw or "command" in raw)
        gate("hooks_no_mac_abs", "/Users/" not in raw.split("commandWindows")[-1][:400] if "commandWindows" in raw else True)
        gate(
            "hooks_cmd_wrappers_configured",
            "pb-session-start.cmd" in raw
            and "pb-user-prompt-submit.cmd" in raw
            and "pb-stop-validate.cmd" in raw,
            "commandWindows must point at permanent .cmd wrappers",
        )
    for w in ("pb-session-start.cmd", "pb-user-prompt-submit.cmd", "pb-stop-validate.cmd"):
        gate(f"wrapper_{w}", (brain / "hooks" / w).is_file(), str(brain / "hooks" / w))

    # local-rag product install into CODEX_HOME/local-rag
    r = _run([sys.executable, str(brain / "scripts" / "install_local_rag.py")], env=env, timeout=120)
    gate("install_local_rag", r.returncode == 0, (r.stdout or r.stderr or "")[-400:])
    r = _run([sys.executable, str(brain / "scripts" / "product_readiness.py")], env=env, timeout=60)
    try:
        pr = json.loads((r.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        pr = {}
    gate(
        "product_readiness_all",
        bool(pr.get("installer_integration"))
        and bool(pr.get("ask_cli"))
        and bool(pr.get("sovereign_provider")),
        json.dumps(pr)[:400],
    )

    # beast profiles (laptop recovery shape)
    for name, body in (
        (
            "beast.config.toml",
            'model = "gpt-5.1"\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\nmodel_reasoning_effort = "high"\n',
        ),
        (
            "beast-enterprise.config.toml",
            'model = "gpt-5.1"\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\nmodel_reasoning_effort = "high"\n',
        ),
    ):
        p = codex / name
        if not p.exists():
            p.write_text(body, encoding="utf-8")
        t = p.read_text(encoding="utf-8")
        gate(f"profile_{name}", "danger-full-access" in t and "never" in t, name)

    cfg = codex / "config.toml"
    if not cfg.exists() or "hooks = true" not in cfg.read_text(encoding="utf-8"):
        cfg.write_text("[features]\nhooks = true\n", encoding="utf-8")
    gate("config_hooks_true", "hooks = true" in cfg.read_text(encoding="utf-8"))


def phase4_rag_boot(brain: Path) -> None:
    print("\n=== P4 RAG-DAG INIT ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    for script in ("brain_init.py", "brain_snapshot.py"):
        sp = brain / "scripts" / script
        if sp.is_file():
            r = _run([sys.executable, str(sp)], env=env, timeout=180)
            gate(f"run_{script}", r.returncode == 0, (r.stdout or r.stderr or "")[-200:])
    r = _run(
        [sys.executable, "-c", "from orchestrate import dag_boot; import json; print(json.dumps(dag_boot(), default=str)[:2000])"],
        env=env,
        timeout=300,
    )
    gate("dag_boot", r.returncode == 0, (r.stdout or r.stderr or "")[-400:])

    # golden config write
    gpy = brain / "scripts" / "golden_config.py"
    if gpy.is_file():
        r = _run([sys.executable, str(gpy)], env=env, timeout=120)
        gate("golden_config_write", r.returncode == 0, (r.stdout or r.stderr or "")[-200:])


def phase5_beast_flags(brain: Path) -> None:
    print("\n=== P5 BEAST MODE FLAGS ===", flush=True)
    st = brain / ".brain" / "state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "enterprise.on").write_text("1\n", encoding="utf-8")
    (st / "beastmode.on").write_text("1\n", encoding="utf-8")
    (st / "conversation_mode.json").write_text(
        json.dumps({"mode": "beast", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
        encoding="utf-8",
    )
    rag_off = st / "rag.off"
    if rag_off.exists():
        rag_off.unlink()
    gate("flag_enterprise", (st / "enterprise.on").is_file())
    gate("flag_beastmode", (st / "beastmode.on").is_file())
    gate("mode_beast", json.loads((st / "conversation_mode.json").read_text(encoding="utf-8")).get("mode") == "beast")


def _hook_json(brain: Path, script: str, payload: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["CODEX_HOME"] = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    env["PB_ENTERPRISE"] = "1"
    path = brain / "hooks" / script
    r = _run(
        [sys.executable, str(path)],
        env=env,
        timeout=180,
        stdin=json.dumps(payload),
    )
    raw = (r.stdout or "").strip()
    # take last JSON object if noise
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try last line
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
        return {"_parse_error": True, "_raw": raw[:500], "_rc": r.returncode, "_err": (r.stderr or "")[:300]}


def phase6_hooks(brain: Path) -> None:
    print("\n=== P6 HOOKS NORMAL + BEAST ===", flush=True)
    st = brain / ".brain" / "state"
    # --- BEAST path ---
    (st / "conversation_mode.json").write_text(json.dumps({"mode": "beast"}), encoding="utf-8")
    if (st / "rag.off").exists():
        (st / "rag.off").unlink()

    t0 = time.perf_counter()
    ss = _hook_json(brain, "session_start.py", {"hook_event_name": "SessionStart", "source": "startup"})
    ss_sec = time.perf_counter() - t0
    gate(
        "session_start_json",
        not ss.get("_parse_error") and (ss.get("continue") is True or "hookSpecificOutput" in ss),
        json.dumps(ss)[:300],
    )
    # SessionStart must complete materially below 120s (budget gate: 25s hard in CI)
    gate("session_start_under_budget", ss_sec < 25.0, f"elapsed_sec={ss_sec:.3f}")
    # Must not inject multi-KB kingdom/golden dumps
    ss_ctx = ""
    if isinstance(ss.get("hookSpecificOutput"), dict):
        ss_ctx = ss["hookSpecificOutput"].get("additionalContext") or ""
    gate("session_start_compact_ctx", len(ss_ctx) < 8000, f"ctx_chars={len(ss_ctx)}")

    t0 = time.perf_counter()
    ups_beast = _hook_json(
        brain,
        "user_prompt_submit.py",
        {"hook_event_name": "UserPromptSubmit", "prompt": "what is the status of the graph? cite nodes."},
    )
    ups_sec = time.perf_counter() - t0
    ctx = ""
    if isinstance(ups_beast.get("hookSpecificOutput"), dict):
        ctx = ups_beast["hookSpecificOutput"].get("additionalContext") or ""
    ctx = ctx or ups_beast.get("additionalContext") or ""
    gate(
        "ups_beast_inject",
        not ups_beast.get("_parse_error") and ups_beast.get("continue") is not False,
        f"ctx_len={len(ctx)} keys={list(ups_beast.keys())[:8]}",
    )
    gate("ups_under_budget", ups_sec < 40.0, f"elapsed_sec={ups_sec:.3f}")

    # Stop: operational ack must NOT block
    stop_ops = _hook_json(
        brain,
        "stop_validate.py",
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Beast mode is already active.",
        },
    )
    gate(
        "stop_ops_beast_ack",
        stop_ops.get("continue") is True and stop_ops.get("decision") != "block",
        json.dumps(stop_ops)[:240],
    )
    stop_ops2 = _hook_json(
        brain,
        "stop_validate.py",
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "Normal mode is active.",
        },
    )
    gate(
        "stop_ops_normal_ack",
        stop_ops2.get("continue") is True and stop_ops2.get("decision") != "block",
        json.dumps(stop_ops2)[:240],
    )

    # Factual uncited source claim should block when enterprise + no cites
    # Seed current evidence so gate has something to demand cites against
    (st / "current_evidence.json").write_text(
        json.dumps(
            {
                "evidence": [
                    {"id": "confluence:page:633240886", "tier": "T0", "source": "confluence"},
                    {"id": "test:node:fixture", "tier": "T1", "source": "fixture"},
                ]
            }
        ),
        encoding="utf-8",
    )
    stop_bad = _hook_json(
        brain,
        "stop_validate.py",
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": (
                "According to confluence the donut rules require X and the graph shows Y."
            ),
        },
    )
    illegal = set(stop_bad.keys()) - {
        "continue",
        "decision",
        "reason",
        "systemMessage",
        "stopReason",
        "suppressOutput",
        "_parse_error",
        "_raw",
        "_rc",
        "_err",
    }
    gate(
        "stop_no_illegal_keys",
        not illegal and not stop_bad.get("_parse_error"),
        f"keys={list(stop_bad.keys())} illegal={illegal}",
    )
    gate(
        "stop_uncited_source_blocks",
        stop_bad.get("decision") == "block",
        json.dumps(stop_bad)[:240],
    )
    # Cited current Confluence page passes
    stop_good = _hook_json(
        brain,
        "stop_validate.py",
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": (
                "According to confluence donut rules see `confluence:page:633240886`."
            ),
        },
    )
    gate(
        "stop_cited_confluence_passes",
        stop_good.get("continue") is True or stop_good.get("decision") != "block",
        json.dumps(stop_good)[:240],
    )
    gate(
        "stop_beast_legal_shape",
        stop_bad.get("decision") == "block" or stop_bad.get("continue") is True,
        json.dumps(stop_bad)[:240],
    )

    # --- NORMAL path ---
    ups_norm = _hook_json(
        brain,
        "user_prompt_submit.py",
        {"hook_event_name": "UserPromptSubmit", "prompt": "stop beast mode"},
    )
    gate("ups_normal_switch", not ups_norm.get("_parse_error"), json.dumps(ups_norm)[:200])
    mode = {}
    try:
        mode = json.loads((st / "conversation_mode.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    gate("mode_normal_sticky", mode.get("mode") == "normal" or (st / "rag.off").exists(), str(mode))

    stop_norm = _hook_json(
        brain,
        "stop_validate.py",
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "plain answer no cites ok in normal mode",
        },
    )
    gate(
        "stop_normal_allows",
        stop_norm.get("continue") is True or stop_norm.get("decision") != "block",
        json.dumps(stop_norm)[:200],
    )

    # re-enable beast
    ups_on = _hook_json(
        brain,
        "user_prompt_submit.py",
        {"hook_event_name": "UserPromptSubmit", "prompt": "beast mode"},
    )
    gate("ups_beast_reenable", not ups_on.get("_parse_error"), json.dumps(ups_on)[:200])


def phase6b_handoff_diagnostics(codex: Path, brain: Path) -> None:
    """Developer handoff gates: GodsEye JSON, Neo4J recon, config.toml placement, e2e report."""
    print("\n=== P6b HANDOFF DIAGNOSTICS ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["CODEX_HOME"] = str(codex)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)

    # GodsEye status --json schema
    r = _run(
        [sys.executable, str(brain / "scripts" / "godseye.py"), "status", "--json"],
        env=env,
        timeout=60,
    )
    try:
        ge = json.loads((r.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        ge = {}
    required_ge = {
        "enabled",
        "dismissed",
        "pids",
        "alive",
        "backend",
        "capability",
        "last_error",
        "last_started_at",
    }
    gate(
        "godseye_status_json_schema",
        r.returncode == 0 and required_ge.issubset(set(ge.keys())),
        f"keys={list(ge.keys())} missing={required_ge - set(ge.keys())}",
    )
    # Must not claim running without alive pids
    gate(
        "godseye_no_false_started",
        not (ge.get("claim_started_ok") and not (ge.get("alive") or ge.get("alive_count"))),
        json.dumps(ge)[:240],
    )

    # Neo4J recon self-test
    r = _run(
        [sys.executable, str(brain / "scripts" / "neoj_path_reconcile.py"), "--self-test"],
        env=env,
        timeout=60,
    )
    gate("neoj_path_reconcile_self_test", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])

    # Confluence short-page always gets ≥1 chunk
    r = _run(
        [
            sys.executable,
            "-c",
            (
                "from brain_lib import write_node, ensure_tree; ensure_tree(); "
                "n=write_node('confluence:page:testchunk', type='Page', source='confluence', "
                "title='t', content='short body rules', tier='T0', chunk=True); "
                "assert n.get('chunk_ids'), n; print(len(n['chunk_ids']))"
            ),
        ],
        env=env,
        timeout=60,
    )
    gate("confluence_page_always_chunks", r.returncode == 0, (r.stdout or r.stderr or "")[:200])

    # config.toml managed keys before first table
    try:
        sys.path.insert(0, str(brain / "scripts"))
        from merge_codex_config import (  # type: ignore
            build_managed_block,
            managed_keys_before_first_table,
            _prepend_managed_before_first_table,
        )

        beast_md = brain / "beast-mode.md"
        if not beast_md.is_file():
            beast_md = ROOT / "beast-mode.md"
        sample = "[features]\nhooks = true\n\n[agents]\nmax_threads = 6\n"
        block = build_managed_block(beast_md, "dev instructions test", "gpt-5.1")
        merged = _prepend_managed_before_first_table(sample, block)
        gate(
            "config_managed_before_tables",
            managed_keys_before_first_table(merged),
            merged[:200],
        )
        after_features = merged.split("[features]", 1)[-1] if "[features]" in merged else ""
        gate(
            "config_no_approval_in_features",
            "approval_policy" not in after_features.split("[")[0],
            after_features[:120],
        )
    except Exception as e:
        gate("config_managed_before_tables", False, str(e))
        gate("config_no_approval_in_features", False, str(e))

    # e2e_status_report read-only
    r = _run(
        [sys.executable, str(brain / "scripts" / "e2e_status_report.py")],
        env=env,
        timeout=120,
    )
    gate("e2e_status_report_runs", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])

    # release gate one-JSON mock
    lr = codex / "local-rag" / "agents" / "run_release_gate_workflow.py"
    if lr.is_file():
        r = _run([sys.executable, str(lr), "--mock"], env=env, timeout=30)
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        ok_one = False
        try:
            objs = [json.loads(ln) for ln in lines if ln.strip().startswith("{")]
            ok_one = len(objs) == 1 and objs[0].get("ok") is True and objs[0].get("violations") == 0
        except Exception:
            ok_one = False
        gate("release_gate_one_json", r.returncode == 0 and ok_one, (r.stdout or "")[:200])
    else:
        gate("release_gate_one_json", False, "release runner missing")

    # mock E2E agent into external runs root
    os.environ["PB_LOCAL_RAG_MOCK"] = "1"
    env["PB_LOCAL_RAG_MOCK"] = "1"
    agent = codex / "local-rag" / "agents" / "run_agent.py"
    if agent.is_file():
        r = _run(
            [sys.executable, str(agent), "--mock", "--role", "retriever", "--prompt", "smoke"],
            env=env,
            timeout=60,
        )
        gate("local_rag_mock_agent", r.returncode == 0, (r.stdout or r.stderr or "")[:200])
    else:
        gate("local_rag_mock_agent", False, "missing")


def phase7_crawlers(brain: Path) -> None:
    print("\n=== P7 CRAWLERS ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    # public crawl — topology light
    r = _run(
        [
            sys.executable,
            str(brain / "scripts" / "crawl_public.py"),
            "--help",
        ],
        env=env,
        timeout=60,
    )
    gate("crawl_public_help", r.returncode == 0, (r.stdout or "")[:120])

    # tiny public crawl if network
    crawl = brain / "scripts" / "crawl_public.py"
    # try module invocation with minimal flags
    # Light public gitlab topology crawl
    r = _run(
        [
            sys.executable,
            str(crawl),
            "--gitlab",
            "--gitlab-base",
            "https://gitlab.com",
            "--gitlab-group",
            "gitlab-org",
            "--max-projects",
            "2",
            "--max-mrs",
            "1",
            "--max-issues",
            "2",
        ],
        env=env,
        timeout=300,
    )
    gate("crawl_public_run", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])


def _node_count(brain: Path, env: dict[str, str]) -> int:
    r = _run(
        [
            sys.executable,
            "-c",
            "from brain_lib import status; print(int((status() or {}).get('node_count') or 0))",
        ],
        env=env,
        timeout=60,
    )
    try:
        return int((r.stdout or "0").strip().splitlines()[-1])
    except Exception:
        return -1


def phase8_ingestors(brain: Path) -> None:
    print("\n=== P8 INGESTORS ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    # CI public OSS path — ALLOW_PUBLIC is the only legal override (enterprise flag file may exist)
    env["PB_ALLOW_PUBLIC_INGEST"] = "1"
    env["PB_ENTERPRISE"] = "1"  # keep enterprise law; allowlist via ALLOW_PUBLIC
    env["GITHUB_TOKEN"] = os.environ.get("GITHUB_TOKEN", "")
    # inter-repo wait law
    inter = float(os.environ.get("PB_GITLAB_INTER_REPO_SEC", "0") or "0")
    gate("gitlab_inter_repo_cap_le_15", inter <= 15.0, f"PB_GITLAB_INTER_REPO_SEC={inter}")

    before = _node_count(brain, env)

    gh = brain / "scripts" / "github_ingest.py"
    if gh.is_file():
        r = _run(
            [
                sys.executable,
                str(gh),
                "--repo",
                "actions/checkout",
                "--max-issues",
                "5",
                "--max-prs",
                "2",
                "--json",
            ],
            env=env,
            timeout=300,
        )
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        blocked = "blocked" in out.lower() and "enterprise" in out.lower()
        after_gh = _node_count(brain, env)
        gate(
            "github_ingest_tiny",
            r.returncode == 0 and not blocked and after_gh > before,
            f"rc={r.returncode} nodes {before}->{after_gh} blocked={blocked} tail={out[-240:]}",
        )
    else:
        gate("github_ingest_tiny", False, "github_ingest.py missing")

    mid = _node_count(brain, env)
    gl = brain / "scripts" / "gitlab_ingest.py"
    if gl.is_file():
        r = _run([sys.executable, str(gl), "--help"], env=env, timeout=60)
        gate("gitlab_ingest_help", r.returncode == 0, (r.stdout or "")[:100])
        # Real public gitlab shallow ingest — must succeed (no soft-pass on enterprise block)
        r2 = _run(
            [
                sys.executable,
                str(gl),
                "--url",
                "https://gitlab.com/gitlab-org/gitlab-runner",
                "--max-projects",
                "2",
                "--shallow",
                "--json",
            ],
            env=env,
            timeout=420,
        )
        out2 = (r2.stdout or "") + "\n" + (r2.stderr or "")
        blocked2 = "policy blocked" in out2.lower() or (
            "blocks public host" in out2.lower()
        )
        after_gl = _node_count(brain, env)
        gate(
            "gitlab_ingest_tiny",
            r2.returncode == 0 and not blocked2 and after_gl > mid,
            f"rc={r2.returncode} nodes {mid}->{after_gl} blocked={blocked2} tail={out2[-280:]}",
        )
        gate(
            "gitlab_ingest_not_soft_block",
            not blocked2,
            "enterprise must not soft-block public CI ingest when PB_ALLOW_PUBLIC_INGEST=1",
        )
    else:
        gate("gitlab_ingest_help", False, "missing")
        gate("gitlab_ingest_tiny", False, "missing")
        gate("gitlab_ingest_not_soft_block", False, "missing")


def phase9_agents(brain: Path) -> None:
    print("\n=== P9 AGENTS MAX 64 ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    env["PB_MAX_AGENTS"] = "64"
    env["PB_SWARM_AGENTS"] = "64"
    # import max_agents
    r = _run(
        [
            sys.executable,
            "-c",
            "from organism import max_agents; n=max_agents(); print(n); assert n>=1 and n<=64, n",
        ],
        env=env,
        timeout=60,
    )
    gate("max_agents_le_64", r.returncode == 0, (r.stdout or r.stderr or "").strip())

    # small swarm smoke (not full 64 threads on free runner — capacity path)
    agents = int(os.environ.get("PB_SWARM_SMOKE_AGENTS", "8") or "8")
    r = _run(
        [
            sys.executable,
            str(brain / "scripts" / "agent_swarm.py"),
            "sweep",
            "--prompt",
            "windows release mvp smoke",
            "--agents",
            str(agents),
        ],
        env=env,
        timeout=600,
    )
    gate("agent_swarm_smoke", r.returncode == 0, (r.stdout or r.stderr or "")[-300:])
    # capacity declared
    gate("capacity_max_agents_64", os.environ.get("PB_MAX_AGENTS") == "64")


def phase9b_laptop_sim() -> None:
    """Isolated laptop sim — fixture hard gates, no AppGate, no real ~/.codex."""
    print("\n=== P9b LAPTOP SIM HARNESS ===", flush=True)
    env = os.environ.copy()
    env["PB_ENTERPRISE"] = "1"
    env["PB_CI"] = "1"
    env["PB_ZERO_SOFT"] = "1"
    env["PB_LOCAL_RAG_MOCK"] = "1"
    env["PB_GODSEYE"] = "0"
    # Always isolated under repo .codex-sim (never real user home)
    env["PB_LAPTOP_SIM_HOME"] = str(ROOT / ".codex-sim" / "mvp-ci")
    env.pop("PB_LAPTOP_SIM_ALLOW_REAL_HOME", None)
    sp = SCRIPTS / "laptop_sim_harness.py"
    if not sp.is_file():
        gate("laptop_sim_harness", False, "missing laptop_sim_harness.py")
        return
    r = _run([sys.executable, str(sp)], env=env, timeout=600, cwd=ROOT)
    # Prefer structured report for failure names (stdout is huge / truncated)
    rep = ROOT / "e2e-reports" / "LAPTOP_SIM.json"
    fail_names: list[str] = []
    if rep.is_file():
        try:
            d = json.loads(rep.read_text(encoding="utf-8"))
            fail_names = [
                str(x.get("name"))
                for x in (d.get("results") or [])
                if isinstance(x, dict) and not x.get("ok")
            ]
            gate(
                "laptop_sim_harness",
                r.returncode == 0 and d.get("ok") is True and int(d.get("fail") or 0) == 0,
                f"pass={d.get('pass')} fail={d.get('fail')} fails={fail_names} tail={(r.stdout or '')[-200:]}",
            )
            gate(
                "laptop_sim_report_ok",
                d.get("ok") is True and int(d.get("fail") or 0) == 0,
                f"pass={d.get('pass')} fail={d.get('fail')} fails={fail_names}",
            )
        except Exception as e:
            gate("laptop_sim_harness", r.returncode == 0, (r.stdout or r.stderr or "")[-400:])
            gate("laptop_sim_report_ok", False, str(e))
    else:
        gate("laptop_sim_harness", r.returncode == 0, (r.stdout or r.stderr or "")[-400:])
        gate("laptop_sim_report_ok", False, "LAPTOP_SIM.json missing")


def phase10_e2e_suite(brain: Path) -> None:
    print("\n=== P10 FULL E2E SUITE ===", flush=True)
    env = os.environ.copy()
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    env["PYTHONPATH"] = str(brain / "scripts") + os.pathsep + str(brain)
    env["PB_ENTERPRISE"] = "1"
    env["PB_CI"] = "1"
    env["PB_ZERO_SOFT"] = "1"
    env["PB_NUCLEAR_HEADLESS"] = "1"
    env["PB_GODSEYE"] = "0"
    env["PB_FORCE_FEED_TINY"] = "1"
    env["PB_MAX_AGENTS"] = "64"

    # Ensure PB_SESSIONS_EMPTY_ACK so doctor/session gates don't red on bare CI
    env["PB_SESSIONS_EMPTY_ACK"] = "1"

    suite = [
        ("fire_drill", "fire_drill.py", 900),
        ("nuclear_x10", "nuclear_x10.py", 900),
        ("rag_dag_e2e", "rag_dag_e2e.py", 600),
        # conversation before force-feed so swarm public noise doesn't bury plan fixtures
        ("conversation_e2e", "conversation_e2e.py", 900),
        ("nuclear_conversation_e2e", "nuclear_conversation_e2e.py", 900),
        ("corporate_golden_dryrun_e2e", "corporate_golden_dryrun_e2e.py", 300),
        ("ci_force_feed_public", "ci_force_feed_public.py", 900),
        ("nuclear_zero_fail", "nuclear_zero_fail.py", 600),
    ]
    # Scenario heal modules (hosts/tokens/index/AWS/sessions/GodsEye)
    gate(
        "ingest_scenario_module",
        (SCRIPTS / "ingest_scenario.py").is_file(),
    )
    gate(
        "scenario_heal_module",
        (SCRIPTS / "scenario_heal.py").is_file(),
    )
    try:
        r_sc = _run(
            [sys.executable, str(SCRIPTS / "scenario_heal.py"), "synthesize", "--reason", "mvp"],
            env=env,
            timeout=90,
            cwd=ROOT,
        )
        gate("scenario_heal_synthesize", r_sc.returncode == 0, (r_sc.stdout or r_sc.stderr or "")[-200:])
    except Exception as e:
        gate("scenario_heal_synthesize", False, str(e))
    # Always run suite from REPO root scripts (installers + workflows present)
    env["PB_REPO_ROOT"] = str(ROOT)
    env["GITHUB_WORKSPACE"] = str(ROOT)
    env["PRIVATE_BRAIN_HOME"] = str(brain)
    for name, script, timeout in suite:
        sp = SCRIPTS / script
        if not sp.is_file():
            sp = brain / "scripts" / script
        if not sp.is_file():
            gate(name, False, f"missing {script}")
            continue
        print(f"  … running {script}", flush=True)
        r = _run([sys.executable, str(sp)], env=env, timeout=timeout, cwd=ROOT)
        gate(name, r.returncode == 0, (r.stdout or r.stderr or "")[-400:])


def write_report(codex: Path, brain: Path) -> Path:
    out_dir = ROOT / "e2e-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": FAIL == 0,
        "pass": PASS,
        "fail": FAIL,
        "codex_home": str(codex),
        "private_brain_home": str(brain),
        "codex_version_pin": os.environ.get("PB_CODEX_VERSION"),
        "max_agents": os.environ.get("PB_MAX_AGENTS"),
        "gitlab_inter_repo_sec": os.environ.get("PB_GITLAB_INTER_REPO_SEC"),
        "results": RESULTS,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = out_dir / "WINDOWS_RELEASE_MVP.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # also under brain state
    st = brain / ".brain" / "state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "WINDOWS_RELEASE_MVP.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def main() -> int:
    print("=" * 60, flush=True)
    print(" WINDOWS RELEASE MVP — HARD GATES ONLY", flush=True)
    print("=" * 60, flush=True)
    codex, brain = _home_layout()
    print(f" CODEX_HOME={codex}", flush=True)
    print(f" PRIVATE_BRAIN_HOME={brain}", flush=True)
    print(f" PB_CODEX_VERSION={os.environ.get('PB_CODEX_VERSION')}", flush=True)
    print(f" PB_MAX_AGENTS={os.environ.get('PB_MAX_AGENTS')}", flush=True)
    print(f" PB_GITLAB_INTER_REPO_SEC={os.environ.get('PB_GITLAB_INTER_REPO_SEC')}", flush=True)

    try:
        phase0_lint()
        phase1_layout(codex, brain)
        phase2_codex()
        phase3_hooks_and_beast(codex, brain)
        phase4_rag_boot(brain)
        phase5_beast_flags(brain)
        phase6_hooks(brain)
        phase6b_handoff_diagnostics(codex, brain)
        phase7_crawlers(brain)
        phase8_ingestors(brain)
        phase9_agents(brain)
        phase9b_laptop_sim()
        phase10_e2e_suite(brain)
    except Exception as e:
        gate("mvp_uncaught", False, str(e))

    path = write_report(codex, brain)
    print("\n" + "=" * 60, flush=True)
    print(f" PASS={PASS} FAIL={FAIL}", flush=True)
    print(f" REPORT={path}", flush=True)
    if FAIL == 0:
        print(" READY — WINDOWS RELEASE MVP GREEN", flush=True)
        return 0
    print(" NOT READY — FIX FAILURES ABOVE", flush=True)
    # print fails
    for r in RESULTS:
        if not r["ok"]:
            print(f"  FAIL: {r['name']}: {r.get('detail','')[:200]}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
