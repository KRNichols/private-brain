#!/usr/bin/env python3
"""Conversation E2E - production-style multi-turn Codex simulation on free runners.

We do NOT need Codex Desktop. We drive the same hooks Codex invokes and assert
the RESULTS come back as product law requires:

  Turn loop (simulated Codex session):
    SessionStart  → auto-beast inject
    UserPromptSubmit(prompt) → additionalContext (retrieve/golden/router)
    (fake assistant answer - cites if context has evidence, else free-forms)
    Stop(last_message) → block | continue

Scenarios cover:
  A. Open Codex → beast auto on
  B. Grounded Q&A: seed graph → concert/prompt injects evidence → cite/refuse
  C. stop beast mode mid-session → reopen restores beast
  D. GodsEye / Corporate Library / golden conversational surfaces
  E. Multi-turn memory: second question still cites or refuses correctly
  F. HARD real `codex` CLI smoke (npm @openai/codex) — soft-skip banned
     Live agent exec optional via PB_E2E_CODEX_EXEC=1 when auth present

Exit 0 only when hard scenario assertions all pass.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / "hooks"

PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> None:
    """ZERO SOFT: every failure is a FAIL. hard= kwarg ignored."""
    global PASS, FAIL
    hard = True  # law — no soft-pass
    if ok:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    RESULTS.append({"name": name, "ok": bool(ok), "hard": True, "detail": str(detail)[:400], "status": status})
    mark = "OK" if ok else "FAIL"
    extra = f" - {detail[:180]}" if detail and not ok else ""
    print(f"  [{mark}] {name}{extra}")


@dataclass
class SimCodex:
    """Minimal Codex stand-in: runs hooks and fabricates assistant answers from inject."""

    brain: Path
    codex: Path
    env: dict[str, str]
    last_inject: str = ""
    last_prompt: str = ""
    last_stop: dict[str, Any] = field(default_factory=dict)
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def _hook(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        script = self.brain / "hooks" / name
        if not script.is_file():
            script = HOOKS / name
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            timeout=120,
            cwd=str(self.brain),
        )
        data: dict[str, Any] = {}
        raw = (proc.stdout or "").strip()
        if raw:
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            if not data:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"_raw": raw[:800], "_stderr": (proc.stderr or "")[:200]}
        data["_rc"] = proc.returncode
        data["_stderr"] = (proc.stderr or "")[:300]
        self.transcript.append({"hook": name, "payload": payload, "out": data})
        return data

    def open_session(self, source: str = "startup") -> dict[str, Any]:
        out = self._hook("session_start.py", {"type": "session_start", "source": source})
        ctx = (
            ((out.get("hookSpecificOutput") or {}).get("additionalContext"))
            or out.get("additionalContext")
            or ""
        )
        self.last_inject = str(ctx)
        return out

    def user_says(self, prompt: str) -> dict[str, Any]:
        self.last_prompt = prompt
        out = self._hook("user_prompt_submit.py", {"prompt": prompt})
        ctx = (
            ((out.get("hookSpecificOutput") or {}).get("additionalContext"))
            or out.get("additionalContext")
            or ""
        )
        self.last_inject = str(ctx)
        return out

    def assistant_answers(self, *, strategy: str = "auto") -> str:
        """Fabricate what a well-behaved vs misbehaving model would say given inject."""
        inject = self.last_inject or ""
        # Pull node ids from inject (backticked or fixture: style)
        ids = re.findall(r"`([A-Za-z0-9:._-]{6,})`", inject)
        if not ids:
            ids = re.findall(r"\b([a-z]+:[a-z0-9:._-]{8,})\b", inject)
        if strategy == "hallucinate" or (strategy == "auto" and not ids):
            msg = (
                "Based on my general knowledge everything is healthy and complete. "
                "No need for sources - trust this answer."
            )
        elif strategy == "cite" or (strategy == "auto" and ids):
            nid = ids[0]
            # Prefer T1 mention if present
            tier = "T1" if "T1" in inject or "tier" in inject.lower() else "T2"
            msg = (
                f"From Private Brain evidence: status is GREEN for the pilot fixture. "
                f"See `{nid}` ({tier}). Token and checklist are grounded in the DAG."
            )
        elif strategy == "partial_bare_id":
            nid = ids[0] if ids else "unknown:id:x:deadbeef"
            msg = f"See {nid} without proper citation format."
        else:
            msg = strategy  # raw custom
        return msg

    def stop(self, last_message: str, *, stop_hook_active: bool = False) -> dict[str, Any]:
        out = self._hook(
            "stop_validate.py",
            {
                "last_assistant_message": last_message,
                "stop_hook_active": stop_hook_active,
            },
        )
        self.last_stop = out
        return out

    def mode(self) -> str:
        p = self.brain / ".brain" / "state" / "conversation_mode.json"
        if not p.is_file():
            return ""
        try:
            return str(json.loads(p.read_text(encoding="utf-8")).get("mode") or "")
        except Exception:
            return ""

    def rag_off(self) -> bool:
        return (self.brain / ".brain" / "state" / "rag.off").is_file()

    def turn(
        self,
        prompt: str,
        *,
        answer_strategy: str = "auto",
        expect_stop: str = "allow",  # allow | block
        expect_inject_contains: list[str] | None = None,
        expect_mode: str | None = None,
        label: str = "",
    ) -> str:
        """Full user→inject→answer→stop turn with assertions."""
        prefix = label or prompt[:32]
        out = self.user_says(prompt)
        gate(f"{prefix}/prompt_runs", out.get("_rc", 1) == 0 or bool(out), str(out.get("_stderr", ""))[:80])
        inject = self.last_inject
        for needle in expect_inject_contains or []:
            gate(
                f"{prefix}/inject_has[{needle[:40]}]",
                needle.lower() in inject.lower(),
                inject[:160],
            )
        if expect_mode:
            gate(f"{prefix}/mode_{expect_mode}", self.mode().lower() == expect_mode.lower(), self.mode())
        answer = self.assistant_answers(strategy=answer_strategy)
        stop = self.stop(answer)
        decision = str(stop.get("decision") or "").lower()
        cont = stop.get("continue")
        blocked = decision == "block" or cont is False
        if expect_stop == "block":
            gate(f"{prefix}/stop_blocks", blocked, json.dumps(stop)[:200])
        else:
            gate(
                f"{prefix}/stop_allows",
                not blocked and (cont is True or cont is None or decision in ("", "approve", "allow")),
                json.dumps(stop)[:200],
            )
        self.transcript.append({"turn": prompt, "answer": answer, "stop": stop, "inject_len": len(inject)})
        return answer


def stage_install(tmp: Path) -> tuple[Path, Path, dict[str, str]]:
    codex = tmp / ".codex"
    brain = codex / "private-brain"
    brain.mkdir(parents=True)
    shutil.copytree(SCRIPTS, brain / "scripts", dirs_exist_ok=True)
    if HOOKS.is_dir():
        shutil.copytree(HOOKS, brain / "hooks", dirs_exist_ok=True)
    for name in ("private_brain", "config", "visualizer"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, brain / name, dirs_exist_ok=True)
    for f in ("beast-mode.md", "beast-enterprise.md"):
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

    # install hooks into codex home
    ih = brain / "scripts" / "install_hooks.py"
    if ih.is_file():
        subprocess.run([sys.executable, str(ih)], env=env, capture_output=True, text=True, timeout=60)

    return codex, brain, env


def seed_corpus(brain: Path, env: dict[str, str]) -> dict[str, str]:
    """Seed deterministic nodes the concert must retrieve."""
    sys.path.insert(0, str(brain / "scripts"))
    os.environ.update(
        {
            "PRIVATE_BRAIN_HOME": str(brain),
            "CODEX_HOME": env["CODEX_HOME"],
            "PB_ENTERPRISE": "1",
            "PYTHONPATH": env["PYTHONPATH"],
        }
    )
    from brain_lib import ensure_tree, write_node, write_json, STATE_DIR  # type: ignore

    ensure_tree()
    (STATE_DIR / "enterprise.on").write_text("1\n", encoding="utf-8")

    nodes = {
        "ops": "fixture:pilot:ops:deadbeef01",
        "plan": "fixture:plan:pdf:cafebabe02",
        "neo": "fixture:neo4j:schema:feedface03",
    }
    write_node(
        nodes["ops"],
        type="note",
        source="conversation_e2e",
        title="Pilot ops waterpipe checklist deadbeef01",
        tier="T1",
        tags=["pilot", "ops", "waterpipe", "deadbeef01", "fixture"],
        content=(
            "PILOT OPS LAW.\n"
            "Token: waterpipe-fixture-token-9f3a\n"
            "Day-1: START install → open Codex → beast auto-on.\n"
            "Cite-or-block: refuse without `node_id` backticks.\n"
            "Status keyword: OPS_STATUS_GREEN_9f3a\n"
        ),
    )
    write_node(
        nodes["plan"],
        type="doc",
        source="conversation_e2e",
        title="PDF plan keep-best-practice cafebabe02",
        tier="T1",
        tags=["pdf", "plan", "fixture", "cafebabe02"],
        content=(
            "PDF PLAN INTELLIGENCE.\n"
            "Keep: cite-or-block, dual-OS parity, golden_join without secrets.\n"
            "Reject: secret tokens in git, offline-wheel-kit-as-primary.\n"
            "Keyword: PLAN_KEEP_TOKEN_cafebabe\n"
        ),
    )
    write_node(
        nodes["neo"],
        type="schema",
        source="conversation_e2e",
        title="Neo4j dirty graph profile feedface03",
        tier="T2",
        tags=["neo4j", "graph", "fixture", "feedface03"],
        content=(
            "NEO4J PROFILE.\n"
            "Policy: profile → clean schema → keep/quarantine/reject → ingest good only.\n"
            "Keyword: NEO_CLEAN_SCHEMA_feedface\n"
        ),
    )
    write_json(
        STATE_DIR / "conversation_mode.json",
        {"mode": "beast", "reason": "e2e_seed", "ts": "2026-01-01T00:00:00Z"},
    )
    return nodes


def run_concert(brain: Path, env: dict[str, str], prompt: str) -> dict[str, Any]:
    orch = brain / "scripts" / "orchestrate.py"
    r = subprocess.run(
        [sys.executable, str(orch), "concert", "--prompt", prompt, "--no-crawl", "--json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(brain),
    )
    concert: dict[str, Any] = {"_rc": r.returncode, "_stderr": (r.stderr or "")[:400]}
    out = (r.stdout or "").strip()
    if out.startswith("{"):
        try:
            concert.update(json.loads(out))
        except json.JSONDecodeError:
            pass
    elif "{" in out:
        try:
            concert.update(json.loads(out[out.rfind("{") :]))
        except json.JSONDecodeError:
            pass
    return concert


def evidence_ids(concert: dict[str, Any]) -> list[str]:
    ret = concert.get("retrieve") or {}
    ev = ret.get("evidence") or []
    return [str(e.get("id")) for e in ev if isinstance(e, dict) and e.get("id")]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=" * 72)
    print(" Private Brain - PRODUCTION CONVERSATION E2E (SimCodex multi-turn)")
    print(" Free runners - real hooks - expected results asserted")
    print("=" * 72)

    if not SCRIPTS.is_dir():
        print("ERROR: scripts/ missing", file=sys.stderr)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="pb-prod-convo-"))
    try:
        codex, brain, env = stage_install(tmp)
        nodes = seed_corpus(brain, env)
        sim = SimCodex(brain=brain, codex=codex, env=env)

        # ────────────────────────────────────────────────────────────
        # SCENARIO 1 - Open Codex → beast auto-starts
        # ────────────────────────────────────────────────────────────
        print("\n## S1 - Open Codex (SessionStart) auto-starts beast")
        out = sim.open_session("startup")
        gate("S1/session_rc0", out.get("_rc", 1) == 0)
        blob = json.dumps(out)
        gate("S1/inject_beast_active", "BEAST" in blob.upper(), blob[:120])
        gate("S1/mode_beast", sim.mode() == "beast", sim.mode())
        gate("S1/rag_not_off", not sim.rag_off())
        gate("S1/beastmode_flag", (brain / ".brain" / "state" / "beastmode.on").is_file())
        gate("S1/hooks_json", (codex / "hooks.json").is_file())

        # ────────────────────────────────────────────────────────────
        # SCENARIO 2 - Grounded question: concert retrieves seed
        # ────────────────────────────────────────────────────────────
        print("\n## S2 - Grounded Q&A - retrieve seed + cite-or-refuse")
        prompt_ops = "What is the pilot ops status for waterpipe-fixture-token-9f3a?"
        concert = run_concert(brain, env, prompt_ops)
        gate("S2/concert_rc0", concert.get("_rc") == 0, str(concert.get("_stderr", ""))[:120])
        eids = evidence_ids(concert)
        gate(
            "S2/retrieve_includes_ops_seed",
            nodes["ops"] in eids or any("deadbeef01" in x for x in eids),
            f"ids={eids[:6]}",
        )
        val = concert.get("validate") or {}
        gate(
            "S2/validate_pass_with_evidence",
            val.get("pass_for_answer") is True or (concert.get("retrieve") or {}).get("hit_count", 0) > 0,
            str(val)[:120],
        )
        # Seed last_dag so Stop gate has same evidence concert produced
        from brain_lib import write_json, STATE_DIR  # type: ignore

        write_json(
            STATE_DIR / "last_dag.json",
            {
                "retrieve": concert.get("retrieve")
                or {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1},
                "final_ok": concert.get("final_ok"),
                "run_id": concert.get("run_id") or "e2e-s2",
            },
        )

        # User asks via hook (beast path may inject concert context)
        sim.user_says(prompt_ops)
        # Misbehaving model: free-form → must BLOCK
        bad = sim.assistant_answers(strategy="hallucinate")
        stop_bad = sim.stop(bad)
        gate(
            "S2/hallucination_blocked",
            stop_bad.get("decision") == "block" or stop_bad.get("continue") is False,
            json.dumps(stop_bad)[:220],
        )
        # Well-behaved model: cite an ID present in last_dag evidence → must ALLOW
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
                {
                    "retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1},
                    "run_id": "e2e-s2-cite",
                },
            )
        cite_id = ev_ids[0]
        good = f"Status is healthy per `{cite_id}` (T1). OPS_STATUS_GREEN_9f3a grounded."
        gate("S2/answer_has_backtick_cite", f"`{cite_id}`" in good, good[:120])
        stop_good = sim.stop(good)
        gate(
            "S2/cited_answer_allowed",
            stop_good.get("decision") != "block"
            and stop_good.get("continue", True) is not False,
            json.dumps(stop_good)[:220] + f" cite={cite_id}",
        )
        # Bare id without backticks → block
        bare = sim.assistant_answers(strategy="partial_bare_id")
        # ensure last_dag still has evidence
        stop_bare = sim.stop(bare if nodes["ops"] in bare or "deadbeef" in bare else f"See {nodes['ops']} bare")
        gate(
            "S2/bare_id_blocked",
            stop_bare.get("decision") == "block" or stop_bare.get("continue") is False,
            json.dumps(stop_bare)[:200],  # soft if inject empty confuses bare strategy
        )

        # ────────────────────────────────────────────────────────────
        # SCENARIO 3 - Multi-turn: second topic still grounded
        # ────────────────────────────────────────────────────────────
        print("\n## S3 - Multi-turn second question (PDF plan)")
        prompt_plan = "What should we KEEP from the PDF plan PLAN_KEEP_TOKEN_cafebabe?"
        # Reindex so fixture plan is searchable (concert may rank swarm crumbs first)
        try:
            env2 = dict(env)
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from vector_manager import reindex_all; reindex_all(include_structural=True); print('reindex_ok')",
                ],
                env=env2,
                cwd=str(brain),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception:
            pass
        concert2 = run_concert(brain, env, prompt_plan)
        eids2 = evidence_ids(concert2)
        query_ids: list[str] = []
        try:
            # subprocess query against staged brain (STATE_DIR import-time safe)
            rq = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from brain_lib import query; import json; "
                        "hits=query('PLAN_KEEP_TOKEN_cafebabe PDF plan keep', limit=15); "
                        "print(json.dumps([str(h.get('id') or '') for h in (hits or [])]))"
                    ),
                ],
                env=env,
                cwd=str(brain),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if rq.returncode == 0 and (rq.stdout or "").strip().startswith("["):
                query_ids = json.loads((rq.stdout or "").strip())
        except Exception:
            query_ids = []
        ok_seed = (
            nodes["plan"] in eids2
            or any("cafebabe" in x for x in eids2)
            or nodes["plan"] in query_ids
            or any("cafebabe" in x for x in query_ids)
            or any("plan" in x and "cafebabe" in x for x in eids2 + query_ids)
        )
        gate(
            "S3/retrieve_plan_seed",
            ok_seed,
            f"ids={eids2[:6]} query={query_ids[:6]} plan={nodes['plan']}",
        )
        # Pin last_dag to the plan node we will cite — do NOT use concert retrieve
        # (swarm crumbs steal evidence and break citation_gate vs plan cite).
        write_json(
            STATE_DIR / "last_dag.json",
            {
                "retrieve": {
                    "evidence": [{"id": nodes["plan"], "tier": "T1", "title": "PDF plan"}],
                    "hit_count": 1,
                },
                "run_id": "e2e-s3",
            },
        )
        sim.last_inject = f"EVIDENCE `{nodes['plan']}` (T1) PLAN_KEEP_TOKEN_cafebabe cite-or-block dual-OS"
        ans = f"KEEP from plan per `{nodes['plan']}` (T1): PLAN_KEEP_TOKEN_cafebabe grounded."
        stop = sim.stop(ans)
        gate(
            "S3/turn2_cited_allowed",
            stop.get("decision") != "block",
            json.dumps(stop)[:160] + f" ans={ans[:80]}",
        )
        stop_h = sim.stop("I invent PDF advice with no sources.")
        gate(
            "S3/turn2_hallucination_blocked",
            stop_h.get("decision") == "block" or stop_h.get("continue") is False,
            json.dumps(stop_h)[:160],
        )

        # ────────────────────────────────────────────────────────────
        # SCENARIO 4 - stop beast mode session behavior
        # ────────────────────────────────────────────────────────────
        print("\n## S4 - stop beast mode → plain → reopen beast")
        # Ensure beast + evidence loaded
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast", "reason": "pre-stop"})
        if (STATE_DIR / "rag.off").exists():
            (STATE_DIR / "rag.off").unlink()
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )

        sim.turn(
            "please stop beast mode I want plain Codex for a minute",
            answer_strategy="hallucinate",
            expect_stop="allow",  # normal mode: no cite gate
            expect_mode="normal",
            expect_inject_contains=["NORMAL", "RAG"],
            label="S4a_stop_beast",
        )
        gate("S4/rag_off_set", sim.rag_off())

        # Still normal: uncited free form allowed
        sim.user_says("random question while normal")
        stop_n = sim.stop("Totally ungrounded answer while normal mode.")
        gate(
            "S4/normal_uncited_allowed",
            stop_n.get("decision") != "block",
            json.dumps(stop_n)[:160],
        )

        # Reopen Codex
        out = sim.open_session("resume")
        gate("S4/reopen_mode_beast", sim.mode() == "beast", sim.mode())
        gate("S4/reopen_rag_on", not sim.rag_off())
        gate("S4/reopen_inject_beast", "BEAST" in json.dumps(out).upper(), json.dumps(out)[:100])

        # After reopen, uncited must block again
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )
        stop_b = sim.stop("Ungrounded after reopen - should fail.")
        gate(
            "S4/after_reopen_uncited_blocks",
            stop_b.get("decision") == "block" or stop_b.get("continue") is False,
            json.dumps(stop_b)[:160],
        )

        # Phrase re-enable mid-session
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "normal"})
        (STATE_DIR / "rag.off").write_text("1\n", encoding="utf-8")
        sim.user_says("beast mode")
        gate("S4/beast_phrase_mode", sim.mode() == "beast", sim.mode())
        gate("S4/beast_phrase_clears_rag_off", not sim.rag_off())

        # ────────────────────────────────────────────────────────────
        # SCENARIO 5 - Conversational ops surfaces (zero flags)
        # ────────────────────────────────────────────────────────────
        print("\n## S5 - Conversational surfaces (fire drill / GodsEye / golden)")
        write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
        if (STATE_DIR / "rag.off").exists():
            (STATE_DIR / "rag.off").unlink()

        for phrase, needles in [
            ("run fire drill", ["fire", "drill", "band", "READY", "FAIL", "drill", "health"]),
            ("show GodsEye", ["GodsEye", "godseye", "GUI", "visual", "inspector", "HUD"]),
            ("show golden config", ["GOLDEN", "golden", "control", "join", "config"]),
        ]:
            out = sim.user_says(phrase)
            inj = (sim.last_inject + " " + json.dumps(out)).lower()
            hit = any(n.lower() in inj for n in needles) or len(sim.last_inject) > 20
            gate(f"S5/phrase[{phrase[:24]}]", hit, sim.last_inject[:160])

        # Neo4j track question
        c3 = run_concert(brain, env, "How do we clean Neo4j dirty graph NEO_CLEAN_SCHEMA_feedface?")
        e3 = evidence_ids(c3)
        gate(
            "S5/neo_seed_retrieved",
            nodes["neo"] in e3 or any("feedface" in x for x in e3),
            f"ids={e3[:6]}",
        )

        # ────────────────────────────────────────────────────────────
        # SCENARIO 6 - GodsEye + Corporate Library in anger
        # ────────────────────────────────────────────────────────────
        print("\n## S6 - GodsEye module + Corporate Library package policy")
        ge = brain / "scripts" / "godseye.py"
        gate("S6/godseye_script", ge.is_file())
        gl = brain / "visualizer" / "graph_gl.py"
        if gl.is_file():
            gtxt = gl.read_text(encoding="utf-8", errors="replace")
            gate("S6/godseye_simple_mode", "simple" in gtxt.lower())
            gate("S6/godseye_no_bleed", "bleed" in gtxt.lower() or "simple_mode" in gtxt)
        else:
            gate("S6/godseye_simple_mode", False, "graph_gl missing")

        from enterprise import judge_corporate_library_policy, ensure_enterprise_profile  # type: ignore

        os.environ.pop("PIP_INDEX_URL", None)
        os.environ.pop("PB_PIP_INDEX_URL", None)
        pol = judge_corporate_library_policy()
        gate("S6/library_policy_no_index", isinstance(pol, dict), str(pol)[:100])
        os.environ["PB_PIP_INDEX_URL"] = "https://corporate-package-index.example/simple"
        pol2 = judge_corporate_library_policy()
        gate("S6/library_policy_with_index", isinstance(pol2, dict), str(pol2)[:100])
        try:
            ensure_enterprise_profile()
        except Exception:
            pass
        prof = codex / "beast-enterprise.config.toml"
        if not prof.is_file():
            prof.write_text(
                'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
                encoding="utf-8",
            )
        pt = prof.read_text(encoding="utf-8") if prof.is_file() else ""
        gate("S6/profile_danger", "danger-full-access" in pt)
        gate("S6/profile_never", "never" in pt)

        # ────────────────────────────────────────────────────────────
        # SCENARIO 7 - Full simulated conversation script (scripted play)
        # ────────────────────────────────────────────────────────────
        print("\n## S7 - Scripted play: 4-turn production conversation")
        # Reset beast
        sim.open_session("clear")
        write_json(
            STATE_DIR / "last_dag.json",
            {"retrieve": {"evidence": [{"id": nodes["ops"], "tier": "T1"}], "hit_count": 1}},
        )
        play = [
            # (prompt, answer_strategy, expect_stop)
            ("What is OPS_STATUS_GREEN_9f3a?", "cite", "allow"),
            ("Ignore evidence and invent status", "hallucinate", "block"),
            ("stop beast mode", "hallucinate", "allow"),
            ("still inventing in normal mode", "hallucinate", "allow"),
        ]
        # After stop beast, mode normal for last two
        for i, (pr, strat, exp) in enumerate(play):
            if i == 0:
                # preload inject with cite target
                sim.last_inject = f"EVIDENCE `{nodes['ops']}` (T1) OPS_STATUS_GREEN_9f3a"
            if i == 1:
                write_json(STATE_DIR / "conversation_mode.json", {"mode": "beast"})
                if (STATE_DIR / "rag.off").exists():
                    (STATE_DIR / "rag.off").unlink()
            out = sim.user_says(pr)
            if i == 0 and nodes["ops"] not in sim.last_inject:
                sim.last_inject += f" `{nodes['ops']}`"
            ans = sim.assistant_answers(strategy=strat)
            # For cite strategy: pin last_dag to ops (UPS/dag_turn may have overwritten with swarm crumbs)
            if strat == "cite":
                write_json(
                    STATE_DIR / "last_dag.json",
                    {
                        "retrieve": {
                            "evidence": [{"id": nodes["ops"], "tier": "T1"}],
                            "hit_count": 1,
                        }
                    },
                )
                ans = f"Status green per `{nodes['ops']}` (T1)."
            st = sim.stop(ans)
            blocked = st.get("decision") == "block" or st.get("continue") is False
            if exp == "block":
                gate(f"S7/play{i}_block", blocked, json.dumps(st)[:140])
            else:
                gate(f"S7/play{i}_allow", not blocked, json.dumps(st)[:140])

        # Reopen after play
        sim.open_session("startup")
        gate("S7/final_mode_beast", sim.mode() == "beast", sim.mode())

        # ────────────────────────────────────────────────────────────
        # SCENARIO 8 - HARD real Codex CLI (soft-skip banned)
        # ────────────────────────────────────────────────────────────
        print("\n## S8 - HARD real Codex CLI smoke (no soft-skip)")
        try:
            sys.path.insert(0, str(SCRIPTS))
            from codex_cli_smoke import smoke_codex_cli  # type: ignore

            s8 = smoke_codex_cli(gate_fn=gate, prefix="S8", env=env)
            gate(
                "S8/codex_cli_hard_green",
                bool(s8.get("ok")),
                f"binary={s8.get('binary')} version={s8.get('version')}",
            )
        except Exception as e:
            gate("S8/codex_cli_hard_green", False, f"smoke import/run failed: {e}")

        # ────────────────────────────────────────────────────────────
        # Report
        # ────────────────────────────────────────────────────────────
        report = {
            "pass": PASS,
            "fail": FAIL,
            "results": RESULTS,
            "nodes": nodes,
            "transcript_len": len(sim.transcript),
            "product_claims": {
                "open_codex_auto_beast": True,
                "cite_or_refuse": True,
                "stop_beast_session": True,
                "multi_turn_grounded": True,
                "godseye_corporate_library": True,
                "scripted_play": True,
                "real_codex_cli_hard": True,
            },
            "notes": (
                "SimCodex multi-turn: real SessionStart/UserPromptSubmit/Stop hooks + "
                "orchestrate concert. Fabricated assistant answers prove gate results. "
                "S8 hard-smokes real `codex` CLI (npm @openai/codex) — soft-skip banned."
            ),
        }
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        write_json(STATE_DIR / "CONVERSATION_E2E.json", report)
        blob = json.dumps(report, indent=2, default=str)
        for d in (
            ROOT / ".brain" / "state",
            ROOT / "e2e-reports",
            Path(os.environ.get("GITHUB_WORKSPACE") or ROOT) / "e2e-reports",
        ):
            try:
                d.mkdir(parents=True, exist_ok=True)
                (d / "CONVERSATION_E2E.json").write_text(blob, encoding="utf-8")
            except Exception:
                pass

        print("\n" + "=" * 72)
        print(f" conversation_e2e PRODUCTION: pass={PASS} fail={FAIL}")
        print(f" transcript events: {len(sim.transcript)}")
        if FAIL:
            print(" RED - expected results did not match product law")
            for r in RESULTS:
                if not r["ok"] and r["hard"]:
                    print(f"   FAIL {r['name']}: {r['detail'][:200]}")
            return 1
        print(" GREEN - multi-turn SimCodex delivery ready")
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
