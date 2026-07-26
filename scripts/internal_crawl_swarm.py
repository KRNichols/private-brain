#!/usr/bin/env python3
"""Polite multi-agent recursive crawl of internal GitLab / Jira / Confluence.

Designed for AppGate-protected corporate sources (internet may work; tools
sit behind ZTNA). Enterprise blocks public OSS presets/hosts.

Agents (ThreadPoolExecutor — portable to AWS worker tasks later):
  gitlab-topo / gitlab-deep
  jira-topo / jira-deep
  confluence-topo / confluence-deep
  rate-guard (shared min-interval / budget)

Usage:
  PB_ENTERPRISE=1 python internal_crawl_swarm.py \\
    --gitlab https://gitlab.corp.internal/mygroup \\
    --jira https://jira.corp.internal \\
    --confluence https://confluence.corp.internal/wiki \\
    --deep --agents 6

Env tokens (optional, raise rate limits / unlock private):
  GITLAB_TOKEN, JIRA_TOKEN / JIRA_USER+JIRA_TOKEN, CONFLUENCE_TOKEN
  PB_CRAWL_MIN_INTERVAL (default 0.35s)
  PB_CRAWL_MAX_PROJECTS / MAX_ISSUES / MAX_PAGES (defaults scale with --deep/--max)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

os.environ.setdefault("PB_ENTERPRISE", "1")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _min_interval() -> float:
    try:
        return max(0.05, float(os.environ.get("PB_CRAWL_MIN_INTERVAL") or "0.35"))
    except ValueError:
        return 0.35


class PoliteGate:
    """Process-wide polite spacing between HTTP-bound agent work units."""

    def __init__(self, interval: float | None = None) -> None:
        self.interval = interval if interval is not None else _min_interval()
        self._last = 0.0
        import threading

        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            gap = self.interval - (now - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()


GATE = PoliteGate()


def _assert_source(url: str | None, preset: str | None = None) -> None:
    if not url and not preset:
        return
    try:
        from enterprise import assert_ingest_allowed, is_enterprise

        if is_enterprise():
            assert_ingest_allowed(url=url, preset=preset)
    except PermissionError:
        raise
    except Exception as e:
        if os.environ.get("PB_ENTERPRISE") == "1":
            raise PermissionError(f"enterprise ingest gate failed: {e}") from e


def _limits(deep: bool, maximum: bool) -> dict[str, int]:
    # Recursive “everything” still polite — raise with --max
    if maximum:
        return {
            "max_projects": int(os.environ.get("PB_CRAWL_MAX_PROJECTS") or 500),
            "max_mrs": int(os.environ.get("PB_CRAWL_MAX_MRS") or 200),
            "max_issues": int(os.environ.get("PB_CRAWL_MAX_ISSUES") or 2000),
            "max_spaces": int(os.environ.get("PB_CRAWL_MAX_SPACES") or 200),
            "max_pages": int(os.environ.get("PB_CRAWL_MAX_PAGES") or 5000),
        }
    if deep:
        return {
            "max_projects": int(os.environ.get("PB_CRAWL_MAX_PROJECTS") or 80),
            "max_mrs": int(os.environ.get("PB_CRAWL_MAX_MRS") or 60),
            "max_issues": int(os.environ.get("PB_CRAWL_MAX_ISSUES") or 400),
            "max_spaces": int(os.environ.get("PB_CRAWL_MAX_SPACES") or 40),
            "max_pages": int(os.environ.get("PB_CRAWL_MAX_PAGES") or 800),
        }
    return {
        "max_projects": 15,
        "max_mrs": 15,
        "max_issues": 40,
        "max_spaces": 8,
        "max_pages": 40,
    }


def agent_gitlab(url: str, limits: dict[str, int], deep: bool, run_id: str) -> dict[str, Any]:
    GATE.wait()
    _assert_source(url)
    t0 = time.perf_counter()
    from gitlab_ingest import GitLabClient, GitLabIngestor, resolve_from_url

    try:
        resolved = resolve_from_url(url)
    except Exception as e:
        u = urlparse(url)
        instance = f"{u.scheme}://{u.netloc}"
        group = (u.path or "").strip("/") or None
        if not group:
            return {"agent": "gitlab", "ok": False, "error": f"need group path: {e}"}
        resolved = {"instance": instance, "group": group}

    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("PB_GITLAB_TOKEN") or os.environ.get("PRIVATE_TOKEN")
    try:
        client = GitLabClient(
            resolved["instance"],
            token=token,
            min_interval=_min_interval(),
        )
        eng = GitLabIngestor(
            client,
            agent_id=f"swarm-gitlab-{run_id}",
            run_id=run_id,
            deep=deep,
            max_projects=limits["max_projects"],
            max_issues=limits.get("max_issues", 100),
            max_mrs=limits["max_mrs"],
            max_subgroups=max(80, limits["max_projects"]),
            workers=1,  # politeness: one recursive walker per source agent
        )
        result = eng.crawl_group_tree(resolved["group"])
        return {
            "agent": "gitlab-deep",
            "ok": bool(result.get("ok", True)),
            "ms": int((time.perf_counter() - t0) * 1000),
            "resolved": resolved,
            "counts": result.get("counts") or result,
            "run_id": run_id,
        }
    except Exception as e:
        # topology fallback
        from crawl_public import crawl_gitlab

        GATE.wait()
        counts = crawl_gitlab(
            resolved["instance"],
            resolved["group"],
            limits["max_projects"],
            limits["max_mrs"],
            agent_id=f"swarm-gitlab-{run_id}",
            run_id=run_id,
        )
        return {
            "agent": "gitlab-topo",
            "ok": True,
            "ms": int((time.perf_counter() - t0) * 1000),
            "resolved": resolved,
            "counts": counts,
            "deep_error": str(e)[:200],
            "run_id": run_id,
        }


def agent_jira(url: str, limits: dict[str, int], run_id: str) -> dict[str, Any]:
    GATE.wait()
    _assert_source(url)
    t0 = time.perf_counter()
    from crawl_public import crawl_jira
    from ingest_url import detect_kind

    kind = detect_kind(url)
    base = kind.get("base") or url.rstrip("/")
    counts = crawl_jira(
        base,
        limits["max_projects"],
        limits["max_issues"],
        agent_id=f"swarm-jira-{run_id}",
        run_id=run_id,
    )
    return {
        "agent": "jira-deep",
        "ok": True,
        "ms": int((time.perf_counter() - t0) * 1000),
        "base": base,
        "counts": counts,
        "run_id": run_id,
    }


def agent_confluence(url: str, limits: dict[str, int], run_id: str) -> dict[str, Any]:
    GATE.wait()
    _assert_source(url)
    t0 = time.perf_counter()
    from crawl_public import crawl_confluence
    from ingest_url import detect_kind

    kind = detect_kind(url)
    base = kind.get("base") or url.rstrip("/")
    counts = crawl_confluence(
        base,
        limits["max_spaces"],
        limits["max_pages"],
        agent_id=f"swarm-confluence-{run_id}",
        run_id=run_id,
    )
    return {
        "agent": "confluence-deep",
        "ok": True,
        "ms": int((time.perf_counter() - t0) * 1000),
        "base": base,
        "counts": counts,
        "run_id": run_id,
    }


def run_swarm(
    *,
    gitlab: str | None,
    jira: str | None,
    confluence: str | None,
    deep: bool = True,
    maximum: bool = False,
    n_agents: int = 6,
) -> dict[str, Any]:
    """Fan-out multi-agent crawl. Returns combined report."""
    from audit_lib import audit
    from brain_lib import ensure_tree, status

    ensure_tree()
    run_id = f"icrawl-{_ts()}"
    limits = _limits(deep, maximum)
    jobs: list[tuple[str, Callable[[], dict[str, Any]]]] = []

    if gitlab:
        jobs.append(("gitlab", lambda: agent_gitlab(gitlab, limits, deep, run_id)))
    if jira:
        jobs.append(("jira", lambda: agent_jira(jira, limits, run_id)))
    if confluence:
        jobs.append(("confluence", lambda: agent_confluence(confluence, limits, run_id)))

    if not jobs:
        return {"ok": False, "error": "no sources — pass --gitlab/--jira/--confluence", "run_id": run_id}

    # multi-agent: one worker per source family, optional parallel topo+deep later
    workers = max(1, min(n_agents, len(jobs)))
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                errors.append(f"{name}: {e}")
                results.append({"agent": name, "ok": False, "error": str(e)[:300]})

    st = status() or {}
    report = {
        "ok": all(r.get("ok") for r in results) and not errors,
        "run_id": run_id,
        "ms": int((time.perf_counter() - t0) * 1000),
        "deep": deep,
        "max": maximum,
        "limits": limits,
        "min_interval_s": _min_interval(),
        "agents_planned": len(jobs),
        "workers": workers,
        "results": results,
        "errors": errors,
        "graph": {"nodes": st.get("node_count"), "edges": st.get("edge_count")},
        "note": (
            "Polite multi-agent crawl for AppGate-protected internal sources. "
            "Portable to AWS workers (same agent names → SQS/ECS tasks)."
        ),
        "port_aws": {
            "pattern": "one task per agent role; shared polite budget via Redis/Dynamo",
            "roles": ["gitlab-deep", "jira-deep", "confluence-deep", "rate-guard"],
            "region_hint": "gov-region-1",
        },
    }
    try:
        audit(
            "internal_crawl_swarm",
            agent_id="icrawl",
            role="crawler",
            result="ok" if report["ok"] else "partial",
            detail=f"run={run_id} agents={len(results)} errors={len(errors)}",
            props={"run_id": run_id, "ok": report["ok"], "ms": report["ms"]},
        )
    except Exception:
        pass
    # persist
    try:
        from brain_lib import STATE_DIR, write_json

        path = STATE_DIR / "internal_crawl_swarm.json"
        write_json(path, report)
        report["path"] = str(path)
    except Exception:
        pass
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Polite multi-agent internal crawl (GitLab/Jira/Confluence)")
    ap.add_argument("--gitlab", default=os.environ.get("PB_GITLAB_URL"))
    ap.add_argument("--jira", default=os.environ.get("PB_JIRA_URL"))
    ap.add_argument("--confluence", default=os.environ.get("PB_CONFLUENCE_URL"))
    ap.add_argument("--deep", action="store_true", default=True)
    ap.add_argument("--shallow", action="store_true", help="disable deep limits")
    ap.add_argument("--max", action="store_true", help="raise limits (still polite interval)")
    ap.add_argument("--agents", type=int, default=int(os.environ.get("PB_CRAWL_AGENTS") or 6))
    ap.add_argument("--min-interval", type=float, default=None)
    args = ap.parse_args()
    if args.min_interval is not None:
        os.environ["PB_CRAWL_MIN_INTERVAL"] = str(args.min_interval)
        global GATE
        GATE = PoliteGate(args.min_interval)
    deep = not args.shallow
    try:
        report = run_swarm(
            gitlab=args.gitlab,
            jira=args.jira,
            confluence=args.confluence,
            deep=deep,
            maximum=bool(args.max),
            n_agents=max(1, args.agents),
        )
    except PermissionError as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        return 2
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
