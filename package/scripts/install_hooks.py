#!/usr/bin/env python3
"""Install Codex SessionStart/UserPromptSubmit/Stop hooks for Private Brain.

Windows first-boot law (developer handoff 2026-07-28):
  - Permanent .cmd wrappers for all three hooks (command AND commandWindows).
  - Never emit multiline direct Python/script commands in hooks.json.
  - Prefer venv python under PRIVATE_BRAIN_HOME / CODEX_HOME.
  - Schema-aware health check targets CODEX_HOME/hooks.json (not only brain copy).
  - Do not place managed top-level keys inside TOML tables (hooks=true under [features] only).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def _resolve_python(brain: Path) -> Path:
    win = brain / "venv" / "Scripts" / "python.exe"
    unix = brain / "venv" / "bin" / "python3"
    if win.exists():
        return win
    if unix.exists():
        return unix
    return Path(sys.executable)


def _write_cmd_wrappers(brain: Path) -> dict[str, Path]:
    """Permanent Windows .cmd wrappers — single responsibility launchers."""
    hooks_dir = brain / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "pb-session-start.cmd": "session_start.py",
        "pb-user-prompt-submit.cmd": "user_prompt_submit.py",
        "pb-stop-validate.cmd": "stop_validate.py",
    }
    written: dict[str, Path] = {}
    for cmd_name, py_script in mapping.items():
        path = hooks_dir / cmd_name
        # Robust: prefer PRIVATE_BRAIN_HOME, then CODEX_HOME\private-brain, then USERPROFILE.
        # Prefer venv python when present; else py -3 / python.
        body = f"""@echo off
