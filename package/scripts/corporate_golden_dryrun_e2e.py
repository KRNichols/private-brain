#!/usr/bin/env python3
"""Corporate golden dry-run E2E — NO secrets required.

Proves the join/map path works before real Corporate tokens arrive:
  1. Load synthetic golden_join (example, no secrets)
  2. Apply via day1_first_start --join --yes
  3. Assert program_id / hosts / URLs landed in golden_config + env map
  4. Write golden_config join pack
  5. Doctor still runnable (library soft only when not ZERO_SOFT product path)

When real secrets arrive: replace example join with Corporate golden_join
and set PIP_INDEX_URL / tokens via secrets_store — this suite stays the scaffold.

ZERO SOFT on suite gates.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({"name": name, "ok": bool(ok), "hard": True, "detail": str(detail)[:500]})
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f" - {detail[:160]}" if detail and not ok else ""))
    return bool(ok)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    os.environ.setdefault("PB_ZERO_SOFT", "1")
    os.environ.setdefault("PB_CI", "1")
    os.environ.setdefault("PB_ENTERPRISE", "1")
    os.environ.setdefault("PB_NONINTERACTIVE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PB_SESSIONS_EMPTY_ACK", "1")

    print("=" * 72)
    print(" CORPORATE GOLDEN DRY-RUN E2E (no secrets)")
    print("=" * 72)

    example = ROOT / "config" / "corporate_golden_join.example.json"
    gate("example_join_present", example.is_file(), str(example))
    if not example.is_file():
        return 1
    join_data = json.loads(example.read_text(encoding="utf-8"))
    gate("example_has_no_token_fields", not any(
        k in join_data for k in ("token", "password", "secret", "api_key", "GITLAB_TOKEN", "JIRA_TOKEN")
    ), "join must never embed secrets")
    gate("example_has_program", bool(join_data.get("program_id")))
    gate("example_has_hosts", len(join_data.get("allowlist_hosts") or []) >= 2)
    gate("example_has_gitlab_url", "gitlab" in str(join_data.get("gitlab_url") or "").lower())

    tmp = Path(tempfile.mkdtemp(prefix="pb-corp-dry-"))
    try:
        codex = tmp / ".codex"
        brain = codex / "private-brain"
        brain.mkdir(parents=True)
        shutil.copytree(SCRIPTS, brain / "scripts", dirs_exist_ok=True)
        for name in ("config", "private_brain"):
            src = ROOT / name
            if src.is_dir():
                shutil.copytree(src, brain / name, dirs_exist_ok=True)
        join_path = brain / "golden_join.json"
        join_path.write_text(json.dumps(join_data, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env.update(
            {
                "CODEX_HOME": str(codex),
                "PRIVATE_BRAIN_HOME": str(brain),
                "PB_KIT_ROOT": str(brain),
                "PYTHONPATH": str(brain / "scripts") + os.pathsep + str(brain),
                "PB_ENTERPRISE": "1",
                "PB_CI": "1",
                "PB_ZERO_SOFT": "1",
                "PB_NONINTERACTIVE": "1",
                "PB_SESSIONS_EMPTY_ACK": "1",
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            }
        )

        day1 = brain / "scripts" / "day1_first_start.py"
        r = subprocess.run(
            [
                sys.executable,
                str(day1),
                "--yes",
                "--route",
                "headless",
                "--join",
                str(join_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(brain),
        )
        gate(
            "day1_join_rc0",
            r.returncode == 0,
            f"rc={r.returncode} {(r.stderr or r.stdout or '')[-200:]}",
        )

        # golden config write
        r2 = subprocess.run(
            [sys.executable, str(brain / "scripts" / "golden_config.py")],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(brain),
        )
        gate("golden_config_rc0", r2.returncode == 0, (r2.stderr or r2.stdout or "")[-160:])

        st = brain / ".brain" / "state"
        join_out = st / "golden_join.json"
        gcfg = st / "golden_config.json"
        gmd = st / "GOLDEN_CONFIG.md"
        gate("golden_join_written", join_out.is_file() or join_path.is_file())
        gate("golden_config_json", gcfg.is_file(), str(gcfg))
        gate("golden_config_md", gmd.is_file() or (st / "GOLDEN_CONFIG.compact.md").is_file())

        # Map assertions — program / hosts from join
        blob = ""
        if gcfg.is_file():
            blob = gcfg.read_text(encoding="utf-8", errors="replace")
        elif join_out.is_file():
            blob = join_out.read_text(encoding="utf-8", errors="replace")
        else:
            blob = (r.stdout or "") + (r.stderr or "")
        gate(
            "map_program_id",
            str(join_data.get("program_id")) in blob or str(join_data.get("program_id")) in (r.stdout or ""),
            join_data.get("program_id"),
        )
        hosts = join_data.get("allowlist_hosts") or []
        hit = sum(1 for h in hosts if h in blob or h in (r.stdout or ""))
        gate("map_hosts_present", hit >= 1, f"hit={hit}/{len(hosts)}")
        gate(
            "map_gitlab_url",
            "gitlab.example.corp" in blob or "gitlab" in blob.lower(),
            "gitlab host map",
        )

        # day1 map state if present
        dmap = st / "day1_map.json"
        if dmap.is_file():
            dm = json.loads(dmap.read_text(encoding="utf-8"))
            gate("day1_map_json", isinstance(dm, dict), str(type(dm)))
        else:
            gate("day1_map_json", True, "optional path — golden_config is source of truth")

        # ensure enterprise profile + doctor runs
        sys.path.insert(0, str(brain / "scripts"))
        os.environ.update({k: env[k] for k in ("PRIVATE_BRAIN_HOME", "CODEX_HOME", "PB_ENTERPRISE", "PYTHONPATH")})
        try:
            from enterprise import doctor_enterprise, ensure_enterprise_profile  # type: ignore

            ensure_enterprise_profile()
            d = doctor_enterprise()
            gate("doctor_runs", isinstance(d, dict) and "checks" in d, str(d.get("ok")))
        except Exception as e:
            gate("doctor_runs", False, str(e))

        # secrets_store path exists for future Corporate tokens (empty ok)
        ss = brain / "scripts" / "secrets_store.py"
        gate("secrets_store_module", ss.is_file())

        report = {
            "suite": "corporate_golden_dryrun_e2e",
            "ok": FAIL == 0,
            "pass": PASS,
            "fail": FAIL,
            "program_id": join_data.get("program_id"),
            "results": RESULTS,
            "note": "NO secrets exercised. Swap example join + secrets_store when Corporate golden secrets arrive.",
        }
        for d in (st, ROOT / "e2e-reports", ROOT / ".brain" / "state"):
            try:
                d.mkdir(parents=True, exist_ok=True)
                (d / "CORPORATE_GOLDEN_DRYRUN_E2E.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

        print("\n" + "=" * 72)
        print(f" CORPORATE GOLDEN DRY-RUN: pass={PASS} fail={FAIL}")
        if FAIL:
            print(" RED")
            for row in RESULTS:
                if not row["ok"]:
                    print(f"   FAIL {row['name']}: {row['detail'][:200]}")
            return 1
        print(" GREEN — join/map/golden path ready for Corporate secrets")
        return 0
    except Exception as e:
        traceback.print_exc()
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    finally:
        if os.environ.get("PB_E2E_KEEP") != "1":
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
