#!/usr/bin/env python3
"""Runtime capability probe + optional-package self-heal / self-repair.

Two worlds, one code path:

  HOME (no Corporate Library / Protected Gateway):
    - Install whatever you want into the venv (numpy, pygame, PyOpenGL, …).
    - heal_optional() uses default pip / public index when packages are missing.

  CORPORATE (enterprise / corporate-package-index required):
    - Optional packages come ONLY from PIP_INDEX_URL / PB_PIP_INDEX_URL (Corporate Library / Protected Gateway).
    - No index → do NOT hit public PyPI; degrade to stdlib / headless.
    - Code always picks the best *importable* modules and keeps running.

Core RAG-DAG is always stdlib. GodsEye / numpy / YAML are optional feature packs.

  python capabilities.py
  python capabilities.py --json
  python capabilities.py --heal          # install missing optional when policy allows
  python capabilities.py --heal --dry-run
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

# Optional packages: (import_name, pip_name, feature, required_for_core)
OPTIONAL: list[tuple[str, str, str, bool]] = [
    ("numpy", "numpy", "GodsEye layout acceleration + PyOpenGL arrays", False),
    ("pygame", "pygame", "GodsEye GUI window", False),
    ("OpenGL", "PyOpenGL", "GodsEye TRUE GL (Metal/OpenGL draw)", False),
    ("OpenGL_accelerate", "PyOpenGL-accelerate", "Faster GL bindings", False),
    ("yaml", "PyYAML", "Richer enterprise.yaml parse (fallback exists)", False),
]


def brain_home() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser()
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "private-brain"


def _try_import(name: str) -> dict[str, Any]:
    # Keep stdout clean for JSON heal/doctor pipes (pygame prints a banner on import)
    if name in ("pygame", "OpenGL", "OpenGL_accelerate"):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        # swallow import-time chatter on stdout/stderr for probe only
        import contextlib
        import io

        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", None)
        return {"ok": True, "version": str(ver) if ver else True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def detect_environment() -> dict[str, Any]:
    """Classify install site: home_dev vs corporate_enterprise (no hard Corporate Library dep at home)."""
    index = (
        os.environ.get("PIP_INDEX_URL")
        or os.environ.get("PB_PIP_INDEX_URL")
        or ""
    ).strip()
    trusted = (
        os.environ.get("PIP_TRUSTED_HOST")
        or os.environ.get("PB_PIP_TRUSTED_HOST")
        or ""
    ).strip()
    enterprise = os.environ.get("PB_ENTERPRISE", "").strip() in ("1", "true", "yes")
    require = os.environ.get("PB_PIP_REQUIRE_CORPORATE_INDEX", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    # Corporate path: enterprise flag OR explicit corporate-package-index-required OR index already set
    # while enterprise is on. Home is everything else — free pip, no Corporate Library needed.
    if enterprise or require:
        site = "corporate_enterprise"
        allow_public_pip = False
    else:
        site = "home_dev"
        allow_public_pip = True

    index_host = None
    if index.startswith("http") and "/" in index[8:]:
        try:
            index_host = index.split("/")[2]
        except Exception:
            index_host = index[:80]
    elif index:
        index_host = index[:80]

    return {
        "site": site,
        "allow_public_pip": allow_public_pip,
        "enterprise": enterprise,
        "require_corporate-package-index": require,
        "index_url_set": bool(index),
        "index_url": index or None,
        "index_host": index_host,
        "trusted_host": trusted or None,
        "corporate_library_gateway": "only_on_corporate_with_PIP_INDEX_URL",
        "note": (
            "Home: install optional packs freely. "
            "Corporate: Corporate Library / Protected Gateway via PIP_INDEX_URL; missing optional → degrade, core stays stdlib."
        ),
    }


def resolve_python() -> str:
    """Prefer private-brain venv. Windows Scripts first; Unix bin first."""
    home = brain_home()
    if sys.platform.startswith("win"):
        candidates = [
            home / "venv" / "Scripts" / "python.exe",
            home / "venv" / "Scripts" / "python",
            home / "venv" / "bin" / "python3",
            home / "venv" / "bin" / "python",
        ]
    else:
        candidates = [
            home / "venv" / "bin" / "python3",
            home / "venv" / "bin" / "python",
            home / "venv" / "Scripts" / "python.exe",
            home / "venv" / "Scripts" / "python",
        ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def probe() -> dict[str, Any]:
    """Detect platform + which optional modules are live; pick feature backends."""
    mods: dict[str, Any] = {}
    for imp, pip, feature, _core in OPTIONAL:
        info = _try_import(imp)
        info["pip"] = pip
        info["feature"] = feature
        mods[imp] = info

    has_numpy = bool(mods.get("numpy", {}).get("ok"))
    has_pygame = bool(mods.get("pygame", {}).get("ok"))
    has_gl = bool(mods.get("OpenGL", {}).get("ok"))
    has_yaml = bool(mods.get("yaml", {}).get("ok"))

    # Backend selection from *importable* modules only (self-select)
    if has_pygame and has_gl:
        godseye_backend = "gl"
        godseye_mode = "TRUE_GL"
    elif has_pygame:
        godseye_backend = "cpu"
        godseye_mode = "software_pygame"
    else:
        godseye_backend = "off"
        godseye_mode = "headless_only"

    layout_accel = "numpy" if has_numpy else "pure_python"
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    is_apple = sysname == "darwin" and ("arm" in machine or "aarch" in machine)
    cuda_usable = False
    if not is_apple:
        try:
            import torch  # type: ignore

            cuda_usable = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
        except Exception:
            cuda_usable = False

    env = detect_environment()
    selected = select_runtime_features(
        {
            "numpy": has_numpy,
            "pygame": has_pygame,
            "opengl": has_gl,
            "yaml": has_yaml,
            "godseye_backend": godseye_backend,
            "layout_accel": layout_accel,
        }
    )

    return {
        "ts": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.split()[0],
        "python_exe": resolve_python(),
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "is_apple_silicon": is_apple,
            "cuda_usable": cuda_usable,
            "note": "CUDA is NVIDIA-only; Apple uses Metal via OpenGL for GodsEye draw",
        },
        "environment": env,
        "modules": mods,
        "features": {
            "core_rag_stdlib": True,  # always
            "yaml_parser": "pyyaml" if has_yaml else "stdlib_fallback",
            "godseye_backend": godseye_backend,
            "godseye_mode": godseye_mode,
            "layout_accel": layout_accel,
            "numpy": has_numpy,
            "pygame": has_pygame,
            "opengl": has_gl,
        },
        "selected": selected,
        "pip": {
            "index_url_set": env["index_url_set"],
            "index_host": env["index_host"],
            "enterprise": env["enterprise"],
            "require_corporate-package-index": env["require_corporate-package-index"],
            "allow_public_pip": env["allow_public_pip"],
            "site": env["site"],
        },
        "policy": {
            "home_dev": "install freely into venv; no Corporate Library / Protected Gateway required",
            "corporate": "PIP_INDEX_URL/Corporate Library / Protected Gateway only; missing optional → degrade; core never requires third-party",
            "self_heal": "probe → install optional when policy allows → re-probe → apply_env_hints; else degrade",
            "self_select": "runtime always uses importable modules only; never assumes a package is present",
        },
    }


def select_runtime_features(feat: dict[str, Any]) -> dict[str, Any]:
    """Map available modules → concrete code paths the rest of the system should use."""
    backend = str(feat.get("godseye_backend") or "off")
    layout = str(feat.get("layout_accel") or "pure_python")
    return {
        "core": "stdlib",
        "yaml": "yaml" if feat.get("yaml") else "json_stdlib",
        "godseye": {
            "enabled": backend != "off",
            "module": (
                "visualizer.graph_gl"
                if backend == "gl"
                else ("visualizer.live_gui" if backend == "cpu" else None)
            ),
            "backend": backend,
        },
        "layout": {
            "engine": layout,
            "module": "numpy" if layout == "numpy" else "math",
        },
        "degraded": backend == "off" or layout == "pure_python",
        "message": (
            "full stack"
            if backend == "gl" and layout == "numpy"
            else (
                "partial — headless core OK"
                if backend == "off"
                else f"godseye={backend} layout={layout}"
            )
        ),
    }


def recommend_install(report: dict[str, Any] | None = None) -> list[str]:
    """Pip names that would unlock missing optional features."""
    r = report or probe()
    want: list[str] = []
    mods = r.get("modules") or {}
    for imp, pip, _feat, _core in OPTIONAL:
        if not (mods.get(imp) or {}).get("ok"):
            # skip accelerate if no OpenGL base
            if imp == "OpenGL_accelerate" and not (mods.get("OpenGL") or {}).get("ok"):
                continue
            # PyOpenGL-accelerate often fails / unneeded on Apple Silicon
            if imp == "OpenGL_accelerate":
                plat = (r.get("platform") or {})
                if plat.get("is_apple_silicon"):
                    continue
            want.append(pip)
    seen: set[str] = set()
    out: list[str] = []
    for p in want:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def heal_optional(*, dry_run: bool = False, force_public: bool = False) -> dict[str, Any]:
    """Attempt to install missing optional packages under site policy.

    Home: public/default pip OK (no Corporate Library needed).
    Corporate: uses PIP_INDEX_URL only; if missing index → degrade (self-heal by selection).
    """
    report = probe()
    env = report.get("environment") or detect_environment()
    missing = recommend_install(report)
    actions: list[dict[str, Any]] = []
    index = env.get("index_url") or None
    trusted = env.get("trusted_host") or None
    allow_public = bool(env.get("allow_public_pip")) or force_public
    site = env.get("site") or "home_dev"

    if not missing:
        return {
            "ok": True,
            "site": site,
            "actions": [{"action": "noop", "detail": "all optional modules present"}],
            "features": report["features"],
            "selected": report.get("selected"),
            "missing": [],
        }

    # Corporate without approved index: degrade — never silent public PyPI
    if not allow_public and not index:
        return {
            "ok": True,
            "site": site,
            "degraded": True,
            "actions": [
                {
                    "action": "skip_install",
                    "detail": (
                        "no PIP_INDEX_URL on Corporate path — "
                        "request packages on Corporate Library / Protected Gateway; core RAG remains stdlib; "
                        "runtime self-selects importable modules only"
                    ),
                    "missing": missing,
                }
            ],
            "features": report["features"],
            "selected": report.get("selected"),
            "missing": missing,
            "request_onboard": missing,
        }

    py = resolve_python()

    for pip_name in missing:
        cmd = [py, "-m", "pip", "install", pip_name]
        if index:
            cmd.extend(["--index-url", index])
            if trusted:
                cmd.extend(["--trusted-host", trusted])
        # home without index: plain pip (public) — intentional
        cmd.append("--disable-pip-version-check")
        if dry_run:
            actions.append(
                {
                    "action": "would_install",
                    "package": pip_name,
                    "site": site,
                    "via": "index" if index else "public_pip",
                    "cmd": cmd,
                }
            )
            continue
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            actions.append(
                {
                    "action": "install",
                    "package": pip_name,
                    "site": site,
                    "via": "index" if index else "public_pip",
                    "rc": p.returncode,
                    "ok": p.returncode == 0,
                    "stderr": (p.stderr or "")[-300:],
                }
            )
        except Exception as e:
            actions.append(
                {
                    "action": "install",
                    "package": pip_name,
                    "ok": False,
                    "error": str(e)[:160],
                }
            )

    after = probe()
    still = recommend_install(after)
    # Self-repair: even if some installs failed, selected features use what is live
    return {
        "ok": True,
        "site": site,
        "degraded": bool(still) and not allow_public,
        "actions": actions,
        "features_before": report["features"],
        "features_after": after["features"],
        "selected": after.get("selected"),
        "still_missing": still,
        "self_repaired": True,
        "detail": (
            "runtime re-probed; using best importable stack"
            + (f"; still missing {still}" if still else "; full optional stack")
        ),
    }


def self_repair() -> dict[str, Any]:
    """Probe → optional heal → re-probe → apply env. Safe on home and Corporate."""
    before = probe()
    heal = heal_optional(dry_run=False)
    after = probe()
    hints = apply_env_hints(after)
    path = write_state(after)
    return {
        "ok": True,
        "site": (after.get("environment") or {}).get("site"),
        "features_before": before.get("features"),
        "features_after": after.get("features"),
        "selected": after.get("selected"),
        "heal": {
            "degraded": heal.get("degraded"),
            "still_missing": heal.get("still_missing") or heal.get("missing"),
            "request_onboard": heal.get("request_onboard"),
            "actions": [
                a.get("package") or a.get("action") for a in (heal.get("actions") or [])
            ][:16],
        },
        "env_hints": hints,
        "state": str(path),
    }


def write_state(report: dict[str, Any] | None = None) -> Path:
    r = report or probe()
    path = brain_home() / ".brain" / "state" / "capabilities.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(r, indent=2), encoding="utf-8")
    return path


def apply_env_hints(report: dict[str, Any] | None = None) -> dict[str, str]:
    """Set process env so GodsEye / layout pick the best *available* backend."""
    r = report or probe()
    feat = r.get("features") or {}
    backend = str(feat.get("godseye_backend") or "off")
    # Always force backend to match reality (override stale PB_GODSEYE_BACKEND=gl)
    if backend == "gl":
        os.environ["PB_GODSEYE_BACKEND"] = "gl"
    elif backend == "cpu":
        os.environ["PB_GODSEYE_BACKEND"] = "cpu"
        # Don't force GodsEye on if user wanted headless; only fix backend if GUI on
    else:
        # no pygame — cannot run GUI; leave PB_GODSEYE as user set but mark backend off
        os.environ["PB_GODSEYE_BACKEND"] = "off"
        if os.environ.get("PB_GODSEYE") == "1":
            # soft demote so launchers don't crash spinning missing pygame
            os.environ["PB_GODSEYE"] = "0"
            os.environ["PB_GODSEYE_DEMOTED"] = "1"
    if feat.get("numpy"):
        os.environ["PB_LAYOUT_ACCEL"] = "numpy"
    else:
        os.environ["PB_LAYOUT_ACCEL"] = "python"
    return {
        "PB_GODSEYE_BACKEND": os.environ.get("PB_GODSEYE_BACKEND", ""),
        "PB_LAYOUT_ACCEL": os.environ.get("PB_LAYOUT_ACCEL", ""),
        "PB_GODSEYE": os.environ.get("PB_GODSEYE", ""),
        "PB_GODSEYE_DEMOTED": os.environ.get("PB_GODSEYE_DEMOTED", ""),
        "site": str((r.get("environment") or {}).get("site") or ""),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Private Brain capability probe / optional heal (home free · Corporate index-or-degrade)"
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--heal",
        action="store_true",
        help="install missing optional packages when policy allows; else degrade",
    )
    ap.add_argument(
        "--repair",
        action="store_true",
        help="full self-repair: probe → heal → apply env → write state",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.repair:
        out = self_repair()
        print(json.dumps(out, indent=2))
        return 0
    if args.heal:
        out = heal_optional(dry_run=args.dry_run)
        write_state(probe())
        apply_env_hints()
        print(json.dumps(out, indent=2))
        return 0
    r = probe()
    apply_env_hints(r)
    path = write_state(r)
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        feat = r["features"]
        env = r.get("environment") or {}
        sel = r.get("selected") or {}
        print("==============================================")
        print(" Private Brain — capabilities")
        print("==============================================")
        print(f" site:         {env.get('site')} (public_pip={env.get('allow_public_pip')})")
        print(f" core_rag:     always stdlib (ok)")
        print(f" godseye:      {feat.get('godseye_mode')} (backend={feat.get('godseye_backend')})")
        print(f" layout:       {feat.get('layout_accel')}")
        print(f" numpy:        {feat.get('numpy')}")
        print(f" pygame:       {feat.get('pygame')}")
        print(f" opengl:       {feat.get('opengl')}")
        print(f" yaml:         {feat.get('yaml_parser')}")
        print(f" selected:     {sel.get('message')}")
        print(f" pip_index:    {r['pip'].get('index_url_set')} host={r['pip'].get('index_host')}")
        print(
            f" apple_silicon:{r['platform'].get('is_apple_silicon')} "
            f"cuda_usable={r['platform'].get('cuda_usable')}"
        )
        miss = recommend_install(r)
        if miss:
            print(f" missing_opt:  {miss}")
            if env.get("allow_public_pip"):
                print("              home: run capabilities.py --heal  (or pip install freely)")
            else:
                print(
                    "              Corporate: set PIP_INDEX_URL (Corporate Library / Protected Gateway) then --heal; "
                    "or request onboard — core stays headless"
                )
        else:
            print(" missing_opt:  (none)")
        print(f" state:        {path}")
        print("==============================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
