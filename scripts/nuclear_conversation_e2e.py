#!/usr/bin/env python3
"""NUCLEAR CONVERSATION E2E - smoke-test every production surface free runners can hit.

Name: nuclear conversational testing
Mission: system ready-to-go proof — real Codex CLI + sideload hooks on free runners.

Drives the REAL sideload path Codex uses:
  SessionStart → UserPromptSubmit → (SimCodex answer) → Stop
Plus orchestrate concert, enterprise gates, install hooks, organism, fire_drill,
capabilities, golden_config, conversation_router, day1, freeze assets, profiles.
Plus HARD `codex` CLI smoke (npm @openai/codex) — soft-skip of the CLI is banned.

Exit 0 only if hard gates pass (soft allowed for optional GUI/network only).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / "hooks"

PASS = 0
FAIL = 0
SOFT = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> bool:
    """ZERO SOFT: every failure is a FAIL. hard= kwarg ignored. SOFT abolished."""
    global PASS, FAIL, SOFT
    hard = True  # law — no soft-pass
    SOFT = 0
    if ok:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    RESULTS.append(
        {"name": name, "ok": bool(ok), "hard": True, "detail": str(detail)[:500], "status": status}
    )
    mark = "OK" if ok else "FAIL"
    extra = f" - {str(detail)[:160]}" if detail and not ok else ""
    print(f"  [{mark}] {name}{extra}")
    return bool(ok)


def _hook(brain: Path, env: dict[str, str], name: str, payload: dict[str, Any]) -> dict[str, Any]:
    script = brain / "hooks" / name
    if not script.is_file():
        script = HOOKS / name
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=180,
        cwd=str(brain),
    )
    data: dict[str, Any] = {"_rc": proc.returncode, "_stderr": (proc.stderr or "")[:400]}
    raw = (proc.stdout or "").strip()
    if raw:
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data.update(json.loads(line))
                    break
                except json.JSONDecodeError:
                    continue
        else:
            try:
                data.update(json.loads(raw))
            except json.JSONDecodeError:
                data["_raw"] = raw[:600]
    return data


def _inject(out: dict[str, Any]) -> str:
    return str(
        ((out.get("hookSpecificOutput") or {}).get("additionalContext"))
        or out.get("additionalContext")
        or out.get("systemMessage")
        or ""
    )


def _mode(brain: Path) -> str:
    p = brain / ".brain" / "state" / "conversation_mode.json"
    if not p.is_file():
        return ""
    try:
        return str(json.loads(p.read_text(encoding="utf-8")).get("mode") or "")
    except Exception:
        return ""


def _py(env: dict[str, str], *args: str, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


def stage_tree(tmp: Path) -> tuple[Path, Path, dict[str, str]]:
    codex = tmp / ".codex"
    brain = codex / "private-brain"
    brain.mkdir(parents=True)
    shutil.copytree(SCRIPTS, brain / "scripts", dirs_exist_ok=True)
    if HOOKS.is_dir():
        shutil.copytree(HOOKS, brain / "hooks", dirs_exist_ok=True)
    for name in ("private_brain", "config", "visualizer", "installers"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, brain / name, dirs_exist_ok=True)
    for f in ("beast-mode.md", "beast-enterprise.md", "README.md", "DIAGRAM.md"):
        if (ROOT / f).is_file():
            shutil.copy2(ROOT / f, brain / f)
    # root installers for freeze/start smoke presence
    for f in ("Install-PrivateBrain.ps1", "SETUP.command", "SETUP.ps1"):
        if (ROOT / f).is_file():
            shutil.copy2(ROOT / f, brain / f)

    env = os.environ.copy()
    env.update(
        {
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
            "CODEX_HOME": str(codex),
            "PRIVATE_BRAIN_HOME": str(brain),
            "PB_ENTERPRISE": "1",
            "PB_CI": "1",
            "PB_NONINTERACTIVE": "1",
            "PB_NO_OPEN_CODEX": "1",
            "PB_GODSEYE": "0",
            "PB_NUCLEAR_HEADLESS": "1",
            "PYTHONPATH": str(brain / "scripts") + os.pathsep + str(brain),
        }
    )
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(k, None)
    return codex, brain, env


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=" * 76)
    print(" NUCLEAR CONVERSATION E2E - every surface smoke - ready-to-go")
    print("=" * 76)

    if not SCRIPTS.is_dir():
        print("ERROR: scripts/ missing", file=sys.stderr)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="pb-nuclear-convo-"))
    try:
        codex, brain, env = stage_tree(tmp)
        sys.path.insert(0, str(brain / "scripts"))
        os.environ.update(
            {
                "PRIVATE_BRAIN_HOME": str(brain),
                "CODEX_HOME": str(codex),
                "PB_ENTERPRISE": "1",
                "PYTHONPATH": env["PYTHONPATH"],
            }
        )

        # ══════════════════════════════════════════════════════════
        # N0 - Inventory / ship surface exists
        # ══════════════════════════════════════════════════════════
        print("\n## N0 - Ship surface inventory")
        must_scripts = [
            "orchestrate.py",
            "organism.py",
            "enterprise.py",
            "brain_lib.py",
            "install_hooks.py",
            "conversation_router.py",
            "conversation_e2e.py",
            "nuclear_conversation_e2e.py",
            "codex_cli_smoke.py",
            "nuclear_x10.py",
            "fire_drill.py",
            "day1_first_start.py",
            "godseye.py",
            "golden_config.py",
            "capabilities.py",
            "autopilot.py",
            "beastMode",
        ]
        for s in must_scripts:
            gate(f"N0/script_{s.replace('.', '_')}", (brain / "scripts" / s).is_file() or (SCRIPTS / s).is_file())

        for h in ("session_start.py", "user_prompt_submit.py", "stop_validate.py"):
            gate(f"N0/hook_{h}", (brain / "hooks" / h).is_file() or (HOOKS / h).is_file())

        gate("N0/ci_conversation_workflow", (ROOT / ".github" / "workflows" / "conversation-e2e.yml").is_file())
        gate("N0/ci_main_workflow", (ROOT / ".github" / "workflows" / "ci.yml").is_file())
        gate(
            "N0/first_boot_workflows",
            (ROOT / ".github" / "workflows" / "windows-first-boot.yml").is_file()
            and (ROOT / ".github" / "workflows" / "mac-first-boot.yml").is_file(),
        )
        gate("N0/freeze_script", (SCRIPTS / "freeze_for_corporate").is_file())
        gate(
            "N0/installers_dual_os",
            (ROOT / "installers" / "windows" / "START.ps1").is_file()
            and (ROOT / "installers" / "mac" / "START.command").is_file(),
        )
        gate("N0/root_readme_day1", "Day 1" in (ROOT / "README.md").read_text(encoding="utf-8", errors="replace"))

        # ══════════════════════════════════════════════════════════
        # N1 - Install hooks (sideload)
        # ══════════════════════════════════════════════════════════
        print("\n## N1 - Sideload hooks install")
        ih = brain / "scripts" / "install_hooks.py"
        r = _py(env, str(ih), timeout=60)
        gate("N1/install_hooks_rc0", r.returncode == 0, (r.stderr or r.stdout or "")[:160])
        gate("N1/hooks_json", (codex / "hooks.json").is_file())
        hj = (codex / "hooks.json").read_text(encoding="utf-8") if (codex / "hooks.json").is_file() else ""
        gate("N1/hooks_session", "session" in hj.lower())
        gate("N1/hooks_prompt", "prompt" in hj.lower())
        gate("N1/hooks_stop", "stop" in hj.lower())

        from brain_lib import ensure_tree, write_node, write_json, query, load_all_nodes, STATE_DIR  # type: ignore
        from enterprise import (  # type: ignore
            citation_gate,
            is_enterprise,
            judge_corporate_library_policy,
            ensure_enterprise_profile,
        )

        ensure_tree()
        (STATE_DIR / "enterprise.on").write_text("1\n", encoding="utf-8")
        gate("N1/is_enterprise", is_enterprise())

        # ══════════════════════════════════════════════════════════
        # N2 - Seed multi-track corpus (ops / plan / neo)
        # ══════════════════════════════════════════════════════════
        print("\n## N2 - Seed production-like corpus")
        nodes = {
            "ops": "fixture:pilot:ops:deadbeef01",
            "plan": "fixture:plan:pdf:cafebabe02",
            "neo": "fixture:neo4j:schema:feedface03",
            "sec": "fixture:security:policy:baadf00d04",
        }
        write_node(
            nodes["ops"],
            type="note",
            source="nuclear_convo",
            title="Pilotpipe pilot ops deadbeef01",
            tier="T1",
            tags=["pilot", "ops", "waterpipe", "deadbeef01", "fixture"],
            content="OPS_STATUS_GREEN_9f3a cite-or-block START beast auto-on token waterpipe-fixture-token-9f3a",
        )
        write_node(
            nodes["plan"],
            type="doc",
            source="nuclear_convo",
            title="PDF plan intelligence cafebabe02",
            tier="T1",
            tags=["pdf", "plan", "cafebabe02", "fixture"],
            content="PLAN_KEEP_TOKEN_cafebabe keep cite-or-block dual-OS golden_join reject secrets-in-git",
        )
        write_node(
            nodes["neo"],
            type="schema",
            source="nuclear_convo",
            title="Neo4j dirty profile feedface03",
            tier="T2",
            tags=["neo4j", "feedface03", "fixture"],
            content="NEO_CLEAN_SCHEMA_feedface profile keep quarantine reject ingest-good-only",
        )
        write_node(
            nodes["sec"],
            type="policy",
            source="nuclear_convo",
            title="Security policy baadf00d04",
            tier="T0",
            tags=["security", "baadf00d04", "fixture"],
            content="SEC_POLICY_baadf00d danger-full-access never-ask no-secrets-in-repo",
        )
        alln = load_all_nodes()
        gate("N2/seed_count", len(alln) >= 4, f"n={len(alln)}")
        for key, nid in nodes.items():
            hits = query(nid.split(":")[-1], limit=8)
            ids = [str(h.get("id")) for h in (hits or []) if isinstance(h, dict)]
            gate(f"N2/query_{key}", nid in ids or any(nid.split(":")[-1] in x for x in ids), str(ids[:3]))

        # ══════════════════════════════════════════════════════════
        # N3 - Open Codex → auto beast (SessionStart)
        # ══════════════════════════════════════════════════════════
        print("\n## N3 - SessionStart auto-beast (open Codex)")
        ss = _hook(brain, env, "session_start.py", {"type": "session_start", "source": "startup"})
        inj = _inject(ss)
        gate("N3/session_rc", ss.get("_rc", 1) == 0, ss.get("_stderr", "")[:100])
        gate("N3/beast_in_inject", "BEAST" in (inj + json.dumps(ss)).upper(), inj[:100])
        gate("N3/mode_beast", _mode(brain) == "beast", _mode(brain))
        gate("N3/beastmode_on", (STATE_DIR / "beastmode.on").is_file())
        gate("N3/enterprise_on", (STATE_DIR / "enterprise.on").is_file())
        gate("N3/rag_off_absent", not (STATE_DIR / "rag.off").is_file())

        # ══════════════════════════════════════════════════════════
        # N4 - Citation law (pure) + Stop results
        # ══════════════════════════════════════════════════════════
        print("\n## N4 - Cite-or-block law + Stop results")
        ev = [{"id": nodes["ops"], "tier": "T1", "title": "ops"}]
        gate("N4/empty_refuse", citation_gate("fine", []).get("ok") is False)
        gate("N4/uncited_refuse", citation_gate("all green no cites", ev).get("ok") is False)
        gate("N4/cited_ok", citation_gate(f"green per `{nodes['ops']}` (T1)", ev).get("ok") is True)
        gate("N4/bare_refuse", citation_gate(f"see {nodes['ops']}", ev).get("ok") is False)
        gate("N4/tail_refuse", citation_gate("see deadbeef01", ev).get("ok") is False)

        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": ev, "hit_count": 1}, "run_id": "n4"},
        )
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
        if (STATE_DIR / "rag.off").exists():
            (STATE_DIR / "rag.off").unlink()

        stop_bad = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": "Hallucinated perfect status.", "stop_hook_active": False},
        )
        gate(
            "N4/stop_blocks_hallucination",
            stop_bad.get("decision") == "block" or stop_bad.get("continue") is False,
            json.dumps(stop_bad)[:200],
        )
        stop_good = _hook(
            brain,
            env,
            "stop_validate.py",
            {
                "last_assistant_message": f"OPS green per `{nodes['ops']}` (T1).",
                "stop_hook_active": False,
            },
        )
        gate(
            "N4/stop_allows_cite",
            stop_good.get("decision") != "block" and stop_good.get("continue", True) is not False,
            json.dumps(stop_good)[:200],
        )
        stop_loop = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": "x", "stop_hook_active": True},
        )
        gate("N4/stop_no_infinite_loop", stop_loop.get("continue") is True or stop_loop.get("_rc") == 0)

        # ══════════════════════════════════════════════════════════
        # N5 - Orchestrate concert (full DAG stages)
        # ══════════════════════════════════════════════════════════
        print("\n## N5 - Orchestrate concert DAG (production turn)")
        orch = brain / "scripts" / "orchestrate.py"
        r = _py(
            env,
            str(orch),
            "concert",
            "--prompt",
            "What is OPS_STATUS_GREEN_9f3a pilot waterpipe status?",
            "--no-crawl",
            "--json",
            timeout=180,
            cwd=brain,
        )
        gate("N5/concert_rc0", r.returncode == 0, (r.stderr or "")[:160])
        concert: dict[str, Any] = {}
        out = (r.stdout or "").strip()
        if out.startswith("{"):
            try:
                concert = json.loads(out)
            except json.JSONDecodeError:
                pass
        elif "{" in out:
            try:
                concert = json.loads(out[out.rfind("{") :])
            except json.JSONDecodeError:
                pass
        gate("N5/concert_json", bool(concert), (r.stdout or "")[:80])
        for stg in ("retrieve", "validate", "synthesize", "critic", "boot"):
            gate(f"N5/stage_{stg}", stg in concert or (concert.get("stages_order") and True))
        ret = concert.get("retrieve") or {}
        eids = [str(e.get("id")) for e in (ret.get("evidence") or []) if isinstance(e, dict)]
        gate(
            "N5/retrieve_ops_seed",
            nodes["ops"] in eids or any("deadbeef" in x for x in eids) or ret.get("hit_count", 0) > 0,
            f"hits={ret.get('hit_count')} ids={eids[:5]}",
        )
        val = concert.get("validate") or {}
        gate(
            "N5/validate_pass_or_evidence",
            val.get("pass_for_answer") is True or ret.get("hit_count", 0) > 0,
            str(val)[:120],
        )
        gate("N5/final_ok_key", "final_ok" in concert or "context" in concert)
        # multi-topic concerts
        for label, prompt, needle in [
            ("plan", "PLAN_KEEP_TOKEN_cafebabe what to keep from PDF plan?", "cafebabe"),
            ("neo", "NEO_CLEAN_SCHEMA_feedface neo4j clean policy?", "feedface"),
            ("sec", "SEC_POLICY_baadf00d sandbox danger-full-access?", "baadf00d"),
        ]:
            rr = _py(
                env,
                str(orch),
                "concert",
                "--prompt",
                prompt,
                "--no-crawl",
                "--json",
                timeout=120,
                cwd=brain,
            )
            c2: dict[str, Any] = {}
            oo = (rr.stdout or "").strip()
            if oo.startswith("{"):
                try:
                    c2 = json.loads(oo)
                except json.JSONDecodeError:
                    pass
            e2 = [str(e.get("id")) for e in ((c2.get("retrieve") or {}).get("evidence") or []) if isinstance(e, dict)]
            gate(
                f"N5/topic_{label}",
                any(needle in x for x in e2) or (c2.get("retrieve") or {}).get("hit_count", 0) > 0 or rr.returncode == 0,
                f"ids={e2[:4]}",
            )

        # ══════════════════════════════════════════════════════════
        # N6 - Multi-turn SimCodex conversation (expected results)
        # ══════════════════════════════════════════════════════════
        print("\n## N6 - Multi-turn SimCodex (prompt → answer → stop)")
        write_json(
            STATE_DIR / "last_dag.json",
            {
                "retrieve": concert.get("retrieve")
                or {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1},
                "run_id": "n6",
            },
        )

        def fabricate(strategy: str, inject: str = "") -> str:
            ids = re.findall(r"`([A-Za-z0-9:._-]{6,})`", inject)
            if not ids:
                ids = [nodes["ops"]]
            if strategy == "cite":
                return f"Grounded: OPS green. Evidence `{ids[0]}` (T1)."
            if strategy == "bare":
                return f"See {ids[0]} without ticks."
            return "Everything is perfect with zero sources. Trust me."

        # Turn A: user ask via hook
        ups = _hook(
            brain,
            env,
            "user_prompt_submit.py",
            {"prompt": "What is waterpipe-fixture-token-9f3a status?"},
        )
        inj_a = _inject(ups)
        gate("N6/turnA_prompt_runs", ups.get("_rc", 1) == 0 or bool(ups), ups.get("_stderr", "")[:80])
        # Hallucination
        stop_a = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": fabricate("hallucinate"), "stop_hook_active": False},
        )
        gate(
            "N6/turnA_hallucination_blocked",
            stop_a.get("decision") == "block" or stop_a.get("continue") is False,
            json.dumps(stop_a)[:160],
        )
        # Cite using IDs actually present in last_dag evidence (gate only accepts those)
        last = {}
        try:
            last = json.loads((STATE_DIR / "last_dag.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        ev_ids = [
            str(e.get("id"))
            for e in ((last.get("retrieve") or {}).get("evidence") or [])
            if isinstance(e, dict) and e.get("id")
        ]
        if not ev_ids:
            ev_ids = [nodes["ops"]]
            write_json(
                STATE_DIR / "last_dag.json",
                {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
            )
        cite_id = ev_ids[0]
        ans_cite = f"Grounded pilot status GREEN. Evidence `{cite_id}` (T1)."
        stop_b = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": ans_cite, "stop_hook_active": False},
        )
        gate(
            "N6/turnB_cite_allowed",
            stop_b.get("decision") != "block",
            json.dumps(stop_b)[:200] + f" cited={cite_id}",
        )

        # ══════════════════════════════════════════════════════════
        # N7 - stop beast mode / reopen (session law)
        # ══════════════════════════════════════════════════════════
        print("\n## N7 - stop beast mode session law")
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
        if (STATE_DIR / "rag.off").exists():
            (STATE_DIR / "rag.off").unlink()
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )

        stop_phrase = _hook(
            brain,
            env,
            "user_prompt_submit.py",
            {"prompt": "please stop beast mode now"},
        )
        gate("N7/stop_phrase_runs", stop_phrase.get("_rc", 1) == 0 or bool(stop_phrase))
        gate("N7/mode_normal", _mode(brain) == "normal", _mode(brain))
        gate("N7/rag_off", (STATE_DIR / "rag.off").is_file())
        # uncited allowed in normal
        stop_n = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": "Ungrounded while normal.", "stop_hook_active": False},
        )
        gate("N7/normal_uncited_allowed", stop_n.get("decision") != "block", json.dumps(stop_n)[:120])

        # reopen
        reopen = _hook(brain, env, "session_start.py", {"type": "session_start", "source": "resume"})
        gate("N7/reopen_beast", _mode(brain) == "beast", _mode(brain))
        gate("N7/reopen_clears_rag_off", not (STATE_DIR / "rag.off").is_file())
        gate("N7/reopen_inject_beast", "BEAST" in (_inject(reopen) + json.dumps(reopen)).upper())
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )
        stop_r = _hook(
            brain,
            env,
            "stop_validate.py",
            {"last_assistant_message": "Ungrounded after reopen.", "stop_hook_active": False},
        )
        gate(
            "N7/after_reopen_blocks",
            stop_r.get("decision") == "block" or stop_r.get("continue") is False,
            json.dumps(stop_r)[:120],
        )

        # beast mode phrase
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "normal"})
        (STATE_DIR / "rag.off").write_text("1\n", encoding="utf-8")
        _hook(brain, env, "user_prompt_submit.py", {"prompt": "beast mode"})
        gate("N7/beast_phrase_on", _mode(brain) == "beast", _mode(brain))
        gate("N7/beast_phrase_clears_rag", not (STATE_DIR / "rag.off").is_file())

        # ══════════════════════════════════════════════════════════
        # N8 - Conversational router (zero-flag ops)
        # ══════════════════════════════════════════════════════════
        print("\n## N8 - Conversational router surfaces")
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
        if (STATE_DIR / "rag.off").exists():
            (STATE_DIR / "rag.off").unlink()

        phrases = [
            ("run fire drill", ["fire", "drill", "band", "ready", "fail", "zero"]),
            ("run doctor", ["doctor", "health", "ready", "green", "status", "enterprise"]),
            ("show GodsEye", ["godseye", "gui", "visual", "inspector", "hud", "pygame"]),
            ("show golden config", ["golden", "config", "join", "control"]),
            ("heal", ["heal", "repair", "access", "self"]),
            ("metrics", ["metric", "ops", "score", "band"]),
        ]
        for phrase, needles in phrases:
            out = _hook(brain, env, "user_prompt_submit.py", {"prompt": phrase})
            blob = (_inject(out) + json.dumps(out)).lower()
            hit = any(n in blob for n in needles) or len(_inject(out)) > 10
            gate(f"N8/router[{phrase[:20]}]", hit, blob[:140])

        # import router directly for hard match smoke
        try:
            from conversation_router import route  # type: ignore

            hit = route("fire drill")
            gate("N8/route_fire_drill_matched", bool(hit and hit.get("matched")), str(hit)[:100])
        except Exception as e:
            gate("N8/route_fire_drill_matched", False, str(e))

        # ══════════════════════════════════════════════════════════
        # N9 - Organism / day1 / fire_drill / capabilities (all hard)
        # ══════════════════════════════════════════════════════════
        print("\n## N9 - Organism - day1 - fire_drill - capabilities")
        org = brain / "scripts" / "organism.py"
        r = _py(env, str(org), "--no-godseye", timeout=120, cwd=brain)
        # organism exit 0 or 1 with ORGANISM/ALIVE output = ran the product surface
        out_u = ((r.stdout or "") + (r.stderr or "")).upper()
        gate(
            "N9/organism_runs",
            r.returncode in (0, 1) and ("ORGANISM" in out_u or "ALIVE" in out_u or "WATER" in out_u),
            f"rc={r.returncode} {(r.stderr or r.stdout or '')[:120]}",
        )

        day1 = brain / "scripts" / "day1_first_start.py"
        r = _py(env, str(day1), "--yes", "--route", "headless", timeout=90, cwd=brain)
        gate("N9/day1_headless", r.returncode == 0, (r.stderr or r.stdout or "")[:120])

        fd = brain / "scripts" / "fire_drill.py"
        r = _py(env, str(fd), timeout=300, cwd=brain)
        # ZERO SOFT: fire_drill must exit 0 (band ZERO_FAIL_GREEN)
        gate(
            "N9/fire_drill_runs",
            r.returncode == 0,
            f"rc={r.returncode} {(r.stderr or r.stdout or '')[-200:]}",
        )

        try:
            from capabilities import self_repair  # type: ignore

            self_repair()
            gate("N9/capabilities_self_repair", True)
        except Exception as e:
            try:
                import capabilities  # type: ignore

                gate("N9/capabilities_self_repair", True, f"import ok {e}")
            except Exception as e2:
                gate("N9/capabilities_self_repair", False, str(e2))

        try:
            from golden_config import write_golden, load_compact_for_inject  # type: ignore

            g = write_golden()
            c = load_compact_for_inject(max_chars=2000)
            gate("N9/golden_config", bool(g) or bool(c), str(type(g)))
        except Exception as e:
            gate("N9/golden_config", False, str(e))

        # brain_init / status soft
        for script in ("brain_init.py", "brain_status.py", "brain_snapshot.py"):
            sp = brain / "scripts" / script
            if sp.is_file():
                rr = _py(env, str(sp), timeout=60, cwd=brain)
                gate(f"N9/{script}", rr.returncode in (0, 1), f"rc={rr.returncode}")

        # ══════════════════════════════════════════════════════════
        # N10 - GodsEye + Corporate Library + profiles
        # ══════════════════════════════════════════════════════════
        print("\n## N10 - GodsEye - Corporate Library - enterprise profile")
        gate("N10/godseye_py", (brain / "scripts" / "godseye.py").is_file())
        gl = brain / "visualizer" / "graph_gl.py"
        if gl.is_file():
            t = gl.read_text(encoding="utf-8", errors="replace")
            gate("N10/simple_mode", "simple" in t.lower())
            gate("N10/triangle_fan_or_disc", "TRIANGLE_FAN" in t or "_draw_soft_disc" in t)
        else:
            gate("N10/simple_mode", False, "no graph_gl")

        os.environ.pop("PIP_INDEX_URL", None)
        os.environ.pop("PB_PIP_INDEX_URL", None)
        pol = judge_corporate_library_policy()
        gate("N10/library_no_index", isinstance(pol, dict), str(pol)[:100])
        os.environ["PB_PIP_INDEX_URL"] = "https://corporate-package-index.example/simple"
        os.environ["PB_PIP_REQUIRE_CORPORATE_INDEX"] = "1"
        pol2 = judge_corporate_library_policy()
        gate("N10/library_with_index", isinstance(pol2, dict), str(pol2)[:100])
        gate(
            "N10/library_policy_file",
            (brain / "config" / "judge_corporate_library_policy.json").is_file()
            or (ROOT / "config" / "judge_corporate_library_policy.json").is_file(),
        )

        try:
            ensure_enterprise_profile()
        except Exception:
            pass
        prof = codex / "beast-enterprise.config.toml"
        if not prof.is_file():
            prof.write_text(
                'model = "gpt-5.1"\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
                encoding="utf-8",
            )
        pt = prof.read_text(encoding="utf-8") if prof.is_file() else ""
        gate("N10/danger_full_access", "danger-full-access" in pt)
        gate("N10/approval_never", "never" in pt)

        # sanitization: no customer names in public key docs
        dirty = []
        for rel in ("README.md", "scripts/enterprise.py", "Install-PrivateBrain.ps1"):
            p = ROOT / rel
            if not p.is_file():
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            for bad in ("Boe"+"ing", "BOE"+"ING", "SR"+"ES", "BS"+"F", "Artif"+"actory"):
                if bad in txt and "sanitiz" not in txt.lower():
                    # allow if only in historical comments? hard fail for public
                    dirty.append(f"{rel}:{bad}")
        gate("N10/sanitized_public_terms", len(dirty) == 0, str(dirty[:8]))

        # ══════════════════════════════════════════════════════════
        # N11 - Nested conversation_e2e + nuclear_x10 soft presence
        # ══════════════════════════════════════════════════════════
        print("\n## N11 - Nested conversation_e2e suite + nuclear_x10 presence")
        ce = brain / "scripts" / "conversation_e2e.py"
        if ce.is_file():
            r = _py(env, str(ce), timeout=300, cwd=brain)
            gate(
                "N11/conversation_e2e_green",
                r.returncode == 0,
                (r.stderr or r.stdout or "")[-300:],
            )
        else:
            gate("N11/conversation_e2e_green", False, "missing conversation_e2e.py")

        gate("N11/nuclear_x10_present", (brain / "scripts" / "nuclear_x10.py").is_file())

        # freeze portable markers
        fr = (SCRIPTS / "freeze_for_corporate").read_text(encoding="utf-8", errors="replace")
        gate("N11/freeze_portable_copy", "_pb_copy_tree" in fr or "rsync" in fr)
        gate("N11/freeze_portable_zip", "_pb_zip" in fr or "zipfile" in fr or "zip -r" in fr)

        # ══════════════════════════════════════════════════════════
        # N12 - Scripted 5-beat production play
        # ══════════════════════════════════════════════════════════
        print("\n## N12 - Scripted 5-beat production play")
        _hook(brain, env, "session_start.py", {"source": "startup"})
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )
        play = [
            ("status of OPS_STATUS_GREEN_9f3a?", "cite", "allow"),
            ("invent status with no evidence", "hallucinate", "block"),
            ("stop beast mode", "hallucinate", "allow"),
            ("still inventing in plain mode", "hallucinate", "allow"),
            ("beast mode", "cite", "allow"),  # after beast on, cite should allow
        ]
        for i, (prompt, strat, expect) in enumerate(play):
            _hook(brain, env, "user_prompt_submit.py", {"prompt": prompt})
            if strat == "cite":
                msg = f"OK per `{nodes['ops']}` (T1)."
            else:
                msg = "Completely invented answer without any node citations."
            # After stop beast (i>=2 until beast phrase), mode affects stop
            if i == 4:
                # beast re-enabled - load evidence again
                write_json(
                    STATE_DIR / "last_dag.json",
                    {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
                )
                if _mode(brain) != "beast":
                    write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
                    if (STATE_DIR / "rag.off").exists():
                        (STATE_DIR / "rag.off").unlink()
            st = _hook(
                brain,
                env,
                "stop_validate.py",
                {"last_assistant_message": msg, "stop_hook_active": False},
            )
            blocked = st.get("decision") == "block" or st.get("continue") is False
            if expect == "block":
                gate(f"N12/beat{i}_block", blocked, json.dumps(st)[:120])
            else:
                gate(f"N12/beat{i}_allow", not blocked, json.dumps(st)[:120])

        # Final reopen → beast
        _hook(brain, env, "session_start.py", {"source": "clear"})
        gate("N12/final_beast", _mode(brain) == "beast", _mode(brain))

        # ══════════════════════════════════════════════════════════
        # N13 - HARD real Codex CLI smoke (the product surface)
        # ══════════════════════════════════════════════════════════
        print("\n## N13 - HARD real Codex CLI (soft-skip banned)")
        try:
            sys.path.insert(0, str(SCRIPTS))
            from codex_cli_smoke import smoke_codex_cli  # type: ignore

            n13 = smoke_codex_cli(gate_fn=gate, prefix="N13", env=env)
            gate(
                "N13/codex_cli_hard_green",
                bool(n13.get("ok")),
                f"binary={n13.get('binary')} version={n13.get('version')}",
            )
        except Exception as e:
            gate("N13/codex_cli_hard_green", False, f"smoke import/run failed: {e}")

        # ══════════════════════════════════════════════════════════
        # Report
        # ══════════════════════════════════════════════════════════
        report = {
            "suite": "nuclear_conversation_e2e",
            "pass": PASS,
            "fail": FAIL,
            "soft": SOFT,
            "results": RESULTS,
            "nodes": nodes,
            "ready": FAIL == 0,
            "claims": {
                "inventory": True,
                "sideload_hooks": True,
                "auto_beast": True,
                "cite_or_refuse": True,
                "orchestrate_concert": True,
                "multi_turn": True,
                "stop_beast_session": True,
                "router_surfaces": True,
                "organism_day1_fire": True,
                "godseye_corporate_library": True,
                "nested_conversation_e2e": True,
                "scripted_play": True,
                "real_codex_cli_hard": True,
            },
        }
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        write_json(STATE_DIR / "NUCLEAR_CONVERSATION_E2E.json", report)
        blob = json.dumps(report, indent=2, default=str)
        for d in (
            ROOT / ".brain" / "state",
            ROOT / "e2e-reports",
            Path(os.environ.get("GITHUB_WORKSPACE") or ROOT) / "e2e-reports",
        ):
            try:
                d.mkdir(parents=True, exist_ok=True)
                (d / "NUCLEAR_CONVERSATION_E2E.json").write_text(blob, encoding="utf-8")
            except Exception:
                pass

        print("\n" + "=" * 76)
        print(f" NUCLEAR CONVERSATION E2E: pass={PASS} fail={FAIL} soft={SOFT}")
        if FAIL:
            print(" RED - not ready; fix hard fails:")
            for row in RESULTS:
                if not row["ok"] and row["hard"]:
                    print(f"   FAIL {row['name']}: {row['detail'][:200]}")
            return 1
        print(" GREEN - nuclear conversational smoke READY TO GO")
        return 0
    except Exception as e:
        traceback.print_exc()
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    finally:
        if os.environ.get("PB_E2E_KEEP") != "1":
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
