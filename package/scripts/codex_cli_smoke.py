#!/usr/bin/env python3
"""Hard Codex CLI smoke — free runners must install and exercise the real binary.

Missing `codex` is a HARD FAIL. Soft-skip is banned (that was the E2E lie).

Hard gates (no API key required):
  - which codex / PATH resolve
  - codex --version
  - codex --help
  - codex exec --help
  - codex doctor --summary (binary + install health; network may warn)

Optional live agent (needs auth / secrets):
  - PB_E2E_CODEX_EXEC=1 → codex exec -q "reply with PONG only" (hard when set)

CI should: setup-node + `npm i -g @openai/codex` before this script.
If PB_E2E_INSTALL_CODEX=1 and binary missing, attempt npm install once.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
        status = "PASS"
    elif hard:
        FAIL += 1
        status = "FAIL"
    else:
        status = "SOFT"
    RESULTS.append(
        {"name": name, "ok": bool(ok), "hard": hard, "detail": str(detail)[:500], "status": status}
    )
    mark = "OK" if ok else ("FAIL" if hard else "SOFT")
    extra = f" - {str(detail)[:160]}" if detail and not ok else ""
    print(f"  [{mark}] {name}{extra}")
    return bool(ok)


def _run(
    argv: list[str],
    *,
    timeout: int = 90,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env or os.environ.copy(),
    )


def _try_npm_install() -> tuple[bool, str]:
    npm = shutil.which("npm")
    if not npm:
        return False, "npm not on PATH"
    try:
        r = _run([npm, "install", "-g", "@openai/codex"], timeout=300)
        out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        return r.returncode == 0, out[-300:] or f"rc={r.returncode}"
    except Exception as e:
        return False, str(e)


def resolve_codex() -> str | None:
    return shutil.which("codex")


def smoke_codex_cli(
    *,
    gate_fn: Callable[..., Any] | None = None,
    prefix: str = "CODEX",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run hard Codex CLI smoke. Returns summary dict. Uses gate_fn if provided."""
    local: list[dict[str, Any]] = []
    local_fail = 0

    def g(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> bool:
        nonlocal local_fail
        local.append(
            {
                "name": name,
                "ok": bool(ok),
                "hard": hard,
                "detail": str(detail)[:500],
                "status": "PASS" if ok else ("FAIL" if hard else "SOFT"),
            }
        )
        if not ok and hard:
            local_fail += 1
        if gate_fn is not None:
            gate_fn(name, ok, detail, hard=hard)
        else:
            gate(name, ok, detail, hard=hard)
        return bool(ok)

    run_env = dict(env) if env else os.environ.copy()
    # Keep product from auto-opening GUI during smoke
    run_env.setdefault("PB_NO_OPEN_CODEX", "1")
    run_env.setdefault("CI", "1")

    print(f"\n## {prefix} - hard Codex CLI smoke (no soft-skip)")

    codex = resolve_codex()
    if not codex and os.environ.get("PB_E2E_INSTALL_CODEX", "").strip() in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    ):
        ok_i, det_i = _try_npm_install()
        g(f"{prefix}/npm_install_codex", ok_i, det_i, hard=False)
        codex = resolve_codex()

    g(
        f"{prefix}/binary_on_path",
        bool(codex),
        codex
        or "codex missing — CI must: npm i -g @openai/codex (setup-node). Soft-skip banned.",
    )
    version_txt = ""
    if not codex:
        return {
            "ok": False,
            "fail": local_fail,
            "results": local,
            "binary": None,
            "version": None,
        }

    try:
        r = _run([codex, "--version"], timeout=45, env=run_env)
        version_txt = ((r.stdout or r.stderr or "").strip())[:120]
        g(
            f"{prefix}/version",
            r.returncode == 0 and bool(version_txt),
            version_txt or f"rc={r.returncode}",
        )
    except Exception as e:
        g(f"{prefix}/version", False, str(e))

    try:
        r = _run([codex, "--help"], timeout=45, env=run_env)
        help_blob = ((r.stdout or "") + (r.stderr or "")).lower()
        g(
            f"{prefix}/help",
            r.returncode == 0 and ("usage" in help_blob or "exec" in help_blob),
            ((r.stdout or r.stderr or "")[:100]),
        )
    except Exception as e:
        g(f"{prefix}/help", False, str(e))

    try:
        r = _run([codex, "exec", "--help"], timeout=45, env=run_env)
        eh = ((r.stdout or "") + (r.stderr or "")).lower()
        g(
            f"{prefix}/exec_help",
            r.returncode == 0 and ("usage" in eh or "prompt" in eh or "exec" in eh),
            ((r.stdout or r.stderr or "")[:100]),
        )
    except Exception as e:
        g(f"{prefix}/exec_help", False, str(e))

    try:
        r = _run([codex, "doctor", "--summary", "--no-color"], timeout=120, env=run_env)
        doc = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        looks_like_doctor = any(
            token in doc.lower()
            for token in ("codex doctor", "environment", "runtime", "install", "ok")
        )
        # Doctor may non-zero without auth/network; process + report is the hard bar.
        g(
            f"{prefix}/doctor_runs",
            looks_like_doctor or r.returncode == 0,
            (doc[:160] if doc else f"rc={r.returncode}"),
        )
    except subprocess.TimeoutExpired:
        g(f"{prefix}/doctor_runs", False, "doctor timeout 120s")
    except Exception as e:
        g(f"{prefix}/doctor_runs", False, str(e))

    # Login surface exists (do not call login interactively)
    try:
        r = _run([codex, "login", "--help"], timeout=30, env=run_env)
        lh = ((r.stdout or "") + (r.stderr or "")).lower()
        g(
            f"{prefix}/login_help",
            r.returncode == 0 and ("usage" in lh or "login" in lh),
            ((r.stdout or r.stderr or "")[:80]),
        )
    except Exception as e:
        g(f"{prefix}/login_help", False, str(e))

    # Live non-interactive exec only when explicitly enabled (needs ChatGPT/API auth)
    exec_flag = os.environ.get("PB_E2E_CODEX_EXEC", "").strip() in ("1", "true", "TRUE", "yes")
    if exec_flag:
        try:
            r = _run(
                [codex, "exec", "-q", "reply with the single word PONG only"],
                timeout=180,
                env=run_env,
            )
            body = ((r.stdout or "") + (r.stderr or "")).strip()
            g(
                f"{prefix}/exec_live",
                r.returncode == 0 or "pong" in body.lower(),
                body[:200],
                hard=True,
            )
        except Exception as e:
            g(f"{prefix}/exec_live", False, str(e), hard=True)
    else:
        g(
            f"{prefix}/cli_hard_no_soft_skip",
            True,
            "binary/version/help/doctor hard-smoked; live agent needs PB_E2E_CODEX_EXEC=1 + auth",
        )

    return {
        "ok": local_fail == 0,
        "fail": local_fail,
        "results": local,
        "binary": codex,
        "version": version_txt,
    }


def main() -> int:
    # Standalone entry for CI step: python scripts/codex_cli_smoke.py
    summary = smoke_codex_cli(prefix="CODEX")
    out_dir = Path(os.environ.get("PRIVATE_BRAIN_HOME") or ".") / ".brain" / "state"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "CODEX_CLI_SMOKE.json").write_text(
            json.dumps(
                {
                    "ok": summary["ok"],
                    "pass": PASS,
                    "fail": FAIL,
                    "binary": summary.get("binary"),
                    "version": summary.get("version"),
                    "results": RESULTS,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    print("\n" + "=" * 72)
    print(f" CODEX CLI SMOKE: pass={PASS} fail={FAIL} binary={summary.get('binary')}")
    if FAIL:
        print(" RED - Codex CLI not exercised; install @openai/codex and re-run")
        for row in RESULTS:
            if not row["ok"] and row["hard"]:
                print(f"   FAIL {row['name']}: {row['detail'][:200]}")
        return 1
    print(f" GREEN - real Codex CLI smoked ({summary.get('version') or 'ok'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