setlocal EnableExtensions
set "PB=%PRIVATE_BRAIN_HOME%"
if not defined PB if defined CODEX_HOME set "PB=%CODEX_HOME%\\private-brain"
if not defined PB set "PB=%USERPROFILE%\\.codex\\private-brain"
set "PY=%PB%\\venv\\Scripts\\python.exe"
if not exist "%PY%" set "PY=%PB%\\venv\\Scripts\\python"
if not exist "%PY%" (
  where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
)
set "HOOK=%PB%\\hooks\\{py_script}"
if not exist "%HOOK%" set "HOOK=%~dp0{py_script}"
%PY% "%HOOK%"
exit /b %ERRORLEVEL%
"""
        path.write_text(body, encoding="utf-8", newline="\r\n")
        written[cmd_name] = path
    return written


def _cmd_unix_wrapper(brain: Path, py_script: str, py: Path) -> str:
    """Unix/mac: direct venv python + script (stable single-line)."""
    return f"{py} {brain / 'hooks' / py_script}"


def _cmd_windows_wrapper(brain: Path, cmd_name: str) -> str:
    """Windows: always invoke permanent .cmd wrapper (no multiline python)."""
    # Absolute path when known; also allow env expansion for portable installs.
    wrapper = brain / "hooks" / cmd_name
    if wrapper.exists():
        # Quote absolute path — Codex launches via CreateProcess / cmd
        return f'cmd /c ""{wrapper}""'
    # Fallback portable
    return (
        'cmd /c "if defined PRIVATE_BRAIN_HOME '
        f'("%PRIVATE_BRAIN_HOME%\\hooks\\{cmd_name}") '
        f'else if defined CODEX_HOME ("%CODEX_HOME%\\private-brain\\hooks\\{cmd_name}") '
        f'else ("%USERPROFILE%\\.codex\\private-brain\\hooks\\{cmd_name}")"'
    )


def health_check(codex: Path, brain: Path) -> dict:
    """Schema-aware hook health using CODEX_HOME/hooks.json (authoritative)."""
    report: dict = {
        "ok": False,
        "codex_hooks_json": str(codex / "hooks.json"),
        "wrappers": {},
        "errors": [],
    }
    hj = codex / "hooks.json"
    if not hj.is_file():
        report["errors"].append("CODEX_HOME/hooks.json missing")
        return report
    try:
        data = json.loads(hj.read_text(encoding="utf-8"))
    except Exception as e:
        report["errors"].append(f"hooks.json parse: {e}")
        return report
    hooks = (data.get("hooks") or {}) if isinstance(data, dict) else {}
    expected = {
        "SessionStart": "pb-session-start.cmd",
        "UserPromptSubmit": "pb-user-prompt-submit.cmd",
        "Stop": "pb-stop-validate.cmd",
    }
    for event, wrapper in expected.items():
        entries = hooks.get(event) or []
        cmd_w = ""
        cmd_u = ""
        try:
            h0 = (entries[0].get("hooks") or [{}])[0]
            cmd_w = str(h0.get("commandWindows") or "")
            cmd_u = str(h0.get("command") or "")
        except Exception:
            report["errors"].append(f"{event}: malformed")
            continue
        wp = brain / "hooks" / wrapper
        ok_wrap = wp.is_file()
        # Windows side must reference wrapper, not raw multiline python
        uses_wrapper = wrapper in cmd_w or wrapper.replace("\\", "/") in cmd_w.replace("\\", "/")
        multiline_bad = "\n" in cmd_w or (cmd_w.count("python") > 0 and ".cmd" not in cmd_w.lower())
        report["wrappers"][event] = {
            "wrapper_file": str(wp),
            "wrapper_exists": ok_wrap,
            "commandWindows_uses_wrapper": uses_wrapper,
            "commandWindows_multiline": "\n" in cmd_w,
            "command_set": bool(cmd_u),
        }
        if not ok_wrap:
            report["errors"].append(f"{wrapper} missing")
        if not uses_wrapper and sys.platform.startswith("win"):
            report["errors"].append(f"{event} commandWindows does not use {wrapper}")
        if multiline_bad and sys.platform.startswith("win"):
            report["errors"].append(f"{event} commandWindows looks like direct python")
    report["ok"] = not report["errors"]
    return report


def main() -> int:
    codex = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    brain = Path(os.environ.get("PRIVATE_BRAIN_HOME", codex / "private-brain")).expanduser()
    pkg_hooks = Path(__file__).resolve().parent.parent / "hooks"
    if not pkg_hooks.is_dir():
        pkg_hooks = brain / "hooks"

    dest = brain / "hooks"
    dest.mkdir(parents=True, exist_ok=True)
    if pkg_hooks.resolve() != dest.resolve():
        for f in pkg_hooks.glob("*.py"):
            target = dest / f.name
            try:
                if f.resolve() == target.resolve():
                    continue
            except OSError:
                pass
            shutil.copy2(f, target)

    py = _resolve_python(brain)
    wrappers = _write_cmd_wrappers(brain)

    hooks = {
        "description": "Private Brain sideload — permanent .cmd wrappers (portable CODEX_HOME)",
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd_unix_wrapper(brain, "session_start.py", py),
                            "commandWindows": _cmd_windows_wrapper(brain, "pb-session-start.cmd"),
                            "timeout": 120,
                            "statusMessage": "Private Brain RAG-DAG boot",
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd_unix_wrapper(brain, "user_prompt_submit.py", py),
                            "commandWindows": _cmd_windows_wrapper(
                                brain, "pb-user-prompt-submit.cmd"
                            ),
                            "timeout": 180,
                            "statusMessage": "Private Brain retrieve DAG",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": _cmd_unix_wrapper(brain, "stop_validate.py", py),
                            "commandWindows": _cmd_windows_wrapper(brain, "pb-stop-validate.cmd"),
                            "timeout": 45,
                            "statusMessage": "Private Brain answer validator",
                        }
                    ],
                }
            ],
        },
    }
    payload = json.dumps(hooks, indent=2) + "\n"
    json.loads(payload)
    # Refuse Mac absolute paths in Windows command
    for event in ("SessionStart", "UserPromptSubmit", "Stop"):
        cw = hooks["hooks"][event][0]["hooks"][0].get("commandWindows", "")
        if "/Users/" in cw:
            raise SystemExit("refusing to write Mac absolute path into commandWindows")
        if "\n" in cw:
            raise SystemExit("refusing multiline commandWindows")

    (codex / "hooks.json").write_text(payload, encoding="utf-8")
    (dest / "hooks.json").write_text(payload, encoding="utf-8")

    # features.hooks = true only under [features] table — never top-level managed keys after tables
    cfg = codex / "config.toml"
    if cfg.exists():
        t = cfg.read_text(encoding="utf-8")
        if "hooks = true" not in t and "hooks=true" not in t.replace(" ", ""):
            if "[features]" in t:
                t = t.replace("[features]", "[features]\nhooks = true", 1)
            else:
                # Append table at end only for this boolean feature key
                t = t.rstrip() + "\n\n[features]\nhooks = true\n"
            cfg.write_text(t, encoding="utf-8")
    else:
        cfg.write_text("[features]\nhooks = true\n", encoding="utf-8")

    hc = health_check(codex, brain)
    print(f"hooks installed -> {codex / 'hooks.json'}")
    print(f"python: {py}")
    print(f"wrappers: {', '.join(sorted(wrappers.keys()))}")
    print(f"health_ok: {hc.get('ok')} errors={hc.get('errors')}")
    return 0 if hc.get("ok") or not sys.platform.startswith("win") else 0


if __name__ == "__main__":
    raise SystemExit(main())
