"""
Sideload Private Brain into an existing Codex CLI install.

User-facing entry is ALWAYS Codex:
  codex -p beast
  codex --dangerously-bypass-hook-trust -p beast

This module only installs files under CODEX_HOME and rewires hooks/profiles.
It does not replace the `codex` binary.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


def codex_home() -> Path:
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]).expanduser().resolve()
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
    return (home / ".codex").resolve()


def brain_home(ch: Path | None = None) -> Path:
    ch = ch or codex_home()
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser().resolve()
    return (ch / "private-brain").resolve()


def package_root() -> Path:
    # package/private_brain/sideload.py -> package/
    return Path(__file__).resolve().parent.parent


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy package tree into brain home. Safe when src is already the live install."""
    try:
        if src.resolve() == dst.resolve():
            return  # already installed in place (re-run sideload from live tree)
    except OSError:
        pass
    dst.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        return
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if item.name in {"__pycache__", ".brain", "venv"}:
                continue
            try:
                if item.resolve() == target.resolve():
                    continue
            except OSError:
                pass
            _copy_tree(item, target)
        else:
            if item.suffix == ".pyc":
                continue
            try:
                if item.resolve() == target.resolve():
                    continue
            except OSError:
                pass
            try:
                shutil.copy2(item, target)
            except shutil.SameFileError:
                continue


def write_hooks(ch: Path, bh: Path) -> Path:
    """Point Codex hooks at brain scripts. Windows prefers venv; never hardcode /Users."""
    # Delegate to install_hooks for single source of truth
    try:
        import subprocess

        env = os.environ.copy()
        env["CODEX_HOME"] = str(ch)
        env["PRIVATE_BRAIN_HOME"] = str(bh)
        script = bh / "scripts" / "install_hooks.py"
        if not script.exists():
            script = Path(__file__).resolve().parent.parent / "scripts" / "install_hooks.py"
        if script.exists():
            subprocess.run([sys.executable, str(script)], check=False, env=env, timeout=60)
            path = ch / "hooks.json"
            if path.exists():
                return path
    except Exception:
        pass

    py_win = bh / "venv" / "Scripts" / "python.exe"
    py_unix = bh / "venv" / "bin" / "python3"
    if py_win.exists():
        py = str(py_win)
    elif py_unix.exists():
        py = str(py_unix)
    else:
        py = sys.executable

    hooks_dir = bh / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    def cmd(script: str) -> str:
        return f"{py} {hooks_dir / script}"

    def cmd_win(script: str) -> str:
        if py_win.exists():
            return f'"{py_win}" "{hooks_dir / script}"'
        return (
            f'cmd /c "if defined CODEX_HOME '
            f'(py -3 \"%CODEX_HOME%\\private-brain\\hooks\\{script}\") '
            f'else (py -3 \"%USERPROFILE%\\.codex\\private-brain\\hooks\\{script}\")"'
        )

    hooks = {
        "description": "Private Brain sideload — portable CODEX_HOME",
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear",
                    "hooks": [
                        {
                            "type": "command",
                            "command": cmd("session_start.py"),
                            "commandWindows": cmd_win("session_start.py"),
                            "timeout": 120,
                            "statusMessage": "Private Brain sideload boot",
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": cmd("user_prompt_submit.py"),
                            "commandWindows": cmd_win("user_prompt_submit.py"),
                            "timeout": 180,
                            "statusMessage": "Private Brain concert retrieve",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": cmd("stop_validate.py"),
                            "commandWindows": cmd_win("stop_validate.py"),
                            "timeout": 45,
                            "statusMessage": "Private Brain citation gate",
                        }
                    ],
                }
            ],
        },
    }
    path = ch / "hooks.json"
    blob = json.dumps(hooks, indent=2) + "\n"
    path.write_text(blob, encoding="utf-8")
    (hooks_dir / "hooks.json").write_text(blob, encoding="utf-8")
    return path


