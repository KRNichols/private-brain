#!/usr/bin/env python3
"""Operational metrics for pilot confidence — single scoreboard JSON.

Writes: .brain/state/ops_metrics.json
Used by GodsEye, doctor soft panel, fire_drill.

  python ops_metrics.py
  python ops_metrics.py --json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))

os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect() -> dict[str, Any]:
    out: dict[str, Any] = {
        "ts": _ts(),
        "suite": "ops_metrics",
        "platform": sys.platform,
        "graph": {},
        "vectors": {},
        "purity": {},
        "audit": {},
        "capabilities": {},
        "sessions": {},
        "godseye": {},
        "cloud": {},
        "health": {},
        "score": {},
    }
    t0 = time.perf_counter()

    try:
        from brain_lib import status

        st = status() or {}
        out["graph"] = {
            "nodes": st.get("node_count"),
            "edges": st.get("edge_count"),
            "by_source": st.get("by_source"),
            "by_type_top": dict(list((st.get("by_type") or {}).items())[:12]),
        }
        by = st.get("by_source") or {}
        out["sessions"] = {
            "codex_session_nodes": int(by.get("codex_session") or 0),
            "sessions_tree": (Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "sessions").is_dir(),
        }
    except Exception as e:
        out["graph"] = {"error": str(e)[:120]}

    try:
        from vector_manager import status as vs

        v = vs() or {}
        out["vectors"] = {
            "vectors": v.get("vectors"),
            "nodes": v.get("nodes"),
            "parity": v.get("parity"),
            "vocab_terms": v.get("vocab_terms"),
            "embed_backend": v.get("embed_backend"),
            "titan_available": v.get("titan_available"),
        }
    except Exception as e:
        out["vectors"] = {"error": str(e)[:120]}

    try:
        from enterprise import corpus_purity_audit

        pur = corpus_purity_audit(write=False)
        out["purity"] = {
            "pilot_ready": pur.get("pilot_ready"),
            "pilot_ready_strict": pur.get("pilot_ready_strict"),
            "pilot_ops_ready": pur.get("pilot_ops_ready"),
            "public_ratio": pur.get("public_ratio"),
            "quarantine_coverage": pur.get("quarantine_coverage"),
            "clean_nodes": pur.get("clean_nodes"),
            "public_host_nodes": pur.get("public_host_nodes"),
        }
    except Exception as e:
        out["purity"] = {"error": str(e)[:120]}

    try:
        from audit_lib import verify_chain

        ch = verify_chain() or {}
        out["audit"] = {
            "ok": ch.get("ok"),
            "events_checked": ch.get("events_checked"),
            "window": ch.get("chain_window"),
            "error_count": len(ch.get("errors") or []),
        }
    except Exception as e:
        out["audit"] = {"error": str(e)[:120]}

    try:
        from capabilities import probe

        p = probe()
        feat = p.get("features") or {}
        env = p.get("environment") or {}
        out["capabilities"] = {
            "site": env.get("site"),
            "godseye_mode": feat.get("godseye_mode"),
            "layout_accel": feat.get("layout_accel"),
            "numpy": feat.get("numpy"),
            "pygame": feat.get("pygame"),
            "opengl": feat.get("opengl"),
            "allow_public_pip": env.get("allow_public_pip"),
        }
    except Exception as e:
        out["capabilities"] = {"error": str(e)[:120]}

    # GodsEye live files
    state = _ROOT / ".brain" / "state"
    for name, key in (("godseye_perf.json", "godseye"), ("godseye_metrics.json", "godseye_metrics")):
        p = state / name
        if p.exists():
            try:
                blob = json.loads(p.read_text(encoding="utf-8"))
                if key == "godseye":
                    out["godseye"] = {
                        "fps": blob.get("fps"),
                        "work_ms": blob.get("work_ms"),
                        "lod_scale": blob.get("lod_scale"),
                        "layout_settled": blob.get("layout_settled"),
                        "gpu_path": blob.get("gpu_path"),
                        "drawn_nodes": blob.get("drawn_nodes"),
                        "loaded_nodes": blob.get("loaded_nodes"),
                        "ok": blob.get("ok"),
                        "age_s": round(time.time() - p.stat().st_mtime, 1),
                    }
                else:
                    out["godseye_metrics_file"] = {
                        "fps": blob.get("fps"),
                        "purity": blob.get("purity"),
                        "cloud": blob.get("cloud"),
                        "audit_chain_ok": blob.get("audit_chain_ok"),
                        "age_s": round(time.time() - p.stat().st_mtime, 1),
                    }
            except Exception:
                pass

    # Hooks + profile presence (LOCAL_READY hard signals)
    hooks_dir = _ROOT / "hooks"
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    out["hooks"] = {
        "hooks_json": (hooks_dir / "hooks.json").is_file(),
        "session_start": (hooks_dir / "session_start.py").is_file(),
        "stop_validate": (hooks_dir / "stop_validate.py").is_file(),
        "user_prompt_submit": (hooks_dir / "user_prompt_submit.py").is_file(),
        "beast_profile": (codex_home / "beast.config.toml").is_file()
        or (codex_home / "beast-enterprise.config.toml").is_file(),
    }
    out["hooks"]["ok"] = all(
        out["hooks"][k]
        for k in ("hooks_json", "session_start", "stop_validate", "user_prompt_submit")
    )

    # Prior gate reports (age + band) — not re-run
    out["gates"] = {}
    for gname in ("fire_drill", "mission_monday", "doctor", "capabilities"):
        # doctor may be under several names
        candidates = [state / f"{gname}.json"]
        if gname == "doctor":
            candidates = [state / "doctor.json", state / "enterprise_doctor.json", _ROOT / "judge_doctor.json"]
        if gname == "mission_monday":
            candidates = [state / "mission_monday.json", state / "mission.json"]
        for p in candidates:
            if p.exists():
                try:
                    blob = json.loads(p.read_text(encoding="utf-8"))
                    out["gates"][gname] = {
                        "path": str(p.name),
                        "age_s": round(time.time() - p.stat().st_mtime, 1),
                        "ok": blob.get("ok") if "ok" in blob else blob.get("ready"),
                        "band": (blob.get("band") or (blob.get("score") or {}).get("band")
                                 or blob.get("overall")),
                        "score": blob.get("score") if not isinstance(blob.get("score"), dict)
                        else blob.get("score"),
                    }
                    break
                except Exception:
                    pass

    # Vector pack age
    for vp in (
        state / "vectors" / "pack.json",
        _ROOT / ".brain" / "vectors" / "pack.json",
        state / "vector_pack.json",
    ):
        if vp.exists():
            out["vectors"]["pack_age_s"] = round(time.time() - vp.stat().st_mtime, 1)
            out["vectors"]["pack_path"] = str(vp)
            break

    # Cloud endpoints configured?
    out["cloud"] = {
        "neptune": bool(os.environ.get("PB_NEPTUNE_ENDPOINT")),
        "opensearch": bool(os.environ.get("PB_OPENSEARCH_ENDPOINT")),
        "llm_shim": bool(os.environ.get("PB_LLM_BASE_URL")),
        "region": os.environ.get("PB_AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    }
    if out["cloud"]["neptune"] or out["cloud"]["opensearch"]:
        try:
            from infra_test import test_cloud

            checks = test_cloud()
            out["cloud"]["checks"] = [
                {"name": c.get("name"), "ok": c.get("ok"), "detail": str(c.get("detail") or "")[:80]}
                for c in checks
            ]
            out["cloud"]["all_ok"] = all(c.get("ok") for c in checks if not c.get("optional"))
        except Exception as e:
            out["cloud"]["error"] = str(e)[:120]

    # Health rollup
    g = out.get("graph") or {}
    v = out.get("vectors") or {}
    a = out.get("audit") or {}
    pur = out.get("purity") or {}
    sess = out.get("sessions") or {}
    hk = out.get("hooks") or {}
    hard = []
    if not a.get("ok"):
        hard.append("audit_chain")
    if v.get("parity") is False:
        hard.append("vector_parity")
    if not pur.get("pilot_ops_ready") and os.environ.get("PB_ENTERPRISE") == "1":
        hard.append("pilot_ops")
    if not hk.get("ok"):
        hard.append("hooks_missing")
    if int(sess.get("codex_session_nodes") or 0) < 1 and os.environ.get("PB_SESSIONS_EMPTY_ACK", "") not in (
        "1",
        "true",
        "yes",
    ):
        # informational for ops board
        pass

    pts = 0
    pts += 20 if a.get("ok") else 0
    pts += 20 if v.get("parity") else 0
    pts += 15 if int(g.get("nodes") or 0) > 0 else 0
    pts += 15 if pur.get("pilot_ops_ready") else 0
    pts += 10 if pur.get("pilot_ready") else 0
    pts += 10 if int(sess.get("codex_session_nodes") or 0) >= 1 else 0
    pts += 10 if hk.get("ok") else 0
    # soft: recent fire drill green
    fd = (out.get("gates") or {}).get("fire_drill") or {}
    if fd.get("ok") is True or str(fd.get("band") or "").upper() in ("ZERO_FAIL_GREEN", "GREEN", "HEALTHY"):
        pts += 0  # already green elsewhere; no double-count
    out["health"] = {
        "hard_issues": hard,
        "ok": len(hard) == 0,
        "collect_ms": int((time.perf_counter() - t0) * 1000),
    }
    out["score"] = {
        "ops_100": pts,
        "band": "HEALTHY" if pts >= 85 else ("CAUTION" if pts >= 55 else "UNHEALTHY"),
        "max": 100,
        "components": {
            "audit": 20 if a.get("ok") else 0,
            "vector_parity": 20 if v.get("parity") else 0,
            "graph": 15 if int(g.get("nodes") or 0) > 0 else 0,
            "pilot_ops": 15 if pur.get("pilot_ops_ready") else 0,
            "pilot_ready": 10 if pur.get("pilot_ready") else 0,
            "sessions": 10 if int(sess.get("codex_session_nodes") or 0) >= 1 else 0,
            "hooks": 10 if hk.get("ok") else 0,
        },
    }
    return out


def write_metrics(report: dict[str, Any] | None = None) -> Path:
    r = report or collect()
    path = _ROOT / ".brain" / "state" / "ops_metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
    return path


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = collect()
    path = write_metrics(r)
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    else:
        print("==============================================")
        print(" Private Brain — ops metrics")
        print("==============================================")
        sc = r.get("score") or {}
        print(f" band:    {sc.get('band')}  score={sc.get('ops_100')}/{sc.get('max', 100)}")
        if sc.get("components"):
            print(f" comps:   {sc.get('components')}")
        print(f" graph:   nodes={(r.get('graph') or {}).get('nodes')} edges={(r.get('graph') or {}).get('edges')}")
        print(f" vectors: {(r.get('vectors') or {}).get('vectors')} parity={(r.get('vectors') or {}).get('parity')} backend={(r.get('vectors') or {}).get('embed_backend')}")
        pur = r.get("purity") or {}
        print(f" purity:  ship={pur.get('pilot_ready')} strict={pur.get('pilot_ready_strict')} ops={pur.get('pilot_ops_ready')} q={pur.get('quarantine_coverage')} public={pur.get('public_ratio')}")
        print(f" audit:   ok={(r.get('audit') or {}).get('ok')} events={(r.get('audit') or {}).get('events_checked')}")
        print(f" sessions:{(r.get('sessions') or {}).get('codex_session_nodes')}")
        print(f" hooks:   ok={(r.get('hooks') or {}).get('ok')} profile={(r.get('hooks') or {}).get('beast_profile')}")
        ge = r.get("godseye") or {}
        if ge:
            print(f" godseye: fps={ge.get('fps')} settled={ge.get('layout_settled')} gpu={ge.get('gpu_path')} age={ge.get('age_s')}s")
        gates = r.get("gates") or {}
        if gates:
            gsum = {k: f"ok={v.get('ok')} band={v.get('band')} age={v.get('age_s')}s" for k, v in gates.items()}
            print(f" gates:   {gsum}")
        print(f" cloud:   {r.get('cloud')}")
        hard = (r.get("health") or {}).get("hard_issues") or []
        print(f" hard:    {hard if hard else 'none'}")
        print(f" state:   {path}")
        print("==============================================")
    return 0 if (r.get("health") or {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
