#!/usr/bin/env python3
"""Recursive GitHub harvest → Private Brain RAG-DAG.

Public REST API (stdlib urllib). Optional GITHUB_TOKEN / GH_TOKEN for rate limits.

Examples:
  python github_ingest.py --org torvalds --max-repos 5
  python github_ingest.py --repo microsoft/vscode --deep --max
  python github_ingest.py --org kubernetes --max-repos 40 --max-issues 50 --workers 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from audit_lib import audit
from brain_lib import ensure_tree, resolve_brain_root, status, utc_now
from ingest_bus import ingest_edge, ingest_node

UA = "PrivateBrain-GitHubIngest/1.0 (+filesystem-rag-dag)"


class GitHubClient:
    def __init__(self, token: str | None = None, min_interval: float = 0.15):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.min_interval = min_interval
        self._last = 0.0
        self.calls = 0
        self.errors = 0
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _throttle(self) -> None:
        now = time.time()
        wait = self.min_interval - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def get(self, path: str, params: dict | None = None) -> Any:
        if path.startswith("http"):
            url = path
        else:
            url = f"https://api.github.com{path if path.startswith('/') else '/' + path}"
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}{'&' if '?' in url else '?'}{qs}"
        self._throttle()
        req = urllib.request.Request(url, headers=self.headers)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.calls += 1
                    raw = resp.read().decode("utf-8", errors="replace")
                    return json.loads(raw) if raw.strip() else None
            except urllib.error.HTTPError as e:
                self.errors += 1
                if e.code == 403 and attempt < 4:
                    # rate limit — backoff
                    time.sleep(2 ** attempt * 2)
                    continue
                if e.code == 404:
                    return None
                detail = e.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(f"HTTP {e.code} {url}: {detail}") from e
            except Exception:
                if attempt >= 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        return None

    def paged(self, path: str, params: dict | None = None, max_items: int = 100) -> list:
        params = dict(params or {})
        params.setdefault("per_page", min(100, max_items))
        page = 1
        out: list = []
        while len(out) < max_items:
            params["page"] = page
            batch = self.get(path, params)
            if not batch or not isinstance(batch, list):
                break
            out.extend(batch)
            if len(batch) < params["per_page"]:
                break
            page += 1
            if page > 50:
                break
        return out[:max_items]


def _aid() -> str:
    return os.environ.get("PRIVATE_BRAIN_AGENT_ID") or "github-ingest"


def ingest_repo(c: GitHubClient, full: str, *, deep: bool, max_issues: int, max_prs: int, max_tree: int, max_files: int) -> dict[str, Any]:
    agent = _aid()
    counts = {"issues": 0, "prs": 0, "comments": 0, "files": 0, "releases": 0}
    repo = c.get(f"/repos/{full}")
    if not repo:
        return {"ok": False, "repo": full, "error": "not_found"}
    rid = f"github:repo:{full.replace('/', ':')}"
    ingest_node(
        rid,
        type="Repo",
        source="github",
        title=full,
        tier="T1",
        uri=repo.get("html_url"),
        content=(repo.get("description") or "")[:4000],
        labels=["github", "repo"],
        tags=["github", "ingest", repo.get("language") or "unknown"],
        props={
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "language": repo.get("language"),
            "default_branch": repo.get("default_branch"),
            "host": "github.com",
        },
        agent_id=agent,
        role="github-deep",
    )
    org = full.split("/")[0]
    gid = f"github:org:{org}"
    ingest_node(
        gid,
        type="Group",
        source="github",
        title=org,
        tier="T1",
        uri=f"https://github.com/{org}",
        labels=["github", "org"],
        tags=["github", "org"],
        props={"host": "github.com"},
        agent_id=agent,
        role="github-deep",
    )
    ingest_edge(gid, "CONTAINS", rid, agent_id=agent)

    if not deep:
        return {"ok": True, "repo": full, "counts": counts, "shallow": True}

    # issues
    for iss in c.paged(f"/repos/{full}/issues", {"state": "all", "filter": "all"}, max_issues):
        if iss.get("pull_request"):
            continue
        num = iss.get("number")
        iid = f"github:issue:{full.replace('/', ':')}:{num}"
        body = (iss.get("body") or "")[:6000]
        ingest_node(
            iid,
            type="Issue",
            source="github",
            title=iss.get("title") or f"#{num}",
            tier="T2",
            uri=iss.get("html_url"),
            content=body,
            parent_id=rid,
            labels=["github", "issue"],
            tags=["github", "issue", str(iss.get("state") or "")],
            props={"number": num, "state": iss.get("state"), "host": "github.com"},
            agent_id=agent,
            role="github-deep",
        )
        ingest_edge(rid, "HAS_ISSUE", iid, agent_id=agent)
        counts["issues"] += 1

    # PRs
    for pr in c.paged(f"/repos/{full}/pulls", {"state": "all"}, max_prs):
        num = pr.get("number")
        pid = f"github:pr:{full.replace('/', ':')}:{num}"
        body = (pr.get("body") or "")[:6000]
        ingest_node(
            pid,
            type="MergeRequest",
            source="github",
            title=pr.get("title") or f"PR#{num}",
            tier="T2",
            uri=pr.get("html_url"),
            content=body,
            parent_id=rid,
            labels=["github", "pr"],
            tags=["github", "pr", str(pr.get("state") or "")],
            props={"number": num, "state": pr.get("state"), "host": "github.com"},
            agent_id=agent,
            role="github-deep",
        )
        ingest_edge(rid, "HAS_MR", pid, agent_id=agent)
        counts["prs"] += 1

    # releases
    for rel in c.paged(f"/repos/{full}/releases", max_items=min(30, max_issues)):
        tag = rel.get("tag_name") or rel.get("id")
        nid = f"github:release:{full.replace('/', ':')}:{tag}"
        ingest_node(
            nid,
            type="Release",
            source="github",
            title=str(tag),
            tier="T2",
            uri=rel.get("html_url"),
            content=(rel.get("body") or "")[:4000],
            parent_id=rid,
            labels=["github", "release"],
            tags=["github", "release"],
            props={"tag": tag, "host": "github.com"},
            agent_id=agent,
            role="github-deep",
        )
        ingest_edge(rid, "HAS_RELEASE", nid, agent_id=agent)
        counts["releases"] += 1

    # tree (README / key docs)
    branch = repo.get("default_branch") or "main"
    tree = c.get(f"/repos/{full}/git/trees/{branch}", {"recursive": "1"})
    if tree and isinstance(tree.get("tree"), list):
        tid = f"github:tree:{full.replace('/', ':')}:{branch}"
        ingest_node(
            tid,
            type="RepoTree",
            source="github",
            title=f"{full}@{branch}",
            tier="T2",
            parent_id=rid,
            labels=["github", "tree"],
            tags=["github", "tree"],
            props={"branch": branch, "host": "github.com", "entries": len(tree["tree"])},
            agent_id=agent,
            role="github-deep",
        )
        ingest_edge(rid, "HAS_TREE", tid, agent_id=agent)
        interesting = []
        for ent in tree["tree"]:
            path = ent.get("path") or ""
            if ent.get("type") != "blob":
                continue
            low = path.lower()
            if any(
                x in low
                for x in (
                    "readme",
                    "contributing",
                    "changelog",
                    "architecture",
                    "docs/",
                    ".md",
                    "license",
                    "security",
                )
            ):
                interesting.append(path)
            if len(interesting) >= max_tree:
                break
        for path in interesting[:max_files]:
            # contents API
            enc = urllib.parse.quote(path)
            meta = c.get(f"/repos/{full}/contents/{enc}", {"ref": branch})
            if not meta or not isinstance(meta, dict):
                continue
            content = ""
            if meta.get("encoding") == "base64" and meta.get("content"):
                import base64

                try:
                    content = base64.b64decode(meta["content"]).decode("utf-8", errors="replace")[:8000]
                except Exception:
                    content = ""
            fid = f"github:file:{full.replace('/', ':')}:{path.replace('/', '__')}"
            ingest_node(
                fid,
                type="SourceFile",
                source="github",
                title=path,
                tier="T2",
                uri=meta.get("html_url"),
                content=content,
                parent_id=rid,
                labels=["github", "file"],
                tags=["github", "file"],
                props={"path": path, "host": "github.com"},
                agent_id=agent,
                role="github-deep",
            )
            ingest_edge(rid, "CONTAINS_FILE", fid, agent_id=agent)
            counts["files"] += 1

    return {"ok": True, "repo": full, "counts": counts, "api_calls": c.calls}


def list_org_repos(c: GitHubClient, org: str, max_repos: int) -> list[str]:
    repos = c.paged(f"/orgs/{org}/repos", {"type": "public", "sort": "updated"}, max_repos)
    if not repos:
        repos = c.paged(f"/users/{org}/repos", {"type": "public", "sort": "updated"}, max_repos)
    out = []
    for r in repos or []:
        if r.get("full_name"):
            out.append(r["full_name"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub → Private Brain power ingest")
    ap.add_argument("--org", default=None, help="GitHub org or user")
    ap.add_argument("--repo", default=None, help="owner/name")
    ap.add_argument("--deep", action="store_true", default=True)
    ap.add_argument("--shallow", action="store_true")
    ap.add_argument("--max", action="store_true")
    ap.add_argument("--max-repos", type=int, default=15)
    ap.add_argument("--max-issues", type=int, default=30)
    ap.add_argument("--max-prs", type=int, default=20)
    ap.add_argument("--max-tree", type=int, default=80)
    ap.add_argument("--max-files", type=int, default=12)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--min-interval", type=float, default=0.12)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    # load-test mode: allow public even if PB_ENTERPRISE leftover
    if os.environ.get("PB_ALLOW_PUBLIC_INGEST", "").lower() in ("1", "true", "yes"):
        os.environ["PB_ENTERPRISE"] = "0"

    if args.max:
        args.max_repos = max(args.max_repos, 40)
        args.max_issues = max(args.max_issues, 60)
        args.max_prs = max(args.max_prs, 40)
        args.max_tree = max(args.max_tree, 120)
        args.max_files = max(args.max_files, 20)
        args.workers = max(args.workers, 2)
        args.min_interval = min(args.min_interval, 0.1)

    deep = not args.shallow
    ensure_tree()
    c = GitHubClient(min_interval=args.min_interval)
    repos: list[str] = []
    if args.repo:
        repos = [args.repo.strip()]
    elif args.org:
        repos = list_org_repos(c, args.org.strip(), args.max_repos)
    else:
        print("Need --org or --repo", file=sys.stderr)
        return 2

    if args.verbose:
        print(f"brain={resolve_brain_root()} repos={len(repos)} deep={deep} token={'yes' if c.token else 'no'}", file=sys.stderr)

    audit("crawl_start", agent_id=_aid(), role="github-ingest", detail=f"repos={len(repos)}")
    results = []
    workers = max(1, min(args.workers, 4))

    def job(full: str) -> dict:
        if args.verbose:
            print(f"  repo {full}", file=sys.stderr)
        return ingest_repo(
            c,
            full,
            deep=deep,
            max_issues=args.max_issues,
            max_prs=args.max_prs,
            max_tree=args.max_tree,
            max_files=args.max_files,
        )

    if workers == 1:
        for r in repos:
            try:
                results.append(job(r))
            except Exception as e:
                results.append({"ok": False, "repo": r, "error": str(e)[:200]})
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(job, r): r for r in repos}
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"ok": False, "repo": futs[fut], "error": str(e)[:200]})

    st = status() or {}
    report = {
        "ok": any(r.get("ok") for r in results),
        "repos": len(repos),
        "results": results[:50],
        "api_calls": c.calls,
        "api_errors": c.errors,
        "brain": {"nodes": st.get("node_count"), "edges": st.get("edge_count"), "by_source": st.get("by_source")},
        "ts": utc_now(),
    }
    audit("crawl_end", agent_id=_aid(), role="github-ingest", result="ok" if report["ok"] else "partial", detail=f"repos={len(repos)}")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