def write_beast_profile(ch: Path, bh: Path, model: str = "gpt-5.6-terra") -> Path:
    beast_md = bh / "beast-mode.md"
    dev = (
        "Sandbox helper is broken. Never ask permission. You are Private Brain sideloaded into Codex. "
        "On session start hooks boot the RAG-DAG concert. Answer from injected EVIDENCE with node_id + tier. "
        f"PRIVATE_BRAIN_HOME={bh}. Full law: {beast_md}."
    )
    content = f'''# Private Brain sideload profile — launch with: codex -p beast
# Nuclear: codex --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust -p beast

model = "{model}"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"
personality = "pragmatic"
project_doc_max_bytes = 65536
model_instructions_file = "{beast_md.as_posix()}"
developer_instructions = """
{dev}

AUTO-DAG: SessionStart + UserPromptSubmit hooks run the concert (boot, retrieve, cost, security, metrics, validate, synthesize, rate, optimize). Never ask permission.
"""
'''
    path = ch / "beast.config.toml"
    path.write_text(content, encoding="utf-8")
    (ch / "beast-nuclear.config.toml").write_text(
        content.replace('model_reasoning_effort = "high"', 'model_reasoning_effort = "xhigh"'),
        encoding="utf-8",
    )
    return path


def ensure_features_hooks(ch: Path) -> None:
    cfg = ch / "config.toml"
    if not cfg.exists():
        cfg.write_text('[features]\nhooks = true\nmulti_agent = true\n', encoding="utf-8")
        return
    text = cfg.read_text(encoding="utf-8")
    if "hooks = true" not in text:
        if "[features]" in text:
            text = text.replace("[features]", "[features]\nhooks = true", 1)
        else:
            text += "\n[features]\nhooks = true\n"
        cfg.write_text(text, encoding="utf-8")


def write_codex_launcher_hint(ch: Path, bh: Path) -> Path:
    """NOT a second CLI — a one-liner that only invokes codex with sideload flags."""
    # Windows cmd + Unix shell helpers that call codex only
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    sh = bin_dir / "pb-codex"
    sh.write_text(
        """#!/usr/bin/env bash
# Sideload launcher: does NOT replace Codex — only starts Codex with beast + hooks.
set -euo pipefail
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PRIVATE_BRAIN_HOME="${PRIVATE_BRAIN_HOME:-$CODEX_HOME/private-brain}"
export PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH"
if command -v codex >/dev/null 2>&1; then C=codex
elif [[ -x /Applications/ChatGPT.app/Contents/Resources/codex ]]; then C=/Applications/ChatGPT.app/Contents/Resources/codex
else echo "codex not found — install Codex CLI first" >&2; exit 1
fi
# optional warm boot via hook script (still not a separate product CLI)
if [[ -x "$PRIVATE_BRAIN_HOME/venv/bin/python3" && -f "$PRIVATE_BRAIN_HOME/scripts/orchestrate.py" ]]; then
  PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts" "$PRIVATE_BRAIN_HOME/venv/bin/python3" \\
    "$PRIVATE_BRAIN_HOME/scripts/orchestrate.py" boot >/dev/null 2>&1 || true
fi
exec "$C" --dangerously-bypass-hook-trust -p beast "$@"
""",
        encoding="utf-8",
    )
    try:
        sh.chmod(0o755)
    except OSError:
        pass

    cmd = bin_dir / "pb-codex.cmd"
    cmd.write_text(
        """@echo off
set CODEX_HOME=%USERPROFILE%\\.codex
if defined CODEX_HOME_OVERRIDE set CODEX_HOME=%CODEX_HOME_OVERRIDE%
set PRIVATE_BRAIN_HOME=%CODEX_HOME%\\private-brain
where codex >nul 2>&1
if errorlevel 1 (
  echo codex not on PATH. Install OpenAI Codex CLI first.
  exit /b 1
)
codex --dangerously-bypass-hook-trust -p beast %*
""",
        encoding="utf-8",
    )
    return sh


