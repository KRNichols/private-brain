#!/usr/bin/env python3
"""Fail closed if READY/package surface contains test/sim leakage or OpenGL GodsEye default.

Run from repo root. Zero soft-pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"  [FAIL] {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"  [OK] {msg}", flush=True)


def main() -> int:
    print("=== RELEASE SURFACE LINT ===", flush=True)

    pkg = ROOT / "package"
    for bad in ("e2e-fixtures", ".codex-sim", ".codex-ci"):
        p = pkg / bad
        if p.exists():
            fail(f"package/{bad} must not ship")
        else:
            ok(f"package/{bad} absent")

    def _req_pins_gl(path: Path) -> bool:
        """True if a dependency pin line names PyOpenGL (ignore comments)."""
        if not path.is_file():
            return False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # pin line e.g. PyOpenGL>=3.1.0
            if "pyopengl" in s.lower() or s.lower().startswith("opengl"):
                return True
        return False

    req = ROOT / "visualizer" / "requirements.txt"
    if req.is_file():
        t = req.read_text(encoding="utf-8", errors="replace")
        if _req_pins_gl(req):
            fail("visualizer/requirements.txt must not pin PyOpenGL")
        else:
            ok("visualizer/requirements.txt has no PyOpenGL pin")
        if "pygame" not in t.lower():
            fail("visualizer/requirements.txt must list pygame")
        else:
            ok("visualizer/requirements.txt lists pygame")
    else:
        fail("visualizer/requirements.txt missing")

    pkg_req = pkg / "visualizer" / "requirements.txt"
    if pkg_req.is_file():
        if _req_pins_gl(pkg_req):
            fail("package/visualizer/requirements.txt must not pin PyOpenGL")
        else:
            ok("package/visualizer/requirements.txt clean")

    ge = (ROOT / "scripts" / "godseye.py").read_text(encoding="utf-8", errors="replace")
    if 'PB_GODSEYE_BACKEND") or "cpu"' not in ge and 'or "cpu"' not in ge:
        if 'get("PB_GODSEYE_BACKEND") or "cpu"' not in ge:
            fail("godseye.py must default backend to cpu")
        else:
            ok("godseye.py defaults to cpu")
    else:
        ok("godseye.py defaults to cpu")
    if "live_gui.py" not in ge:
        fail("godseye.py must launch live_gui.py")
    else:
        ok("godseye.py references live_gui.py")
    if 'setdefault("PB_GODSEYE_BACKEND", "gl")' in ge:
        fail("godseye.py still setdefault gl")
    else:
        ok("godseye.py no gl setdefault")

    org = (ROOT / "scripts" / "organism.py").read_text(encoding="utf-8", errors="replace")
    if 'setdefault("PB_GODSEYE_BACKEND", "gl")' in org:
        fail("organism.py still defaults gl")
    elif 'setdefault("PB_GODSEYE_BACKEND", "cpu")' in org:
        ok("organism.py defaults cpu")
    else:
        fail("organism.py missing cpu default")

    caps = (ROOT / "scripts" / "capabilities.py").read_text(encoding="utf-8", errors="replace")
    if 'godseye_backend = "gl"\n        godseye_mode = "TRUE_GL"' in caps:
        fail("capabilities.py still selects TRUE_GL when pygame+OpenGL present")
    else:
        ok("capabilities.py does not prefer TRUE_GL")
    if "software_pygame" not in caps:
        fail("capabilities.py must expose software_pygame mode")
    else:
        ok("capabilities.py software_pygame mode")

    live = ROOT / "visualizer" / "live_gui.py"
    if not live.is_file() or live.stat().st_size < 1000:
        fail("visualizer/live_gui.py missing or too small")
    else:
        ok(f"live_gui.py present ({live.stat().st_size} bytes)")

    # root e2e-fixtures allowed (CI only) — package copy is not
    if (ROOT / "e2e-fixtures").is_dir():
        ok("repo e2e-fixtures present for CI (not shipped via package)")

    mock = ROOT / "local-rag" / "providers" / "mock.py"
    if mock.is_file():
        ok("local-rag mock provider present (product readiness — OK)")

    print("=" * 40, flush=True)
    if FAILS:
        print(f"RELEASE SURFACE LINT RED — {len(FAILS)} fail(s)", flush=True)
        for f in FAILS:
            print(f"  • {f}", flush=True)
        return 1
    print("RELEASE SURFACE LINT GREEN", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
