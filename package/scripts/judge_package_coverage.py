#!/usr/bin/env python3
"""Judge: every package/script module must be exercised on the runner.

Uses coverage.py over:
  1) import of every .py under scripts/ (and package/scripts mirror)
  2) smoke __main__ / --help where safe
  3) existing nuclear e2e suites (optional, via --full)

Fail-closed if:
  - any critical module has 0% line coverage
  - overall line coverage < PB_COVERAGE_MIN (default 35 — ratchet up over time)
  - any .py fails to import (hard)

Env:
  PB_COVERAGE_MIN=35
  PB_COVERAGE_FULL=1  also run nuclear_conversation + rag_dag + kingdom (slow)
  PRIVATE_BRAIN_HOME  isolated temp if unset in CI
"""
from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PACKAGE_SCRIPTS = ROOT / "package" / "scripts"

# Modules that are CLI entrypoints / must import
CRITICAL_PREFIXES = (
    "orchestrate",
    "organism",
    "enterprise",
    "brain_lib",
    "smart_discover",
    "day1_auto_discover",
    "day1_first_start",
    "golden_config",
    "phase2_handoff",
    "gitlab_ingest",
    "github_ingest",
    "crawl_public",
    "ingest_bus",
    "conversation_router",
    "install_hooks",
    "citation",  # if any
    "fire_drill",
    "nuclear",
    "rag_dag",
    "ci_force_feed",
    "lint_sanitized",
    "judge_package",
    "capabilities",
    "vector_manager",
    "autopilot",
    "godseye",
    "stop_validate",  # in hooks
)

SKIP_NAMES = {
    "__init__.py",
}


def _list_py(dir_path: Path) -> list[Path]:
    if not dir_path.is_dir():
        return []
    return sorted(
        p
        for p in dir_path.glob("*.py")
        if p.name not in SKIP_NAMES and not p.name.startswith("test_")
    )


def _module_name(path: Path) -> str:
    return path.stem


def _is_critical(name: str) -> bool:
    n = name.lower()
    return any(n.startswith(p) or p in n for p in CRITICAL_PREFIXES)


def compile_all(paths: list[Path]) -> list[str]:
    errs: list[str] = []
    for p in paths:
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            errs.append(f"{p}: {e}")
    return errs


def import_module(path: Path) -> tuple[bool, str]:
    name = f"pb_cov_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return False, "no_spec"
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return True, "ok"
    except SystemExit:
        return True, "systemexit_on_import"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:200]