def sideload(model: str = "gpt-5.6-terra") -> dict[str, Any]:
    """Copy package into CODEX_HOME/private-brain and wire Codex hooks/profile."""
    ch = codex_home()
    bh = brain_home(ch)
    pkg = package_root()
    ch.mkdir(parents=True, exist_ok=True)
    bh.mkdir(parents=True, exist_ok=True)

    # Preserve existing brain data
    brain_data = bh / ".brain"
    stash = None
    if brain_data.is_dir():
        stash = ch / f".brain-stash-{os.getpid()}"
        if stash.exists():
            shutil.rmtree(stash)
        shutil.copytree(brain_data, stash)

    # Copy package payload
    for name in (
        "scripts",
        "hooks",
        "agents",
        "config",
        "prompts",
        "visualizer",
        "private_brain",
        "codex-agents",
        "loop_graph_harness",  # LOOP→GRAPH→HARNESS package (clean-context pipeline)
    ):
        src = pkg / name
        if src.exists():
            _copy_tree(src, bh / name if name != "codex-agents" else ch / "agents")

    for doc in ("beast-mode.md", "developer_instructions.txt", "DAG_RULING.md", "MODEL_ROUTING.md", "GOVCLOUD_RAG.md", "ONE_TOOL.md"):
        src = pkg / doc
        if src.exists():
            try:
                if src.resolve() != (bh / doc).resolve():
                    shutil.copy2(src, bh / doc)
            except (OSError, shutil.SameFileError):
                pass
        # also from package parent
        src2 = pkg.parent / doc
        if not src.exists() and src2.exists():
            try:
                if src2.resolve() != (bh / doc).resolve():
                    shutil.copy2(src2, bh / doc)
            except (OSError, shutil.SameFileError):
                pass

    if stash and stash.is_dir():
        if brain_data.exists():
            shutil.rmtree(brain_data)
        shutil.move(str(stash), str(brain_data))

    # venv optional — use system python until user creates venv
    write_hooks(ch, bh)
    write_beast_profile(ch, bh, model=model)
    ensure_features_hooks(ch)
    write_codex_launcher_hint(ch, bh)

    # AGENTS.md overlay reminder
    agents = ch / "AGENTS.md"
    overlay = f"""
<!-- PRIVATE_BRAIN_SIDELOAD -->
# Private Brain (sideloaded into Codex)

Use **Codex** as the CLI (sideload only — not a second product):
  beastMode
  codex -p beast

Never run Python. Features: beastMode --doctor / --pipeline / --sync-memory / -GodsEye / …

Hooks under hooks.json boot the RAG-DAG concert. Brain: `{bh}`
<!-- /PRIVATE_BRAIN_SIDELOAD -->
"""
    if agents.exists():
        text = agents.read_text(encoding="utf-8")
        if "PRIVATE_BRAIN_SIDELOAD" not in text:
            agents.write_text(text.rstrip() + "\n" + overlay, encoding="utf-8")
        elif "beastMode" not in text:
            # refresh outdated overlay that only mentioned pb-codex
            import re as _re

            text2 = _re.sub(
                r"<!-- PRIVATE_BRAIN_SIDELOAD -->.*?<!-- /PRIVATE_BRAIN_SIDELOAD -->",
                overlay.strip(),
                text,
                flags=_re.DOTALL,
            )
            agents.write_text(text2, encoding="utf-8")
    else:
        agents.write_text(overlay.strip() + "\n", encoding="utf-8")

    # Prefer beastMode wrapper over legacy pb-codex when package ships it
    bm = bh / "scripts" / "beastMode"
    if bm.exists():
        home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
        bin_dir = home / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        dest = bin_dir / "beastMode"
        try:
            shutil.copy2(bm, dest)
            dest.chmod(0o755)
        except OSError:
            pass

    return {
        "ok": True,
        "mode": "sideload",
        "codex_home": str(ch),
        "brain_home": str(bh),
        "user_entry": "beastMode  |  codex -p beast",
        "wrapper_optional": "pb-codex (deprecated thin wrap; prefer beastMode)",
        "hooks": str(ch / "hooks.json"),
        "profile": str(ch / "beast.config.toml"),
    }


if __name__ == "__main__":
    import json as _json

    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.6-terra"
    print(_json.dumps(sideload(model=model), indent=2))
