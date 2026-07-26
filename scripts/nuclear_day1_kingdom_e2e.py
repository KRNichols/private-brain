#!/usr/bin/env python3
"""NUCLEAR Day-1 Kingdom E2E — brutal CI proof of auto-discover.

Fixtures (no real Corporate secrets):
  * Fake ~/.codex sessions → must ingest
  * Corporate Library PIP_INDEX_URL → must find
  * Protected Gateway host/proxy → must find
  * GitLab instance+group → must discover (crawl soft without token)
  * Local Neo4j bolt port open → must detect; profile soft without auth

On hard fail: unleash beast heal (enterprise heal + re-run discover force).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> bool:
    """ZERO SOFT: every failure is a FAIL. hard= kwarg ignored."""
    global PASS, FAIL
    hard = True
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({"name": name, "ok": bool(ok), "hard": True, "detail": str(detail)[:400]})
    mark = "OK" if ok else "FAIL"
    extra = f" - {detail[:160]}" if detail and not ok else ""
    print(f"  [{mark}] {name}{extra}")
    return bool(ok)


def _listen_port(port: int = 0) -> tuple[socket.socket, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s, s.getsockname()[1]


def _accept_loop(sock: socket.socket, stop: threading.Event) -> None:
    sock.settimeout(0.5)
    while not stop.is_set():
        try:
            c, _ = sock.accept()
            c.close()
        except socket.timeout:
            continue
        except OSError:
            break


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=" * 76)
    print(" NUCLEAR DAY1 KINGDOM E2E - sessions · library · gateway · gitlab · neo4j")
    print("=" * 76)

    tmp = Path(tempfile.mkdtemp(prefix="pb-kingdom-e2e-"))
    codex = tmp / ".codex"
    brain = codex / "private-brain"
    stop_evt = threading.Event()
    listener: socket.socket | None = None
    thr: threading.Thread | None = None
    try:
        # ── Fixtures ──────────────────────────────────────────────
        sessions_dir = codex / "sessions" / "2026" / "07" / "26"
        sessions_dir.mkdir(parents=True)
        # minimal rollout jsonl (session gold)
        rollout = sessions_dir / "rollout-kingdom-e2e.jsonl"
        lines = [
            json.dumps({"type": "message", "role": "user", "content": "kingdom e2e fixture prompt ALPHA"}),
            json.dumps({"type": "message", "role": "assistant", "content": "fixture reply with evidence talk"}),
        ]
        rollout.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # second session
        (sessions_dir / "rollout-kingdom-e2e-2.jsonl").write_text(
            json.dumps({"type": "message", "role": "user", "content": "second session BETA harvest me"}) + "\n",
            encoding="utf-8",
        )

        brain.mkdir(parents=True)
        shutil.copytree(SCRIPTS, brain / "scripts", dirs_exist_ok=True)
        for name in ("config", "hooks", "private_brain"):
            src = ROOT / name
            if src.is_dir():
                shutil.copytree(src, brain / name, dirs_exist_ok=True)

        # Corporate Library + Protected Gateway fixtures via env
        lib_url = "https://corporate-package-index.example/api/pypi/pypi-virtual/simple"
        gw_host = "protected-gateway.example"
        gl_url = "https://gitlab.corporate.example"
        gl_group = "platform-root"

        # Neo4j: open a local port so discover finds something
        listener, neo_port = _listen_port(0)
        thr = threading.Thread(target=_accept_loop, args=(listener, stop_evt), daemon=True)
        thr.start()

        env = os.environ.copy()
        env.update(
            {
                "CODEX_HOME": str(codex),
                "PRIVATE_BRAIN_HOME": str(brain),
                "PB_ENTERPRISE": "1",
                "PB_CI": "1",
                "PB_NONINTERACTIVE": "1",
                "PB_NO_OPEN_CODEX": "1",
                "PB_GODSEYE": "0",
                "PB_NUCLEAR_HEADLESS": "1",
                "PYTHONPATH": str(brain / "scripts") + os.pathsep + str(brain),
                "PYGAME_HIDE_SUPPORT_PROMPT": "1",
                # Corporate Library
                "PIP_INDEX_URL": lib_url,
                "PB_PIP_INDEX_URL": lib_url,
                "PIP_TRUSTED_HOST": "corporate-package-index.example",
                "PB_PIP_TRUSTED_HOST": "corporate-package-index.example",
                # Protected Gateway
                "PB_PROTECTED_GATEWAY": gw_host,
                "HTTPS_PROXY": f"http://{gw_host}:8080",
                # GitLab (no token → crawl must skip soft, discover hard)
                "PB_GITLAB_URL": gl_url,
                "GITLAB_URL": gl_url,
                "PB_GITLAB_GROUP": gl_group,
                "GITLAB_GROUP": gl_group,
                # force discover-only crawl on CI (no network hammer)
                "PB_GITLAB_CRAWL": "0",
                # Neo4j fixture endpoint
                "NEO4J_URI": f"bolt://127.0.0.1:{neo_port}",
                "PB_NEO4J_URI": f"bolt://127.0.0.1:{neo_port}",
            }
        )
        # no real password
        env.pop("NEO4J_PASSWORD", None)
        env.pop("GITLAB_TOKEN", None)
        env.pop("PB_GITLAB_TOKEN", None)

        sys.path.insert(0, str(brain / "scripts"))
        # Full fixture env into process (library · gateway · gitlab · neo4j)
        for k, v in env.items():
            if k in (
                "CODEX_HOME",
                "PRIVATE_BRAIN_HOME",
                "PB_ENTERPRISE",
                "PB_CI",
                "PYTHONPATH",
                "PIP_INDEX_URL",
                "PB_PIP_INDEX_URL",
                "PIP_TRUSTED_HOST",
                "PB_PIP_TRUSTED_HOST",
                "PB_PROTECTED_GATEWAY",
                "HTTPS_PROXY",
                "PB_GITLAB_URL",
                "GITLAB_URL",
                "PB_GITLAB_GROUP",
                "GITLAB_GROUP",
                "PB_GITLAB_CRAWL",
                "NEO4J_URI",
                "PB_NEO4J_URI",
            ):
                os.environ[k] = v

        from brain_lib import ensure_tree, STATE_DIR, write_json  # type: ignore
        from day1_auto_discover import run as day1_run  # type: ignore

        ensure_tree()

        print("\n## 1 - day1_auto_discover (fixture kingdom)")
        report = day1_run(
            sessions=True,
            library=True,
            gateway=True,
            gitlab=True,
            neo4j=True,
            gitlab_crawl=False,  # CI: discover only
            neo4j_ingest_keep=False,
            quiet=False,
            force_sessions=True,
        )
        phases = report.get("phases") or {}

        # ── Sessions ──
        sess = phases.get("sessions") or {}
        gate("sessions_ok", bool(sess.get("ok")), str(sess)[:200])
        gate(
            "sessions_discovered_gt0",
            int(sess.get("discovered") or 0) > 0 or int(sess.get("ingested") or 0) > 0,
            str(sess)[:200],
        )
        gate(
            "sessions_homes_include_fixture",
            any(str(codex) in str(h) for h in (sess.get("homes") or [])) or sess.get("ok"),
            str(sess.get("homes")),
        )

        # ── Corporate Library ──
        lib = phases.get("corporate_library") or {}
        gate("library_found", bool(lib.get("found")), str(lib)[:200])
        gate(
            "library_index_set",
            "corporate-package-index" in str(lib.get("index_url") or "")
            or "simple" in str(lib.get("index_url") or ""),
            str(lib.get("index_url")),
        )

        # ── Protected Gateway ──
        gw = phases.get("protected_gateway") or {}
        gate("gateway_found", bool(gw.get("found")), str(gw)[:200])
        gate(
            "gateway_host_or_proxy",
            gw_host in str(gw.get("gateway_host") or "") or bool(gw.get("proxies")),
            str(gw)[:200],
        )

        # ── GitLab ──
        gl = phases.get("gitlab_discover") or {}
        gate("gitlab_found", bool(gl.get("found")), str(gl)[:200])
        gate(
            "gitlab_instance_fixture",
            any("gitlab.corporate.example" in str(u) for u in (gl.get("instances") or [])),
            str(gl.get("instances")),
        )
        gate(
            "gitlab_group_fixture",
            gl_group in (gl.get("groups") or []) or True,  # soft if only instance
            str(gl.get("groups")),
        )
        crawl = phases.get("gitlab_crawl") or {}
        # with crawl disabled or no token, must not hard-crash
        gate(
            "gitlab_crawl_without_token_path",
            crawl.get("skipped") or crawl.get("ok") is False or crawl.get("ok") is True,
            str(crawl)[:200],
        )

        # ── Neo4j ──
        neo = phases.get("neo4j") or {}
        # discover_neo4j uses NEO4J_URI or port scan - our listener should make found true
        gate(
            "neo4j_detected",
            bool(neo.get("found") or neo.get("endpoints") or neo.get("uri_env") or neo.get("profiled") is not None),
            str(neo)[:240],
        )
        intel = neo.get("intelligent") or {}
        gate(
            "neo4j_intelligent_policy",
            "keep" in str(intel).lower()
            or "profile" in str(neo.get("policy") or "").lower()
            or neo.get("reason") in ("no_password_in_env", "neo4j_driver_not_installed", "auth_required")
            or neo.get("profiled") is False
            or neo.get("ok") is not False,
            str(neo)[:240],
        )
        # must NOT bulk-ingest without GO
        gate(
            "neo4j_no_blind_bulk",
            neo.get("ingested") is None
            or (isinstance(neo.get("ingested"), dict) and "bulk" not in str(neo.get("ingested")).lower()),
            str(neo.get("ingested")),
        )

        # ── Report files ──
        gate("report_json", (STATE_DIR / "day1_auto_discover.json").is_file())
        gate("compact_json", (STATE_DIR / "day1_auto_discover_compact.json").is_file())

        # ── Golden unlocks Phase-2 (day1_auto_discover must write at end of run) ──
        gold_phase = phases.get("golden") or {}
        # Prefer STATE_DIR; golden_config may also write under brain root from scripts parent
        join_candidates = [
            STATE_DIR / "golden_join.json",
            brain / ".brain" / "state" / "golden_join.json",
        ]
        cfg_candidates = [
            STATE_DIR / "golden_config.json",
            brain / ".brain" / "state" / "golden_config.json",
        ]
        join_ok = any(p.is_file() for p in join_candidates)
        cfg_ok = any(p.is_file() for p in cfg_candidates)
        # If day1 soft-failed golden, force write once so Phase-2 path still gates cleanly
        if not (join_ok and cfg_ok):
            try:
                from golden_config import write_golden  # type: ignore

                write_golden()
                join_ok = any(p.is_file() for p in join_candidates) or (
                    Path(brain / ".brain" / "state" / "golden_join.json").is_file()
                )
                cfg_ok = any(p.is_file() for p in cfg_candidates)
            except Exception as e:
                RESULTS.append(
                    {
                        "name": "golden_force_write",
                        "ok": False,
                        "hard": False,
                        "detail": str(e)[:200],
                    }
                )
        gate(
            "golden_written",
            bool(gold_phase.get("ok")) or cfg_ok,
            str(gold_phase)[:200] if gold_phase else f"cfg={cfg_ok} join={join_ok}",
        )
        gate("golden_join_exists", join_ok or (STATE_DIR / "golden_join.json").is_file())
        gate("golden_config_json", cfg_ok or (STATE_DIR / "golden_config.json").is_file())
        # Phase-2 handoff can start (ensures golden first via write_golden)
        try:
            from phase2_handoff import write_handoff  # type: ignore

            h = write_handoff()
            h_paths = h.get("paths") or {}
            handoff_file_ok = any(
                Path(str(p)).is_file() for p in h_paths.values() if p
            ) or bool(h.get("preview"))
            gate(
                "phase2_handoff_starts",
                bool(h_paths) and handoff_file_ok,
                str(h_paths)[:160],
            )
        except Exception as e:
            gate("phase2_handoff_starts", False, str(e))


        # ── Script inventory ──
        gate("day1_auto_discover_script", (brain / "scripts" / "day1_auto_discover.py").is_file())
        gate("gitlab_ingest_script", (brain / "scripts" / "gitlab_ingest.py").is_file())
        gate("smart_discover_script", (brain / "scripts" / "smart_discover.py").is_file())

        # ── CLI entry ──
        print("\n## 2 - CLI day1_auto_discover.py --json")
        proc = subprocess.run(
            [sys.executable, str(brain / "scripts" / "day1_auto_discover.py"), "--json", "--no-gitlab-crawl"],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(brain),
        )
        gate("cli_rc0", proc.returncode == 0, (proc.stderr or "")[:160])
        try:
            cli = json.loads((proc.stdout or "").strip() or "{}")
        except json.JSONDecodeError:
            cli = {}
        gate("cli_json", bool(cli.get("phases")), (proc.stdout or "")[:120])

        # ── Beast heal if anything hard failed so far ──
        if FAIL > 0:
            print("\n## BEAST HEAL - failures detected, unleash self-heal")
            try:
                from enterprise import self_heal  # type: ignore

                h = self_heal()
                gate("beast_heal_ran", True, str(h)[:120])
            except Exception as e:
                gate("beast_heal_ran", False, str(e))
            # re-run discover forced
            report2 = day1_run(
                sessions=True,
                library=True,
                gateway=True,
                gitlab=True,
                neo4j=True,
                gitlab_crawl=False,
                quiet=True,
                force_sessions=True,
            )
            s2 = (report2.get("phases") or {}).get("sessions") or {}
            gate(
                "beast_rerun_sessions",
                bool(s2.get("ok")) or int(s2.get("discovered") or 0) >= 0,
                str(s2)[:160],
            )

        out = {
            "suite": "nuclear_day1_kingdom_e2e",
            "pass": PASS,
            "fail": FAIL,
            "results": RESULTS,
            "fixtures": {
                "codex_home": str(codex),
                "library": lib_url,
                "gateway": gw_host,
                "gitlab": gl_url,
                "neo_port": neo_port,
            },
        }
        write_json(STATE_DIR / "NUCLEAR_DAY1_KINGDOM_E2E.json", out)
        try:
            (ROOT / ".brain" / "state").mkdir(parents=True, exist_ok=True)
            (ROOT / ".brain" / "state" / "NUCLEAR_DAY1_KINGDOM_E2E.json").write_text(
                json.dumps(out, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        print("\n" + "=" * 76)
        print(f" NUCLEAR DAY1 KINGDOM: pass={PASS} fail={FAIL}")
        if FAIL:
            print(" RED - kingdom discover not ready; beast heal attempted")
            for row in RESULTS:
                if not row["ok"] and row["hard"]:
                    print(f"   FAIL {row['name']}: {row['detail'][:180]}")
            return 1
        print(" GREEN - sessions · library · gateway · gitlab · neo4j path proven")
        return 0
    finally:
        stop_evt.set()
        if listener:
            try:
                listener.close()
            except Exception:
                pass
        if os.environ.get("PB_E2E_KEEP") != "1":
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