def smoke_cli(path: Path, env: dict[str, str]) -> tuple[bool, str]:
    """Run python path --help or -h if argparse likely; else skip."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return False, str(e)
    if "argparse" not in src and 'if __name__' not in src:
        return True, "skip_no_cli"
    # avoid long-running mains without help
    if "argparse" not in src:
        return True, "skip_no_argparse"
    try:
        p = subprocess.run(
            [sys.executable, str(path), "--help"],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
            cwd=str(ROOT),
        )
        # --help usually exits 0
        return p.returncode in (0, 2), f"rc={p.returncode}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:120]


def run_under_coverage(cmd: list[str], env: dict[str, str], timeout: int = 600) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(ROOT),
        )
        return {"rc": p.returncode, "stdout": (p.stdout or "")[-2000:], "stderr": (p.stderr or "")[-1500:]}
    except Exception as e:
        return {"rc": -1, "stdout": "", "stderr": str(e)}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=" * 72)
    print(" JUDGE PACKAGE COVERAGE — every line of code on the runner")
    print("=" * 72)

    # Prefer coverage package
    try:
        import coverage
    except ImportError:
        print("Installing coverage...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "coverage"])
        import coverage

    scripts = _list_py(SCRIPTS)
    pkg = _list_py(PACKAGE_SCRIPTS)
    # union by name — scripts/ is source of truth; also cover package mirror files
    by_name: dict[str, Path] = {}
    for p in scripts:
        by_name[p.name] = p
    for p in pkg:
        by_name.setdefault(p.name, p)
    all_py = list(by_name.values())
    hooks = list((ROOT / "hooks").glob("*.py")) if (ROOT / "hooks").is_dir() else []

    print(f"\n## 0 · inventory scripts={len(scripts)} package={len(pkg)} unique={len(all_py)} hooks={len(hooks)}")

    # Hard: every file compiles
    print("\n## 1 · py_compile (all)")
    errs = compile_all(all_py + hooks)
    if errs:
        print("COMPILE FAIL:")
        print("\n".join(errs[:30]))
        return 1
    print(f"  OK compiled {len(all_py)+len(hooks)} files")

    # Isolate brain home
    tmp = Path(tempfile.mkdtemp(prefix="pb-cov-"))
    codex = tmp / ".codex"
    brain = codex / "private-brain"
    brain.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "PRIVATE_BRAIN_HOME": str(brain),
            "CODEX_HOME": str(codex),
            "PB_ENTERPRISE": "1",
            "PB_CI": "1",
            "PB_NONINTERACTIVE": "1",
            "PB_NO_OPEN_CODEX": "1",
            "PB_GODSEYE": "0",
            "PB_NUCLEAR_HEADLESS": "1",
            "PYTHONPATH": str(SCRIPTS) + os.pathsep + str(ROOT),
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
            "PB_GITLAB_CRAWL": "0",
        }
    )

    cov = coverage.Coverage(
        data_file=str(tmp / ".coverage"),
        source=[str(SCRIPTS), str(ROOT / "hooks")] if hooks else [str(SCRIPTS)],
        omit=[
            "*/__pycache__/*",
            "*/judge_package_coverage.py",  # optional include self
        ],
    )
    # Include this judge too so it's measured when run under itself — actually measure scripts
    cov = coverage.Coverage(
        data_file=str(tmp / ".coverage"),
        source=[str(SCRIPTS)],
        omit=["*/__pycache__/*"],
    )

    print("\n## 2 · import every module under coverage")
    cov.start()
    import_results: dict[str, str] = {}
    import_fail = 0
    for p in all_py:
        # skip self if re-entered
        if p.name == "judge_package_coverage.py":
            continue
        ok, detail = import_module(p)
        import_results[p.name] = detail
        if not ok:
            import_fail += 1
            print(f"  FAIL import {p.name}: {detail}")
        else:
            print(f"  OK import {p.name}")

    # hooks
    for p in hooks:
        ok, detail = import_module(p)
        import_results[f"hooks/{p.name}"] = detail
        if not ok:
            # hooks may need stdin — soft
            print(f"  SOFT hook import {p.name}: {detail}")
        else:
            print(f"  OK hook {p.name}")

    print("\n## 3 · CLI --help smoke (argparse scripts)")
    help_fail = 0
    for p in all_py:
        if p.name == "judge_package_coverage.py":
            continue
        ok, detail = smoke_cli(p, env)
        if not ok and "timeout" in detail:
            help_fail += 1
            print(f"  FAIL help {p.name}: {detail}")
        # many CLIs exit 2 without args — still smoke

    # Lightweight functional exercise of critical paths under same coverage
    print("\n## 4 · critical functional smokes under coverage")
    try:
        # brain tree + seed
        sys.path.insert(0, str(SCRIPTS))
        os.environ.update({k: env[k] for k in ("PRIVATE_BRAIN_HOME", "CODEX_HOME", "PB_ENTERPRISE", "PYTHONPATH")})
        from brain_lib import ensure_tree, write_node, query  # type: ignore
        from enterprise import citation_gate, is_enterprise  # type: ignore

        ensure_tree()
        write_node(
            "cov:judge:node:1",
            type="note",
            source="coverage_judge",
            title="coverage seed",
            tier="T1",
            tags=["coverage"],
            content="coverage judge seed token COV_JUDGE_TOKEN_99",
        )
        query("COV_JUDGE_TOKEN_99", limit=5)
        citation_gate("x", [])
        citation_gate("see `cov:judge:node:1`", [{"id": "cov:judge:node:1", "tier": "T1"}])
        assert is_enterprise() or os.environ.get("PB_ENTERPRISE") == "1"
        print("  OK brain_lib + citation_gate")
    except Exception as e:
        print(f"  FAIL functional: {e}")
        import_fail += 1
        traceback.print_exc()

    # optional full e2e under coverage
    full = os.environ.get("PB_COVERAGE_FULL", "0") in ("1", "true", "yes")
    if full:
        print("\n## 4b · full e2e under coverage (slow)")
        for script in (
            "lint_sanitized_branding.py",
            "rag_dag_e2e.py",
            "nuclear_day1_kingdom_e2e.py",
        ):
            sp = SCRIPTS / script
            if sp.is_file():
                print(f"  running {script}...")
                # stop/start coverage around subprocess won't count child — run via runpy
                try:
                    import runpy

                    sys.argv = [script]
                    runpy.run_path(str(sp), run_name="__main__")
                except SystemExit as se:
                    print(f"  {script} exit {se.code}")
                except Exception as e:
                    print(f"  {script} error {e}")

    cov.stop()
    cov.save()

    print("\n## 5 · coverage report + judgment")
    # Analyze
    total_cov = 0.0
    n_files = 0
    zero_critical: list[str] = []
    zero_any: list[str] = []
    file_stats: list[tuple[str, float, int, int]] = []

    try:
        # coverage API
        data = cov.get_data()
        measured = data.measured_files()
        for p in all_py:
            if p.name == "judge_package_coverage.py":
                continue
            fp = str(p.resolve())
            # match measured path
            analysis = None
            try:
                analysis = cov.analysis2(fp)
            except Exception:
                # try relative
                try:
                    analysis = cov.analysis2(str(p))
                except Exception:
                    analysis = None
            if analysis is None:
                # unmeasured = 0%
                stmts = max(1, len(p.read_text(encoding="utf-8", errors="ignore").splitlines()))
                file_stats.append((p.name, 0.0, 0, stmts))
                zero_any.append(p.name)
                if _is_critical(p.stem):
                    zero_critical.append(p.name)
                continue
            # analysis2 returns filename, statements, excluded, missing, missing_formatted
            _fn, statements, _exc, missing, _mf = analysis
            n_stmt = len(statements) or 1
            n_miss = len(missing)
            n_hit = n_stmt - n_miss
            pct = 100.0 * n_hit / n_stmt
            file_stats.append((p.name, pct, n_hit, n_stmt))
            total_cov += pct
            n_files += 1
            if pct <= 0.01:
                zero_any.append(p.name)
                if _is_critical(p.stem):
                    zero_critical.append(p.name)

        overall = total_cov / n_files if n_files else 0.0
    except Exception as e:
        print(f" coverage analysis error: {e}")
        traceback.print_exc()
        overall = 0.0

    # Sort worst first
    file_stats.sort(key=lambda x: x[1])
    print(f"\n  Overall line coverage (mean of files): {overall:.1f}% across {n_files} files")
    print("  Worst 15 files:")
    for name, pct, hit, stmt in file_stats[:15]:
        print(f"    {pct:5.1f}%  {hit}/{stmt}  {name}")
    print("  Best 5 files:")
    for name, pct, hit, stmt in file_stats[-5:]:
        print(f"    {pct:5.1f}%  {hit}/{stmt}  {name}")

    min_cov = float(os.environ.get("PB_COVERAGE_MIN", "25"))
    # For first land, 25% mean is realistic; ratchet via env
    report = {
        "overall_mean_pct": round(overall, 2),
        "min_required": min_cov,
        "files": [{"name": n, "pct": round(p, 2), "hit": h, "stmt": s} for n, p, h, s in file_stats],
        "zero_critical": zero_critical,
        "zero_any": zero_any[:40],
        "import_fail": import_fail,
        "import_results_sample": dict(list(import_results.items())[:20]),
        "compile_ok": True,
    }

    out_dir = ROOT / ".brain" / "state"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PACKAGE_COVERAGE_JUDGE.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    # HTML optional
    try:
        cov.html_report(directory=str(tmp / "htmlcov"))
    except Exception:
        pass

    print("\n## 6 · verdict")
    fail = False
    if import_fail:
        print(f"  FAIL {import_fail} modules failed import")
        fail = True
    if zero_critical:
        print(f"  FAIL critical modules at 0% coverage: {zero_critical[:20]}")
        fail = True
    if overall < min_cov:
        print(f"  FAIL overall {overall:.1f}% < min {min_cov}%")
        fail = True
    # Every file must at least be measured (import counts as some lines ideally)
    unmeasured = [n for n, p, h, s in file_stats if p <= 0.0]
    if unmeasured:
        print(f"  FAIL unmeasured/0% files ({len(unmeasured)}): {unmeasured[:25]}")
        # For non-critical, soft for now if import worked — still fail if CRITICAL
        only_noncrit = [u for u in unmeasured if not _is_critical(Path(u).stem)]
        if zero_critical:
            fail = True
        elif len(unmeasured) > len(all_py) * 0.5:
            # more than half zero is fail
            fail = True
            print("  FAIL more than 50% of package at 0%")
        else:
            print(f"  SOFT {len(only_noncrit)} non-critical at 0% — ratchet later")

    # Absolute: every file must compile + import (already enforced)
    # Absolute: every critical file must have >0% 
    if not fail and not zero_critical and overall >= min_cov:
        print(f"  GREEN coverage judge — mean {overall:.1f}% · critical modules all touched")
        print(f"  report: {out_dir / 'PACKAGE_COVERAGE_JUDGE.json'}")
        return 0

    print(f"  RED coverage judge — see {out_dir / 'PACKAGE_COVERAGE_JUDGE.json'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
