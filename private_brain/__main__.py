"""
NOT a product CLI.

This module only supports sideload/maintenance helpers. End users run Codex:

  codex -p beast
  codex --dangerously-bypass-hook-trust -p beast

Usage for installers / CI only:
  python -m private_brain sideload
  python -m private_brain doctor
  python -m private_brain uninstall [--dry-run] [--purge-brain] [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _help() -> None:
    print(
        """Private Brain is a Codex sideload (not a separate CLI).

End user:
  codex -p beast
  codex --dangerously-bypass-hook-trust -p beast

Maintainer helpers only:
  python -m private_brain sideload [model]
  python -m private_brain doctor
  python -m private_brain uninstall [--dry-run] [--purge-brain] [--json] [--codex-home PATH]
"""
    )


def _resolve_uninstall_module():
    """Load uninstall_private_brain from package scripts or installed brain home."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "scripts",  # package/scripts (source tree)
    ]
    try:
        from .paths import brain_home

        candidates.append(brain_home() / "scripts")
    except Exception:
        pass
    # Also CODEX_HOME/private-brain/scripts
    codex = Path(
        __import__("os").environ.get("CODEX_HOME")
        or (Path.home() / ".codex")
    ).expanduser()
    candidates.append(codex / "private-brain" / "scripts")

    for scripts in candidates:
        mod_path = scripts / "uninstall_private_brain.py"
        if mod_path.is_file():
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            import uninstall_private_brain as u  # type: ignore

            return u
    raise FileNotFoundError(
        "uninstall_private_brain.py not found under package/scripts or "
        "$CODEX_HOME/private-brain/scripts"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        _help()
        return 0

    cmd = argv[0]
    if cmd == "sideload":
        from .sideload import sideload

        model = argv[1] if len(argv) > 1 else "gpt-5.6-terra"
        print(json.dumps(sideload(model=model), indent=2))
        return 0

    if cmd == "doctor":
        from .paths import brain_home, codex_home, sessions_dir

        ch, bh = codex_home(), brain_home()
        report = {
            "codex_home": str(ch),
            "brain_home": str(bh),
            "hooks_json": (ch / "hooks.json").exists(),
            "beast_profile": (ch / "beast.config.toml").exists(),
            "sessions": str(sessions_dir()),
            "sessions_exists": sessions_dir().is_dir(),
            "entry": "codex -p beast",
            "note": "Private Brain does not replace the codex binary",
            "uninstall": "python -m private_brain uninstall",
        }
        scripts = bh / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        try:
            from audit_lib import verify_chain  # type: ignore
            from brain_lib import status  # type: ignore

            report["brain"] = status()
            report["chain_ok"] = verify_chain().get("ok")
        except Exception as e:
            report["brain_error"] = str(e)[:200]
        print(json.dumps(report, indent=2, default=str))
        return 0

    if cmd == "uninstall":
        try:
            u = _resolve_uninstall_module()
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        return int(u.main(argv[1:]))

    print("Unknown helper. End users should run: codex -p beast", file=sys.stderr)
    print("Helpers: sideload | doctor | uninstall", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
