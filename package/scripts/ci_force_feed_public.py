#!/usr/bin/env python3
"""CI FORCE-FEED — real public open-source data into the RAG-DAG.

No Corporate secrets. Pulls bounded public sources so CI exercises crawl/ingest:

  GitLab   → gitlab.com/gitlab-org (or gnome) via gitlab_ingest + crawl_public
  GitHub   → public org/repo via github_ingest
  Jira     → issues.apache.org/jira via crawl_public
  Confluence → cwiki.apache.org/confluence via crawl_public

Then: reindex vectors, retrieve probe, write report.

Env:
  PB_FORCE_FEED_TINY=1   even smaller limits (default on CI)
  PB_FORCE_FEED_SKIP_GITHUB=1 / SKIP_GITLAB / SKIP_JIRA / SKIP_CONFLUENCE
  GITHUB_TOKEN optional (higher rate limit)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from brain_lib import STATE_DIR, ensure_tree, load_all_nodes, query, utc_now, write_json  # noqa: E402

PASS = 0
FAIL = 0
RESULTS: list[dict[str, Any]] = []


def gate(name: str, ok: bool, detail: str = "", *, hard: bool = True) -> bool:
    """ZERO SOFT: every failure is a FAIL. hard= kwarg ignored."""
    global PASS, FAIL
    hard = True  # law
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({"name": name, "ok": bool(ok), "hard": True, "detail": str(detail)[:500]})
    mark = "OK" if ok else "FAIL"
    extra = f" - {detail[:180]}" if detail and not ok else ""
    print(f"  [{mark}] {name}{extra}")
    return bool(ok)


def _py_run(args: list[str], timeout: int = 600) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    env["PB_ENTERPRISE"] = env.get("PB_ENTERPRISE") or "1"
    env["PB_CI"] = "1"
    try:
        p = subprocess.run(
            [sys.executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_SCRIPTS.parent),
            env=env,
        )
        return {
            "rc": p.returncode,
            "stdout": (p.stdout or "")[-4000:],
            "stderr": (p.stderr or "")[-2000:],
            "ok": p.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "timeout", "ok": False}
    except Exception as e:
        return {"rc": -1, "stdout": "", "stderr": str(e)[:300], "ok": False}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=" * 76)
    print(" CI FORCE-FEED PUBLIC OSS - GitLab · GitHub · Jira · Confluence")
    print("=" * 76)

    ensure_tree()
    tiny = os.environ.get("PB_FORCE_FEED_TINY", "1") in ("1", "true", "yes")
    # bounded for free runners
    gl_projects = 3 if tiny else 8
    gh_repos = 2 if tiny else 6
    jira_issues = 8 if tiny else 25
    conf_pages = 6 if tiny else 20
    conf_spaces = 2 if tiny else 5

    feeds: dict[str, Any] = {"ts": utc_now(), "tiny": tiny, "sources": {}}

    # ── 1. GitLab public ─────────────────────────────────────────
    print("\n## 1 - GitLab public (gitlab-org light)")
    if os.environ.get("PB_FORCE_FEED_SKIP_GITLAB") in ("1", "true", "yes"):
        # ZERO SOFT: skip env is a hard fail in CI — do not pretend pass
        gate("gitlab_feed", False, "PB_FORCE_FEED_SKIP_GITLAB set — skip banned under zero-soft")
        feeds["sources"]["gitlab"] = {"skipped": True, "fail": True}
    else:
        # Prefer gitlab_ingest preset shallow-ish limits
        r = _py_run(
            [
                str(_SCRIPTS / "gitlab_ingest.py"),
                "--instance",
                "https://gitlab.com",
                "--group",
                "gitlab-org",
                "--shallow",
                "--max-projects",
                str(gl_projects),
                "--max-issues",
                "5",
                "--max-mrs",
                "3",
                "--max-subgroups",
                "5",
                "--json",
                "-v",
            ],
            timeout=900,
        )
        # fallback crawl_public gitlab
        if not r.get("ok"):
            print("  gitlab_ingest soft-fail → crawl_public --gitlab")
            r2 = _py_run(
                [
                    str(_SCRIPTS / "crawl_public.py"),
                    "--gitlab",
                    "--gitlab-base",
                    "https://gitlab.com",
                    "--gitlab-group",
                    "gitlab-org",
                    "--max-projects",
                    str(gl_projects),
                    "--max-issues",
                    "8",
                ],
                timeout=600,
            )
            r = r2
        feeds["sources"]["gitlab"] = {"ok": r.get("ok"), "rc": r.get("rc"), "stderr_tail": (r.get("stderr") or "")[-400:]}
        # hard if both paths total fail AND network might work - soft if network blocked
        nodes = load_all_nodes()
        gl_nodes = [n for n in nodes if str(n.get("source") or "").lower() in ("gitlab", "gitlab.com") or "gitlab" in str(n.get("id") or "").lower()]
        gate(
            "gitlab_ingested_nodes",
            len(gl_nodes) > 0 or r.get("ok"),
            f"nodes={len(gl_nodes)} rc={r.get('rc')}",  # network flaky on some runners
        )
        if len(gl_nodes) > 0:
            gate("gitlab_has_graph", True, f"n={len(gl_nodes)}")
        else:
            gate("gitlab_has_graph", False, (r.get("stderr") or r.get("stdout") or "")[:200])

    # ── 2. GitHub public ─────────────────────────────────────────
    print("\n## 2 - GitHub public (cli/cli small)")
    if os.environ.get("PB_FORCE_FEED_SKIP_GITHUB") in ("1", "true", "yes"):
        gate("github_feed", False, "PB_FORCE_FEED_SKIP_GITHUB set — skip banned under zero-soft")
        feeds["sources"]["github"] = {"skipped": True, "fail": True}
    else:
        r = _py_run(
            [
                str(_SCRIPTS / "github_ingest.py"),
                "--repo",
                "cli/cli",
                "--shallow",
                "--max-repos",
                "1",
                "--max-issues",
                str(max(5, gh_repos * 3)),
                "--max-prs",
                "3",
                "--max-files",
                "4",
                "--json",
            ],
            timeout=600,
        )
        # fallback org tiny
        if not r.get("ok"):
            r = _py_run(
                [
                    str(_SCRIPTS / "github_ingest.py"),
                    "--org",
                    "octocat",
                    "--shallow",
                    "--max-repos",
                    str(gh_repos),
                    "--max-issues",
                    "5",
                    "--json",
                ],
                timeout=400,
            )
        feeds["sources"]["github"] = {"ok": r.get("ok"), "rc": r.get("rc"), "stderr_tail": (r.get("stderr") or "")[-400:]}
        nodes = load_all_nodes()
        gh_nodes = [
            n
            for n in nodes
            if str(n.get("source") or "").lower() in ("github", "github.com")
            or "github" in str(n.get("id") or "").lower()
        ]
        gate(
            "github_ingested_nodes",
            len(gh_nodes) > 0 or r.get("ok"),
            f"nodes={len(gh_nodes)} rc={r.get('rc')}",
        )
        gate("github_has_graph", len(gh_nodes) > 0, f"n={len(gh_nodes)}")

    # ── 3. Jira public (Apache) ──────────────────────────────────
    print("\n## 3 - Jira public (issues.apache.org)")
    if os.environ.get("PB_FORCE_FEED_SKIP_JIRA") in ("1", "true", "yes"):
        gate("jira_feed", False, "PB_FORCE_FEED_SKIP_JIRA set — skip banned under zero-soft")
        feeds["sources"]["jira"] = {"skipped": True, "fail": True}
    else:
        r = _py_run(
            [
                str(_SCRIPTS / "crawl_public.py"),
                "--jira",
                "--jira-base",
                "https://issues.apache.org/jira",
                "--max-projects",
                "4",
                "--max-issues",
                str(jira_issues),
            ],
            timeout=600,
        )
        feeds["sources"]["jira"] = {"ok": r.get("ok"), "rc": r.get("rc"), "stderr_tail": (r.get("stderr") or "")[-400:]}
        nodes = load_all_nodes()
        j_nodes = [n for n in nodes if str(n.get("source") or "").lower() == "jira" or str(n.get("id") or "").startswith("jira:")]
        gate(
            "jira_ingested_nodes",
            len(j_nodes) > 0 or r.get("ok"),
            f"nodes={len(j_nodes)} rc={r.get('rc')}",
        )
        gate("jira_has_graph", len(j_nodes) > 0, f"n={len(j_nodes)}")

    # ── 4. Confluence public (Apache cwiki) ──────────────────────
    print("\n## 4 - Confluence public (cwiki.apache.org)")
    if os.environ.get("PB_FORCE_FEED_SKIP_CONFLUENCE") in ("1", "true", "yes"):
        gate("confluence_feed", False, "PB_FORCE_FEED_SKIP_CONFLUENCE set — skip banned under zero-soft")
        feeds["sources"]["confluence"] = {"skipped": True, "fail": True}
    else:
        r = _py_run(
            [
                str(_SCRIPTS / "crawl_public.py"),
                "--confluence",
                "--confluence-base",
                "https://cwiki.apache.org/confluence",
                "--max-spaces",
                str(conf_spaces),
                "--max-pages",
                str(conf_pages),
            ],
            timeout=600,
        )
        feeds["sources"]["confluence"] = {"ok": r.get("ok"), "rc": r.get("rc"), "stderr_tail": (r.get("stderr") or "")[-400:]}
        nodes = load_all_nodes()
        c_nodes = [
            n
            for n in nodes
            if str(n.get("source") or "").lower() == "confluence"
            or str(n.get("id") or "").startswith("confluence:")
        ]
        gate(
            "confluence_ingested_nodes",
            len(c_nodes) > 0 or r.get("ok"),
            f"nodes={len(c_nodes)} rc={r.get('rc')}",
        )
        gate("confluence_has_graph", len(c_nodes) > 0, f"n={len(c_nodes)}")

    # ── 5. Graph must have grown; RAG retrieve works ─────────────
    print("\n## 5 - Graph + RAG retrieve after force-feed")
    nodes = load_all_nodes()
    gate("graph_nodes_gt0", len(nodes) > 0, f"n={len(nodes)}")
    gate("graph_nodes_gt10", len(nodes) >= 10, f"n={len(nodes)}")

    sources = {}
    for n in nodes:
        s = str(n.get("source") or "unknown")
        sources[s] = sources.get(s, 0) + 1
    feeds["graph_source_counts"] = dict(sorted(sources.items(), key=lambda x: -x[1])[:20])
    feeds["graph_total_nodes"] = len(nodes)

    # at least 2 distinct public sources preferred
    publicish = {k for k in sources if k.lower() in ("gitlab", "github", "jira", "confluence") or "gitlab" in k.lower() or "github" in k.lower()}
    gate("multi_source_graph", len(publicish) >= 1, f"sources={sorted(publicish)}")
    gate("multi_source_2plus", len(publicish) >= 2, f"sources={sorted(publicish)}")

    # retrieve probe
    try:
        hits = query("gitlab", limit=8) or query("apache", limit=8) or query("readme", limit=8)
        gate("retrieve_hits", len(hits) > 0, f"hits={len(hits)}")
    except Exception as e:
        gate("retrieve_hits", False, str(e))

    # orchestrate concert against force-fed corpus
    print("\n## 6 - orchestrate concert on force-fed graph")
    r = _py_run(
        [
            str(_SCRIPTS / "orchestrate.py"),
            "concert",
            "--prompt",
            "What open-source projects did we ingest from GitLab GitHub Jira or Confluence? Cite node ids.",
            "--no-crawl",
            "--json",
        ],
        timeout=180,
    )
    gate("concert_rc0", r.get("ok") or r.get("rc") == 0, (r.get("stderr") or "")[:160])
    concert: dict[str, Any] = {}
    out = (r.get("stdout") or "").strip()
    if out.startswith("{"):
        try:
            concert = json.loads(out)
        except json.JSONDecodeError:
            pass
    ret = concert.get("retrieve") or {}
    gate(
        "concert_retrieve_hits",
        int(ret.get("hit_count") or 0) > 0 or bool(ret.get("evidence")),
        str(ret.get("hit_count")),
    )

    # reindex soft
    try:
        from vector_manager import reindex_all

        ri = reindex_all()
        gate("reindex", True, str(ri)[:80])
    except Exception as e:
        gate("reindex", False, str(e))

    feeds["pass"] = PASS
    feeds["fail"] = FAIL
    feeds["results"] = RESULTS
    write_json(STATE_DIR / "CI_FORCE_FEED_PUBLIC.json", feeds)
    try:
        root = Path(__file__).resolve().parents[1]
        (root / ".brain" / "state").mkdir(parents=True, exist_ok=True)
        (root / ".brain" / "state" / "CI_FORCE_FEED_PUBLIC.json").write_text(
            json.dumps(feeds, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass

    # ZERO SOFT: any gate fail OR empty graph OR <2 public sources = RED
    print("\n" + "=" * 76)
    print(f" CI FORCE-FEED: pass={PASS} fail={FAIL} graph_nodes={len(nodes)} sources={feeds.get('graph_source_counts')}")
    if len(nodes) == 0:
        print(" RED - zero nodes after force-feed (network blocked or crawlers broken)")
        print(" BEAST HEAL - retry crawl_public --all tiny")
        _py_run(
            [
                str(_SCRIPTS / "crawl_public.py"),
                "--all",
                "--max-projects",
                "2",
                "--max-issues",
                "5",
                "--max-spaces",
                "1",
                "--max-pages",
                "3",
            ],
            timeout=400,
        )
        nodes2 = load_all_nodes()
        if len(nodes2) == 0:
            return 1
        print(f" HEAL recovered nodes={len(nodes2)}")
        # re-evaluate after heal still requires zero FAIL on gates already recorded
    if FAIL > 0:
        print(f" RED - {FAIL} hard gate failure(s) (zero-soft law — no fail-but-green)")
        for row in RESULTS:
            if not row.get("ok"):
                print(f"   FAIL {row.get('name')}: {str(row.get('detail') or '')[:160]}")
        return 1
    if len(publicish) < 2:
        print(f" RED - need ≥2 public sources, got {sorted(publicish)}")
        return 1
    if len(nodes) < 10:
        print(f" RED - need ≥10 graph nodes, got {len(nodes)}")
        return 1
    print(" GREEN - public OSS force-feed exercised crawl/ingest/RAG (zero soft)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
