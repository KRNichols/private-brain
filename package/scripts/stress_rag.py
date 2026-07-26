#!/usr/bin/env python3
"""DAG-RAG stress test — find limiting factors and shut-down cliffs.

Does NOT require network model calls for core RAG (local filesystem).
Optional --gpt51 attempts Codex CLI concerts if available.

  PB_ENTERPRISE=1 python scripts/stress_rag.py
  PB_ENTERPRISE=1 python scripts/stress_rag.py --gpt51 --json

Reports: first soft degrade, first hard fail, recommended max settings.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("PB_ENTERPRISE", "1")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    p = _ROOT / ".brain" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _bench(name: str, fn, *, soft_ms: float, hard_ms: float, hard_err: bool = True) -> dict[str, Any]:
    t0 = time.perf_counter()
    err = None
    result = None
    try:
        result = fn()
        ok = True
    except Exception as e:
        ok = False
        err = f"{type(e).__name__}: {e}"[:240]
    ms = (time.perf_counter() - t0) * 1000
    band = "ok"
    if not ok:
        band = "hard_fail" if hard_err else "soft_fail"
    elif ms >= hard_ms:
        band = "hard_slow"
    elif ms >= soft_ms:
        band = "soft_slow"
    return {
        "name": name,
        "ok": ok and band not in ("hard_fail", "hard_slow"),
        "band": band,
        "ms": round(ms, 1),
        "error": err,
        "detail": result if isinstance(result, (dict, str, int, float, bool, type(None))) else str(result)[:200],
    }


def stage_baseline() -> dict[str, Any]:
    from brain_lib import status
    from vector_manager import status as vs

    s = status() or {}
    v = vs() or {}
    return {
        "nodes": s.get("node_count") or s.get("nodes"),
        "edges": s.get("edge_count") or s.get("edges"),
        "vectors": v.get("vectors"),
        "parity": v.get("parity"),
        "cpu": os.cpu_count(),
        "embed_backend": v.get("embed_backend"),
    }


def stage_query_latency(limits: list[int] | None = None) -> list[dict[str, Any]]:
    from brain_lib import query

    limits = limits or [5, 20, 50, 100, 200]
    prompts = [
        "authentication resilience kafka",
        "aws govcloud opensearch neptune",
        "gitlab merge request pipeline",
        "confluence runbook deploy",
        "session restore codex sideload",
    ]
    out = []
    for lim in limits:
        samples = []
        for p in prompts:
            t0 = time.perf_counter()
            hits = query(p, limit=lim)
            samples.append((time.perf_counter() - t0) * 1000)
        out.append(
            {
                "limit": lim,
                "p50_ms": round(statistics.median(samples), 1),
                "p95_ms": round(sorted(samples)[max(0, int(len(samples) * 0.95) - 1)], 1),
                "max_ms": round(max(samples), 1),
                "mean_ms": round(statistics.mean(samples), 1),
                "hits_last": len(hits) if hits is not None else 0,
            }
        )
    return out


def stage_vector_search(limits: list[int] | None = None) -> list[dict[str, Any]]:
    from vector_manager import search_vectors

    limits = limits or [5, 20, 50, 100]
    out = []
    for lim in limits:
        t0 = time.perf_counter()
        try:
            hits = search_vectors("enterprise pilot rag dag", limit=lim)
            err = None
            n = len(hits or [])
        except Exception as e:
            hits = []
            err = str(e)[:160]
            n = 0
        out.append(
            {
                "limit": lim,
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "hits": n,
                "error": err,
            }
        )
    return out


def stage_concurrent_query(workers: list[int] | None = None) -> list[dict[str, Any]]:
    from brain_lib import query

    workers = workers or [4, 8, 16, 32, 64]
    out = []
    for w in workers:
        t0 = time.perf_counter()
        errors = 0
        lat = []

        def one(i: int) -> float:
            t = time.perf_counter()
            query(f"stress token {i % 17} auth deploy", limit=20)
            return (time.perf_counter() - t) * 1000

        with ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(one, i) for i in range(w * 2)]
            for f in as_completed(futs):
                try:
                    lat.append(f.result())
                except Exception:
                    errors += 1
        wall = (time.perf_counter() - t0) * 1000
        out.append(
            {
                "workers": w,
                "jobs": w * 2,
                "wall_ms": round(wall, 1),
                "p50_ms": round(statistics.median(lat), 1) if lat else None,
                "p95_ms": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 1) if lat else None,
                "errors": errors,
                "qps": round((w * 2) / (wall / 1000), 2) if wall else 0,
            }
        )
    return out


def stage_concurrent_write(writers: list[int] | None = None) -> list[dict[str, Any]]:
    from ingest_bus import ingest_node

    writers = writers or [4, 8, 16, 32]
    rid = f"stress-{int(time.time())}"
    out = []
    for w in writers:
        t0 = time.perf_counter()
        ok = 0
        err = 0

        def one(i: int) -> bool:
            nid = f"stress:write:{rid}:{w}:{i}"
            try:
                ingest_node(
                    nid,
                    type="StressNode",
                    source="stress",
                    title=f"stress {i}",
                    tier="T3",
                    tags=["stress", "bench"],
                    content=f"stress payload {i} " * 20,
                    props={"i": i, "w": w},
                    agent_id=f"stress-{i}",
                    role="stress",
                )
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(one, i) for i in range(w * 3)]
            for f in as_completed(futs):
                if f.result():
                    ok += 1
                else:
                    err += 1
        wall = (time.perf_counter() - t0) * 1000
        out.append(
            {
                "writers": w,
                "jobs": w * 3,
                "ok": ok,
                "errors": err,
                "wall_ms": round(wall, 1),
                "writes_per_s": round(ok / (wall / 1000), 2) if wall else 0,
            }
        )
    return out


def stage_audit_concurrent(n_writers: list[int] | None = None) -> list[dict[str, Any]]:
    from audit_lib import audit, verify_chain

    n_writers = n_writers or [10, 20, 40]
    out = []
    for n in n_writers:
        t0 = time.perf_counter()
        errors = 0

        def one(i: int) -> None:
            audit(
                "stress_event",
                agent_id=f"stress-{i}",
                role="stress",
                result="ok",
                detail=f"stress {i}",
            )

        with ThreadPoolExecutor(max_workers=min(n, 32)) as ex:
            futs = [ex.submit(one, i) for i in range(n)]
            for f in as_completed(futs):
                try:
                    f.result()
                except Exception:
                    errors += 1
        wall = (time.perf_counter() - t0) * 1000
        ch = verify_chain() or {}
        out.append(
            {
                "writers": n,
                "wall_ms": round(wall, 1),
                "errors": errors,
                "chain_ok": ch.get("ok"),
                "events_checked": ch.get("events_checked"),
            }
        )
    return out


def stage_swarm(ns: list[int] | None = None) -> list[dict[str, Any]]:
    from agent_swarm import sweep

    ns = ns or [8, 16, 32, 64]
    out = []
    for n in ns:
        t0 = time.perf_counter()
        try:
            r = sweep(
                "stress rag resilience auth deploy",
                n_agents=n,
                max_workers=min(n, 64),
            )
            err = None
            completed = r.get("completed") if isinstance(r, dict) else None
            expected = r.get("expected") if isinstance(r, dict) else n
            ok = bool(r.get("ok", True)) if isinstance(r, dict) else True
        except Exception as e:
            err = str(e)[:200]
            completed = 0
            expected = n
            ok = False
        wall = (time.perf_counter() - t0) * 1000
        out.append(
            {
                "n_agents": n,
                "wall_ms": round(wall, 1),
                "ok": ok,
                "completed": completed,
                "expected": expected,
                "error": err,
            }
        )
    return out


def stage_concert(prompts: list[str] | None = None) -> list[dict[str, Any]]:
    """Local DAG concert (hooks path) — no external LLM required."""
    from orchestrate import dag_turn

    prompts = prompts or [
        "What is the pilot ready purity path?",
        "Explain vector parity for the brain",
        "How does enterprise quarantine work?",
        "Summarize session ingest policy",
        "Where does AWS gov-region-1 fit?",
    ]
    out = []
    for p in prompts:
        t0 = time.perf_counter()
        try:
            r = dag_turn(p, allow_crawl=False)
            ok = bool(r.get("final_ok", True))
            ctx_len = len(r.get("context") or "")
            err = None
        except Exception as e:
            ok = False
            ctx_len = 0
            err = str(e)[:200]
        out.append(
            {
                "prompt": p[:60],
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "ok": ok,
                "context_chars": ctx_len,
                "error": err,
            }
        )
    return out


def stage_reindex() -> dict[str, Any]:
    from vector_manager import reindex_all, status as vs

    t0 = time.perf_counter()
    try:
        # structural only if full reindex too heavy — still stress lock path
        r = reindex_all(include_structural=True)
        err = None
        ok = True
    except Exception as e:
        r = None
        err = str(e)[:200]
        ok = False
    ms = (time.perf_counter() - t0) * 1000
    v = vs() or {}
    return {
        "ok": ok,
        "ms": round(ms, 1),
        "error": err,
        "vectors_after": v.get("vectors"),
        "parity": v.get("parity"),
        "result_keys": list(r.keys())[:8] if isinstance(r, dict) else None,
    }


def stage_gpt51(n: int = 3) -> dict[str, Any]:
    """Optional: hammer Codex CLI with gpt-5.1 short prompts (costs tokens)."""
    codex = os.environ.get("CODEX_BIN") or "/Applications/ChatGPT.app/Contents/Resources/codex"
    if not Path(codex).exists():
        which = subprocess.run(["which", "codex"], capture_output=True, text=True)
        codex = (which.stdout or "").strip() or codex
    if not Path(codex).exists() and not which.returncode == 0:
        return {"skipped": True, "reason": "codex binary not found"}

    results = []
    for i in range(n):
        prompt = (
            f"Private Brain stress {i}: In one sentence, confirm you see injected evidence "
            f"and would cite node_ids. Reply only: STRESS_OK_{i}"
        )
        cmd = [
            codex,
            "exec",
            "--dangerously-bypass-hook-trust",
            "--dangerously-bypass-approvals-and-sandbox",
            "-p",
            "beast-enterprise",
            "-c",
            'model="gpt-5.1"',
            prompt,
        ]
        t0 = time.perf_counter()
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("PB_STRESS_GPT_TIMEOUT", "180")),
                cwd=str(_ROOT),
                env={**os.environ, "PB_ENTERPRISE": "1", "PRIVATE_BRAIN_HOME": str(_ROOT)},
            )
            wall = (time.perf_counter() - t0) * 1000
            text = (p.stdout or p.stderr or "")[-500:]
            results.append(
                {
                    "i": i,
                    "rc": p.returncode,
                    "ms": round(wall, 1),
                    "ok": p.returncode == 0,
                    "tail": text,
                    "model_rejected": "model" in text.lower() and ("not" in text.lower() or "unknown" in text.lower() or "invalid" in text.lower()),
                }
            )
        except subprocess.TimeoutExpired:
            results.append({"i": i, "ok": False, "error": "timeout", "ms": 180000})
        except Exception as e:
            results.append({"i": i, "ok": False, "error": str(e)[:200]})
    return {"skipped": False, "n": n, "results": results}


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    cliffs = []
    soft = []
    limits = {}

    # query
    for row in report.get("query_latency") or []:
        if row.get("p95_ms", 0) > 2000:
            cliffs.append(f"lexical query limit={row['limit']} p95={row['p95_ms']}ms > 2s")
        elif row.get("p95_ms", 0) > 500:
            soft.append(f"lexical query limit={row['limit']} p95={row['p95_ms']}ms soft")
        limits["max_query_limit_ok"] = row["limit"]

    # concurrent query
    for row in report.get("concurrent_query") or []:
        if row.get("errors", 0) > 0:
            cliffs.append(f"concurrent query workers={row['workers']} errors={row['errors']}")
        if row.get("p95_ms") and row["p95_ms"] > 3000:
            cliffs.append(f"concurrent query workers={row['workers']} p95={row['p95_ms']}ms")
        elif row.get("p95_ms") and row["p95_ms"] > 1000:
            soft.append(f"concurrent query workers={row['workers']} p95 soft")
        else:
            limits["max_query_workers_ok"] = row["workers"]

    # writes
    for row in report.get("concurrent_write") or []:
        if row.get("errors", 0) > row.get("ok", 0) * 0.1:
            cliffs.append(f"write workers={row['writers']} error_rate high ok={row['ok']} err={row['errors']}")
        else:
            limits["max_write_workers_ok"] = row["writers"]

    # audit
    for row in report.get("audit") or []:
        if row.get("chain_ok") is False:
            cliffs.append(f"audit writers={row['writers']} broke chain")
        elif row.get("errors", 0) > 0:
            soft.append(f"audit writers={row['writers']} write errors={row['errors']}")
        else:
            limits["max_audit_writers_ok"] = row["writers"]

    # swarm
    for row in report.get("swarm") or []:
        if not row.get("ok") or row.get("completed") != row.get("expected"):
            cliffs.append(
                f"swarm n={row['n_agents']} ok={row.get('ok')} completed={row.get('completed')}/{row.get('expected')}"
            )
        elif row.get("wall_ms", 0) > 180000:
            soft.append(f"swarm n={row['n_agents']} wall={row['wall_ms']}ms very slow")
        else:
            limits["max_swarm_ok"] = row["n_agents"]

    # concert
    for row in report.get("concert") or []:
        if not row.get("ok"):
            cliffs.append(f"concert failed: {row.get('prompt')} {row.get('error')}")
        elif row.get("ms", 0) > 15000:
            soft.append(f"concert slow {row.get('ms')}ms: {row.get('prompt')}")
        if row.get("context_chars", 0) > 12000:
            soft.append(f"concert context {row.get('context_chars')} chars near inject cap")

    # reindex
    ri = report.get("reindex") or {}
    if ri and not ri.get("ok"):
        cliffs.append(f"reindex failed: {ri.get('error')}")
    elif ri.get("ms", 0) > 120000:
        soft.append(f"reindex {ri.get('ms')}ms > 2min")

    # gpt51
    g = report.get("gpt51") or {}
    if g and not g.get("skipped"):
        fails = [r for r in (g.get("results") or []) if not r.get("ok")]
        if fails:
            cliffs.append(f"gpt-5.1 codex exec failures: {len(fails)}/{g.get('n')}")
        for r in g.get("results") or []:
            if r.get("model_rejected"):
                cliffs.append("gpt-5.1 model slug rejected by Codex account")

    base = report.get("baseline") or {}
    nodes = int(base.get("nodes") or 0)
    return {
        "cliffs": cliffs,
        "soft_degrades": soft,
        "recommended_limits": limits,
        "scale_notes": {
            "nodes": nodes,
            "edges": base.get("edges"),
            "cpu": base.get("cpu"),
            "guidance": (
                "Shut-down cliffs = correctness failures or multi-second stalls under concurrent load. "
                "Soft = still works but UX degrades. Raise PB_MAX_AGENTS only up to max_swarm_ok."
            ),
        },
    }


def run(*, with_gpt51: bool = False, quick: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ts": _ts(),
        "suite": "stress_rag",
        "quick": quick,
        "with_gpt51": with_gpt51,
    }
    print("==============================================")
    print(" DAG-RAG STRESS — find shut-down cliffs")
    print("==============================================")

    print("· baseline…")
    report["baseline"] = stage_baseline()
    print(f"  nodes={report['baseline'].get('nodes')} vectors={report['baseline'].get('vectors')}")

    print("· lexical query latency…")
    report["query_latency"] = stage_query_latency([5, 20, 50] if quick else [5, 20, 50, 100, 200])

    print("· vector search…")
    report["vector_search"] = stage_vector_search([5, 20, 50] if quick else [5, 20, 50, 100])

    print("· concurrent query…")
    report["concurrent_query"] = stage_concurrent_query([4, 8, 16] if quick else [4, 8, 16, 32, 64])

    print("· concurrent write…")
    report["concurrent_write"] = stage_concurrent_write([4, 8, 16] if quick else [4, 8, 16, 32])

    print("· audit concurrent…")
    report["audit"] = stage_audit_concurrent([10, 20] if quick else [10, 20, 40])

    print("· swarm ramp…")
    report["swarm"] = stage_swarm([8, 16] if quick else [8, 16, 32, 64])

    print("· local concert (dag_turn)…")
    report["concert"] = stage_concert(
        None if not quick else ["What is pilot ready?", "Explain quarantine"]
    )

    if not quick:
        print("· reindex…")
        report["reindex"] = stage_reindex()
    else:
        report["reindex"] = {"skipped": True, "reason": "quick"}

    if with_gpt51:
        print("· gpt-5.1 codex exec (optional, tokens)…")
        report["gpt51"] = stage_gpt51(2 if quick else 3)
    else:
        report["gpt51"] = {"skipped": True, "reason": "pass --gpt51 to enable"}

    report["analysis"] = analyze(report)
    path = _state() / "stress_rag.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["path"] = str(path)

    # human summary
    a = report["analysis"]
    print("----------------------------------------------")
    print(" BASELINE:", report["baseline"])
    print(" RECOMMENDED LIMITS:", a.get("recommended_limits"))
    print(" SOFT DEGRADES:")
    for s in a.get("soft_degrades") or ["(none)"]:
        print("  ·", s)
    print(" SHUT-DOWN CLIFFS:")
    for c in a.get("cliffs") or ["(none observed in this run)"]:
        print("  ·", c)
    print(" state:", path)
    print("==============================================")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gpt51", action="store_true", help="Also stress Codex gpt-5.1 exec (uses tokens)")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    r = run(with_gpt51=args.gpt51, quick=args.quick)
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    cliffs = r.get("analysis", {}).get("cliffs") or []
    return 1 if cliffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
