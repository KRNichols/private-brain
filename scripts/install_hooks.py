#!/usr/bin/env python3
"""Install Codex SessionStart/UserPromptSubmit/Stop hooks for Private Brain.

Windows first-boot law:
  Prefer venv\\Scripts\\python.exe under PRIVATE_BRAIN_HOME / CODEX_HOME.
  Never hardcode /Users/... or only %USERPROFILE%\\.codex without CODEX_HOME.
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


def _win_command(brain: Path, script: str) -> str:
    """Portable Windows hook line — expands CODEX_HOME/PRIVATE_BRAIN_HOME at runtime via cmd."""
    # Prefer venv if present at install time (absolute path). Fallback: py -3 + env expansion.
    venv_py = brain / "venv" / "Scripts" / "python.exe"
    hook = brain / "hooks" / script
    if venv_py.exists():
        # Absolute paths in JSON — Codex on Windows accepts them
        return f'"{venv_py}" "{hook}"'
    # Runtime expansion: CODEX_HOME first, then USERPROFILE\.codex
    return (
        'cmd /c "if defined PRIVATE_BRAIN_HOME '
        f'(if exist \\"%PRIVATE_BRAIN_HOME%\\venv\\Scripts\\python.exe\\" '
        f'("%PRIVATE_BRAIN_HOME%\\venv\\Scripts\\python.exe" "%PRIVATE_BRAIN_HOME%\\hooks\\{script}") '
        f'else if exist \\"%PRIVATE_BRAIN_HOME%\\hooks\\{script}\\" '
        f'(py -3 "%PRIVATE_BRAIN_HOME%\\hooks\\{script}") else (py -3 "%USERPROFILE%\\.codex\\private-brain\\hooks\\{script}")) '
        f'else if defined CODEX_HOME '
        f'(if exist \\"%CODEX_HOME%\\private-brain\\venv\\Scripts\\python.exe\\" '
        f'("%CODEX_HOME%\\private-brain\\venv\\Scripts\\python.exe" "%CODEX_HOME%\\private-brain\\hooks\\{script}") '
        f'else (py -3 "%CODEX_HOME%\\private-brain\\hooks\\{script}")) '
        f'else (if exist \\"%USERPROFILE%\\.codex\\private-brain\\venv\\Scripts\\python.exe\\" '
        f'("%USERPROFILE%\\.codex\\private-brain\\venv\\Scripts\\python.exe" "%USERPROFILE%\\.codex\\private-brain\\hooks\\{script}") '
        f'else (py -3 "%USERPROFILE%\\.codex\\private-brain\\hooks\\{script}"))"'
    )


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

    def cmd_unix(script: str) -> str:
        return f"{py} {dest / script}"

    hooks = {
        "description": "Private Brain sideload — Codex owns CLI; hooks run RAG-DAG (portable CODEX_HOME)",
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear",
                    "hooks": [
                        {
                            "type": "command",
                            "command": cmd_unix("session_start.py"),
                            "commandWindows": _win_command(brain, "session_start.py"),
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
                            "command": cmd_unix("user_prompt_submit.py"),
                            "commandWindows": _win_command(brain, "user_prompt_submit.py"),
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
                            "command": cmd_unix("stop_validate.py"),
                            "commandWindows": _win_command(brain, "stop_validate.py"),
                            "timeout": 45,
                            "statusMessage": "Private Brain answer validator",
                        }
                    ],
                }
            ],
        },
    }
    payload = json.dumps(hooks, indent=2) + "\n"
    # Fail closed: must be valid JSON and never ship Mac home paths into Windows command
    json.loads(payload)
    if "/Users/" in hooks["hooks"]["SessionStart"][0]["hooks"][0].get("commandWindows", ""):
        raise SystemExit("refusing to write Mac absolute path into commandWindows")

    (codex / "hooks.json").write_text(payload, encoding="utf-8")
    (dest / "hooks.json").write_text(payload, encoding="utf-8")

    cfg = codex / "config.toml"
    if cfg.exists():
        t = cfg.read_text(encoding="utf-8")
        if "hooks = true" not in t:
            if "[features]" in t:
                t = t.replace("[features]", "[features]\nhooks = true", 1)
            else:
                t += "\n[features]\nhooks = true\n"
            cfg.write_text(t, encoding="utf-8")
    else:
        cfg.write_text("[features]\nhooks = true\n", encoding="utf-8")

    print(f"hooks installed → {codex / 'hooks.json'}")
    print(f"python: {py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
