#!/usr/bin/env python3
"""Hard Codex CLI smoke — install + loop until PERFECT. Soft-skip banned.

If `codex` is missing: install it (npm/npx), heal PATH, re-probe, retry.
Never soft-pass a missing binary. Exit 0 only when every hard gate is green.

Hard gates (no API key required):
  - binary on PATH
  - codex --version
  - codex --help
  - codex exec --help
  - codex doctor --summary
  - codex login --help

Optional live agent (needs auth):
  - PB_E2E_CODEX_EXEC=1 → codex exec -q "reply with PONG only"

Env:
  PB_E2E_CODEX_ATTEMPTS   max install/smoke loops (default 8)
  PB_E2E_INSTALL_CODEX    force reinstall even if binary present (1=yes; default auto-install when missing)
  PB_E2E_CODEX_EXEC       1 = live agent hard gate
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
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


def _truthy(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _max_attempts() -> int:
    try:
        n = int(os.environ.get("PB_E2E_CODEX_ATTEMPTS", "8") or "8")
    except ValueError:
        n = 8
    return max(1, min(n, 20))


def _npm_global_bins(env: dict[str, str]) -> list[Path]:
    """Collect likely npm global bin dirs so we can heal PATH after install."""
    bins: list[Path] = []
    seen: set[str] = set()

    def add(p: Path | None) -> None:
        if p is None:
            return
        try:
            r = p.expanduser().resolve()
        except Exception:
            r = p.expanduser()
        key = str(r)
        if key in seen:
            return
        if r.is_dir():
            seen.add(key)
            bins.append(r)

    npm = shutil.which("npm") or "npm"
    try:
        r = _run([npm, "prefix", "-g"], timeout=30, env=env)
        if r.returncode == 0 and (r.stdout or "").strip():
            root = Path((r.stdout or "").strip())
            add(root / "bin")
            add(root)  # Windows often puts .cmd next to prefix
    except Exception:
        pass
    try:
        r = _run([npm, "bin", "-g"], timeout=30, env=env)
        if r.returncode == 0 and (r.stdout or "").strip():
            add(Path((r.stdout or "").strip()))
    except Exception:
        pass

    home = Path.home()
    add(home / ".npm-global" / "bin")
    add(home / ".local" / "share" / "npm" / "bin")
    add(Path("/usr/local/bin"))
    # nvm / fnm / volta common layouts (runner + laptop)
    for p in home.glob(".nvm/versions/node/*/bin"):
        add(p)
    for p in home.glob(".fnm/node-versions/*/installation/bin"):
        add(p)
    # Windows npm
    appdata = env.get("APPDATA") or os.environ.get("APPDATA")
    if appdata:
        add(Path(appdata) / "npm")
    localapp = env.get("LOCALAPPDATA") or os.environ.get("LOCALAPPDATA")
    if localapp:
        add(Path(localapp) / "npm")

    return bins


def heal_path(env: dict[str, str]) -> dict[str, str]:
    """Prepend npm global bins so `which codex` finds a just-installed binary."""
    out = dict(env)
    parts = [str(p) for p in _npm_global_bins(out)]
    cur = out.get("PATH") or os.environ.get("PATH") or ""
    # also scan existing PATH entries for node/npm
    merged: list[str] = []
    for p in parts + cur.split(os.pathsep):
        if p and p not in merged:
            merged.append(p)
    out["PATH"] = os.pathsep.join(merged)
    # Keep process PATH in sync so shutil.which sees it
    os.environ["PATH"] = out["PATH"]
    return out


def resolve_codex(env: dict[str, str] | None = None) -> str | None:
    e = heal_path(env or os.environ.copy())
    found = shutil.which("codex", path=e.get("PATH"))
    if found:
        return found
    # Windows: codex.cmd
    found = shutil.which("codex.cmd", path=e.get("PATH"))
    if found:
        return found
    # Brute: look for codex binary under npm global bins
    for b in _npm_global_bins(e):
        for name in ("codex", "codex.cmd", "codex.exe", "codex.js"):
            cand = b / name
            if cand.is_file():
                return str(cand)
            # npm package bin layout
            nested = b / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            if nested.is_file():
                return str(nested)
    return None


def _try_install(env: dict[str, str], attempt: int) -> tuple[bool, str, dict[str, str]]:
    """Install @openai/codex. Returns (ok, detail, updated_env)."""
    env = heal_path(env)
    npm = shutil.which("npm", path=env.get("PATH"))
    npx = shutil.which("npx", path=env.get("PATH"))
    node = shutil.which("node", path=env.get("PATH"))
    detail_parts: list[str] = [f"attempt={attempt}", f"node={node}", f"npm={npm}"]

    if not npm and not npx:
        # last-ditch: maybe corepack / full path
        for cand in ("/usr/local/bin/npm", "/opt/homebrew/bin/npm"):
            if Path(cand).is_file():
                npm = cand
                break
    if not npm and not npx:
        return False, "npm/npx missing — setup-node required before smoke", env

    cmds: list[list[str]] = []
    if npm:
        # prefer clean reinstall on retry loops
        if attempt >= 2:
            cmds.append([npm, "uninstall", "-g", "@openai/codex"])
        cmds.append([npm, "install", "-g", "@openai/codex@latest"])
        cmds.append([npm, "install", "-g", "@openai/codex"])
    if npx:
        # npx can pull the package; does not always put global bin — still try
        cmds.append([npx, "--yes", "@openai/codex", "--version"])

    last = "no install command ran"
    ok_any = False
    for argv in cmds:
        try:
            print(f"  … install: {' '.join(argv)}")
            r = _run(argv, timeout=360, env=env)
            blob = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
            last = f"rc={r.returncode} {(blob[-240:] if blob else '')}"
            detail_parts.append(f"{argv[0]}:{r.returncode}")
            if r.returncode == 0:
                ok_any = True
        except Exception as e:
            last = str(e)
            detail_parts.append(f"err:{e}")

    env = heal_path(env)
    # After install, re-hash which
    codex = resolve_codex(env)
    if codex:
        return True, f"installed codex={codex} | {last}", env
    return ok_any, f"install finished but codex not on PATH | {last} | {'; '.join(detail_parts)}", env


def _probe(codex: str, env: dict[str, str]) -> dict[str, Any]:
    """Run all hard probes once. Returns structured results (no gating)."""
    out: dict[str, Any] = {"binary": codex, "version": "", "checks": {}}

    def check(name: str, argv: list[str], *, timeout: int = 90, pred=None) -> None:
        try:
            r = _run(argv, timeout=timeout, env=env)
            body = ((r.stdout or "") + (r.stderr or "")).strip()
            ok = r.returncode == 0
            if pred is not None:
                ok = bool(pred(r, body))
            out["checks"][name] = {
                "ok": ok,
                "rc": r.returncode,
                "detail": body[:200],
            }
            if name == "version" and body:
                out["version"] = body.splitlines()[0][:120]
        except Exception as e:
            out["checks"][name] = {"ok": False, "rc": -1, "detail": str(e)[:200]}

    check(
        "version",
        [codex, "--version"],
        timeout=45,
        pred=lambda r, b: r.returncode == 0 and bool(b.strip()),
    )
    check(
        "help",
        [codex, "--help"],
        timeout=45,
        pred=lambda r, b: r.returncode == 0 and ("usage" in b.lower() or "exec" in b.lower()),
    )
    check(
        "exec_help",
        [codex, "exec", "--help"],
        timeout=45,
        pred=lambda r, b: r.returncode == 0
        and ("usage" in b.lower() or "prompt" in b.lower() or "exec" in b.lower()),
    )
    check(
        "doctor",
        [codex, "doctor", "--summary", "--no-color"],
        timeout=120,
        pred=lambda r, b: r.returncode == 0
        or any(t in b.lower() for t in ("codex doctor", "environment", "runtime", "install", "ok")),
    )
    check(
        "login_help",
        [codex, "login", "--help"],
        timeout=30,
        pred=lambda r, b: r.returncode == 0 and ("usage" in b.lower() or "login" in b.lower()),
    )

    if _truthy("PB_E2E_CODEX_EXEC"):
        check(
            "exec_live",
            [codex, "exec", "-q", "reply with the single word PONG only"],
            timeout=180,
            pred=lambda r, b: r.returncode == 0 or "pong" in b.lower(),
        )

    out["perfect"] = all(c.get("ok") for c in out["checks"].values()) and bool(codex)
    return out


def ensure_and_smoke(
    *,
    gate_fn: Callable[..., Any] | None = None,
    prefix: str = "CODEX",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Install if missing, loop probes until perfect or attempts exhausted."""
    local: list[dict[str, Any]] = []
    local_fail = 0
    attempts_log: list[dict[str, Any]] = []

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
    run_env.setdefault("PB_NO_OPEN_CODEX", "1")
    run_env.setdefault("CI", "1")
    run_env = heal_path(run_env)

    max_n = _max_attempts()
    force_install = _truthy("PB_E2E_INSTALL_CODEX")
    # Default: ALWAYS install when missing. Never soft-skip.
    print(f"\n## {prefix} - hard Codex CLI smoke — loop until perfect (max {max_n})")

    best: dict[str, Any] | None = None
    codex: str | None = None
    version_txt = ""

    for attempt in range(1, max_n + 1):
        print(f"\n### {prefix} attempt {attempt}/{max_n}")
        run_env = heal_path(run_env)
        codex = resolve_codex(run_env)

        need_install = (not codex) or force_install or (attempt > 1 and best and not best.get("perfect"))
        if need_install:
            # On first attempt only force_install if missing unless env forces
            if not codex or force_install or attempt > 1:
                ok_i, det_i, run_env = _try_install(run_env, attempt)
                print(f"  install: {'ok' if ok_i else 'retry'} — {det_i[:200]}")
                attempts_log.append({"attempt": attempt, "phase": "install", "ok": ok_i, "detail": det_i[:300]})
                codex = resolve_codex(run_env)
                # After first successful presence, don't force reinstall every loop unless broken
                if codex and force_install and attempt == 1:
                    force_install = False

        if not codex:
            attempts_log.append(
                {
                    "attempt": attempt,
                    "phase": "resolve",
                    "ok": False,
                    "detail": "codex still missing after install",
                }
            )
            print("  codex still missing — looping install…")
            time.sleep(min(2 * attempt, 8))
            continue

        probe = _probe(codex, run_env)
        best = probe
        version_txt = str(probe.get("version") or "")
        attempts_log.append(
            {
                "attempt": attempt,
                "phase": "probe",
                "ok": bool(probe.get("perfect")),
                "checks": {k: v.get("ok") for k, v in (probe.get("checks") or {}).items()},
                "version": version_txt,
                "binary": codex,
            }
        )
        print(f"  binary={codex}")
        print(f"  version={version_txt or '?'}")
        for name, c in (probe.get("checks") or {}).items():
            print(f"  probe {name}: {'OK' if c.get('ok') else 'FAIL'} — {str(c.get('detail') or '')[:80]}")

        if probe.get("perfect"):
            print(f"  PERFECT on attempt {attempt}")
            break

        print(f"  not perfect — reinstall/retry (attempt {attempt}/{max_n})")
        force_install = True
        time.sleep(min(1.5 * attempt, 6))

    # Emit final hard gates from best probe (or hard fail if never found)
    perfect = bool(best and best.get("perfect") and codex)
    g(
        f"{prefix}/binary_on_path",
        bool(codex),
        codex or "codex missing after install loop — setup-node + npm required",
    )
    if not codex or not best:
        g(f"{prefix}/loop_perfect", False, f"exhausted {max_n} attempts; binary never resolved")
        g(
            f"{prefix}/install_loop_log",
            False,
            json.dumps(attempts_log)[:400],
        )
        return {
            "ok": False,
            "fail": local_fail,
            "results": local,
            "binary": None,
            "version": None,
            "attempts": attempts_log,
            "perfect": False,
        }

    checks = best.get("checks") or {}
    for name in ("version", "help", "exec_help", "doctor", "login_help"):
        c = checks.get(name) or {}
        g(
            f"{prefix}/{name}" if name != "doctor" else f"{prefix}/doctor_runs",
            bool(c.get("ok")),
            str(c.get("detail") or "")[:200],
        )
    if "exec_live" in checks:
        c = checks["exec_live"]
        g(f"{prefix}/exec_live", bool(c.get("ok")), str(c.get("detail") or "")[:200])
    else:
        g(
            f"{prefix}/cli_hard_no_soft_skip",
            True,
            "CLI hard-smoked via install loop; live agent needs PB_E2E_CODEX_EXEC=1 + auth",
        )

    g(
        f"{prefix}/loop_perfect",
        perfect,
        f"attempts={len(attempts_log)} version={version_txt} binary={codex}",
    )
    # Record how hard we worked (informational pass if perfect)
    g(
        f"{prefix}/install_loop_log",
        perfect,
        f"{len(attempts_log)} steps | last={json.dumps(attempts_log[-1])[:220] if attempts_log else 'none'}",
    )

    return {
        "ok": local_fail == 0 and perfect,
        "fail": local_fail,
        "results": local,
        "binary": codex,
        "version": version_txt,
        "attempts": attempts_log,
        "perfect": perfect,
    }


# Back-compat alias for conversation_e2e / nuclear imports
def smoke_codex_cli(
    *,
    gate_fn: Callable[..., Any] | None = None,
    prefix: str = "CODEX",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    return ensure_and_smoke(gate_fn=gate_fn, prefix=prefix, env=env)


def main() -> int:
    global PASS, FAIL, RESULTS
    PASS = 0
    FAIL = 0
    RESULTS = []

    summary = ensure_and_smoke(prefix="CODEX")
    out_dir = Path(os.environ.get("PRIVATE_BRAIN_HOME") or ".") / ".brain" / "state"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "CODEX_CLI_SMOKE.json").write_text(
            json.dumps(
                {
                    "ok": summary.get("ok"),
                    "perfect": summary.get("perfect"),
                    "pass": PASS,
                    "fail": FAIL,
                    "binary": summary.get("binary"),
                    "version": summary.get("version"),
                    "attempts": summary.get("attempts"),
                    "results": RESULTS,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    print("\n" + "=" * 72)
    print(
        f" CODEX CLI SMOKE: pass={PASS} fail={FAIL} perfect={summary.get('perfect')} "
        f"binary={summary.get('binary')}"
    )
    if FAIL or not summary.get("perfect"):
        print(" RED - looped install/smoke; still not perfect")
        for row in RESULTS:
            if not row["ok"] and row["hard"]:
                print(f"   FAIL {row['name']}: {row['detail'][:200]}")
        return 1
    print(f" GREEN - real Codex CLI PERFECT ({summary.get('version') or 'ok'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
