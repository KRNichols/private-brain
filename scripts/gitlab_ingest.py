#!/usr/bin/env python3
"""
GitLab power ingest — point at ANY GitLab instance and recursively harvest:

  groups / subgroups / projects
  issues + notes
  merge requests + notes
  wiki pages
  milestones, labels, boards (when API allows)
  repository tree + README / key docs
  releases, pipelines (summary)
  epics (group-level, EE when public)

Everything flows through ingest_bus → node + vector + knowledge_worth + audit.

Presets (largest public bells-and-whistles targets):
  --preset gnome     → https://gitlab.gnome.org  group GNOME
  --preset salsa     → https://salsa.debian.org  group debian
  --preset gitlab    → https://gitlab.com        group gitlab-org
  --preset freexian  → https://salsa.debian.org  group freexian-team

Auth (optional, raises rate limits / unlocks private):
  export GITLAB_TOKEN=...
  or --token

Examples:
  python gitlab_ingest.py --preset gnome --deep --max-projects 25
  python gitlab_ingest.py --instance https://gitlab.example.com --group platform --token $GITLAB_TOKEN --deep
  python gitlab_ingest.py --instance https://salsa.debian.org --group debian --max-projects 40 --max-issues 30 --max-mrs 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from audit_lib import audit
from brain_lib import (
    STATE_DIR,
    build_snapshot,
    ensure_tree,
    read_json,
    resolve_brain_root,
    utc_now,
    write_json,
)
from ingest_bus import ingest_edge, ingest_node

UA = "PrivateBrain-GitLabIngest/2.0 (+filesystem-rag-dag; research)"
PRESETS = {
    "gnome": {
        "instance": "https://gitlab.gnome.org",
        "group": "GNOME",
        "note": "GNOME ecosystem — issues, MRs, wikis heavily populated",
    },
    "salsa": {
        "instance": "https://salsa.debian.org",
        "group": "debian",
        "note": "Debian Salsa — huge public package/group graph",
    },
    "gitlab": {
        "instance": "https://gitlab.com",
        "group": "gitlab-org",
        "note": "GitLab dogfood — every product feature used",
    },
    "freexian": {
        "instance": "https://salsa.debian.org",
        "group": "freexian-team",
        "note": "Active Debian services team on Salsa",
    },
}

# Key source files worth ingesting from repo trees
DOC_NAMES = {
    "readme",
    "readme.md",
    "readme.rst",
    "readme.txt",
    "contributing",
    "contributing.md",
    "changelog",
    "changelog.md",
    "news",
    "news.md",
    "architecture.md",
    "design.md",
    "docs.md",
    "license",
    "copying",
    "security.md",
    "code_of_conduct.md",
}


class GitLabClient:
    """Thin resilient GitLab API client with rate-limit backoff."""

    def __init__(self, base: str, token: str | None = None, min_interval: float = 0.12):
        self.base = base.rstrip("/")
        self.token = token or os.environ.get("GITLAB_TOKEN") or os.environ.get("PRIVATE_TOKEN")
        self.min_interval = min_interval
        self._last = 0.0
        self.calls = 0
        self.errors = 0
        self.headers = {"User-Agent": UA, "Accept": "application/json"}
        if self.token:
            self.headers["PRIVATE-TOKEN"] = self.token

    def _throttle(self) -> None:
        now = time.time()
        wait = self.min_interval - (now - self._last)
        # MVP law: never wait more than PB_GITLAB_INTER_REPO_SEC (default 15s)
        try:
            cap = float(os.environ.get("PB_GITLAB_INTER_REPO_SEC") or "15")
        except ValueError:
            cap = 15.0
        cap = max(0.05, min(15.0, cap))
        if wait > 0:
            time.sleep(min(wait, cap))
        self._last = time.time()

    def get(self, path: str, params: dict | None = None, timeout: int = 45) -> Any:
        if path.startswith("http"):
            url = path
        else:
            url = f"{self.base}/api/v4{path if path.startswith('/') else '/' + path}"
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}{'&' if '?' in url else '?'}{qs}"
        self._throttle()
        req = urllib.request.Request(url, headers=self.headers)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    self.calls += 1
                    raw = resp.read().decode("utf-8", errors="replace")
                    if not raw.strip():
                        return None
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                self.errors += 1
                body = e.read().decode("utf-8", errors="replace")[:200]
                if e.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if e.code in (401, 403, 404):
                    raise RuntimeError(f"HTTP {e.code} {url}: {body}") from e
                raise RuntimeError(f"HTTP {e.code} {url}: {body}") from e
            except Exception as e:
                self.errors += 1
                if attempt < 3:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                raise RuntimeError(f"GET fail {url}: {e}") from e
        return None

    def paginate(
        self,
        path: str,
        params: dict | None = None,
        *,
        max_items: int = 100,
        per_page: int = 50,
        max_pages: int = 40,
    ) -> list[dict]:
        params = dict(params or {})
        params.setdefault("per_page", min(per_page, 100))
        out: list[dict] = []
        page = 1
        while len(out) < max_items and page <= max_pages:
            params["page"] = page
            try:
                batch = self.get(path, params)
            except RuntimeError as e:
                if "HTTP 401" in str(e) or "HTTP 403" in str(e) or "HTTP 404" in str(e):
                    break
                raise
            if not batch:
                break
            if not isinstance(batch, list):
                break
            out.extend(batch)
            if len(batch) < params["per_page"]:
                break
            page += 1
        return out[:max_items]


def host_tag(base: str) -> str:
    host = urllib.parse.urlparse(base).netloc or "gitlab"
    return re.sub(r"[^a-z0-9.-]+", "-", host.lower())


class GitLabIngestor:
    def __init__(
        self,
        client: GitLabClient,
        *,
        agent_id: str,
        run_id: str,
        deep: bool = True,
        max_projects: int = 25,
        max_issues: int = 25,
        max_mrs: int = 15,
        max_notes: int = 12,
        max_wiki: int = 20,
        max_tree: int = 40,
        max_files: int = 6,
        max_subgroups: int = 80,
        workers: int = 1,
    ):
        self.c = client
        self.agent_id = agent_id
        self.run_id = run_id
        self.deep = deep
        self.max_projects = max_projects
        self.max_issues = max_issues
        self.max_mrs = max_mrs
        self.max_notes = max_notes
        self.max_wiki = max_wiki
        self.max_tree = max_tree
        self.max_files = max_files
        self.max_subgroups = max_subgroups
        self.workers = max(1, workers)
        self.host = host_tag(client.base)
        self.counts: dict[str, int] = {
            "groups": 0,
            "projects": 0,
            "issues": 0,
            "mrs": 0,
            "notes": 0,
            "wiki": 0,
            "milestones": 0,
            "labels": 0,
            "boards": 0,
            "files": 0,
            "releases": 0,
            "pipelines": 0,
            "epics": 0,
            "errors": 0,
        }

    def _node(
        self,
        node_id: str,
        *,
        type: str,
        title: str,
        tier: str = "T2",
        uri: str | None = None,
        tags: list[str] | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        content: str | None = None,
        props: dict | None = None,
    ) -> None:
        base_tags = ["gitlab", "ingest", self.host]
        ingest_node(
            node_id,
            type=type,
            source="gitlab",
            title=title or node_id,
            tier=tier,
            uri=uri,
            tags=list(dict.fromkeys(base_tags + (tags or []))),
            labels=labels,
            parent_id=parent_id,
            content=content,
            props={**(props or {}), "instance": self.c.base, "host": self.host},
            agent_id=self.agent_id,
            role="gitlab-ingest",
        )

    def crawl_group_tree(self, group_path: str) -> dict[str, Any]:
        """Recursive group → subgroups → projects → deep harvest."""
        ensure_tree()
        audit(
            "crawl_start",
            agent_id=self.agent_id,
            role="gitlab-ingest",
            run_id=self.run_id,
            detail=f"recursive {self.c.base} group={group_path}",
            props={"deep": self.deep, "max_projects": self.max_projects},
        )
        enc = urllib.parse.quote(group_path, safe="")
        group = self.c.get(f"/groups/{enc}", {"with_projects": "false"})
        if not group:
            raise RuntimeError(f"group not found: {group_path}")

        root_id = self._ingest_group(group, parent_id=None, is_root=True)
        # recursive subgroups
        self._walk_subgroups(group["id"], root_id, depth=0)
        # projects (include all nested subgroups)
        projects = self.c.paginate(
            f"/groups/{group['id']}/projects",
            {
                "include_subgroups": "true",
                "simple": "false",
                "order_by": "last_activity_at",
                "sort": "desc",
                "with_shared": "false",
            },
            max_items=self.max_projects,
            per_page=50,
        )

        # Inter-repo wait between projects. Default 0 (API min_interval already polite).
        # Hard ceiling 15s per MVP law: never wait more than 15s between gitlab repos.
        try:
            inter_repo = float(os.environ.get("PB_GITLAB_INTER_REPO_SEC") or "0")
        except ValueError:
            inter_repo = 0.0
        inter_repo = max(0.0, min(15.0, inter_repo))

        if self.workers > 1 and len(projects) > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as ex:
                futs = [ex.submit(self._ingest_project, p, root_id) for p in projects]
                for f in as_completed(futs):
                    try:
                        f.result()
                    except Exception as e:
                        self.counts["errors"] += 1
                        audit(
                            "crawl_error",
                            agent_id=self.agent_id,
                            role="gitlab-ingest",
                            run_id=self.run_id,
                            result="fail",
                            detail=str(e)[:240],
                        )
        else:
            for i, p in enumerate(projects):
                if i > 0 and inter_repo > 0:
                    time.sleep(inter_repo)
                try:
                    self._ingest_project(p, root_id)
                except Exception as e:
                    self.counts["errors"] += 1
                    audit(
                        "crawl_error",
                        agent_id=self.agent_id,
                        role="gitlab-ingest",
                        run_id=self.run_id,
                        object_id=f"gitlab:project:{p.get('id')}",
                        result="fail",
                        detail=str(e)[:240],
                    )

        # group epics if available (EE)
        if self.deep:
            try:
                self._ingest_epics(group["id"], root_id)
            except Exception:
                pass

        cursors = {}
        cp = STATE_DIR / "cursors.json"
        if cp.exists():
            try:
                cursors = read_json(cp)
            except Exception:
                cursors = {}
        cursors.setdefault("gitlab", {})
        cursors["gitlab"]["last_topo"] = utc_now()
        cursors["gitlab"]["last_instance"] = self.c.base
        cursors["gitlab"]["last_group"] = group_path
        cursors["gitlab"]["last_counts"] = dict(self.counts)
        write_json(cp, cursors)

        snap = build_snapshot(force=True)
        result = {
            "ok": True,
            "instance": self.c.base,
            "group": group_path,
            "group_id": group.get("id"),
            "deep": self.deep,
            "counts": self.counts,
            "api_calls": self.c.calls,
            "api_errors": self.c.errors,
            "snapshot": snap.get("stats"),
            "brain_root": str(resolve_brain_root()),
            "token_used": bool(self.c.token),
        }
        audit(
            "crawl_end",
            agent_id=self.agent_id,
            role="gitlab-ingest",
            run_id=self.run_id,
            result="ok",
            detail=json.dumps(self.counts),
            props=result,
        )
        write_json(STATE_DIR / "last_gitlab_ingest.json", {**result, "ts": utc_now()})
        return result

    def _ingest_group(self, g: dict, parent_id: str | None, is_root: bool = False) -> str:
        gid = f"gitlab:group:{g['id']}"
        self._node(
            gid,
            type="Group" if is_root else "Subgroup",
            title=g.get("full_path") or g.get("name") or gid,
            tier="T2",
            uri=g.get("web_url"),
            parent_id=parent_id,
            tags=["group", (g.get("full_path") or "").split("/")[0]],
            labels=["root-group"] if is_root else ["subgroup"],
            content=g.get("description") or "",
            props={
                "path": g.get("full_path"),
                "visibility": g.get("visibility"),
                "gitlab_id": g.get("id"),
            },
        )
        if parent_id:
            ingest_edge(parent_id, "PARENT_OF", gid, agent_id=self.agent_id)
        self.counts["groups"] += 1
        return gid

    def _walk_subgroups(self, group_id: int, parent_node: str, depth: int) -> None:
        if depth > 6 or self.counts["groups"] >= self.max_subgroups:
            return
        page = 1
        while self.counts["groups"] < self.max_subgroups and page <= 20:
            try:
                batch = self.c.get(
                    f"/groups/{group_id}/subgroups",
                    {"per_page": 50, "page": page},
                )
            except Exception:
                break
            if not batch:
                break
            for sg in batch:
                sid = self._ingest_group(sg, parent_id=parent_node, is_root=False)
                self._walk_subgroups(sg["id"], sid, depth + 1)
                if self.counts["groups"] >= self.max_subgroups:
                    break
            if len(batch) < 50:
                break
            page += 1

    def _ingest_project(self, p: dict, fallback_parent: str) -> None:
        pid_num = p["id"]
        pid = f"gitlab:project:{pid_num}"
        parent = (
            f"gitlab:group:{p['namespace']['id']}"
            if p.get("namespace") and p["namespace"].get("id")
            else fallback_parent
        )
        desc = p.get("description") or ""
        topics = p.get("topics") or p.get("tag_list") or []
        self._node(
            pid,
            type="Project",
            title=p.get("path_with_namespace") or p.get("name") or pid,
            tier="T2",
            uri=p.get("web_url"),
            parent_id=parent,
            tags=["project"] + [str(t).lower() for t in topics[:8]],
            labels=["service"],
            content=desc,
            props={
                "path_with_namespace": p.get("path_with_namespace"),
                "default_branch": p.get("default_branch"),
                "star_count": p.get("star_count"),
                "forks_count": p.get("forks_count"),
                "open_issues_count": p.get("open_issues_count"),
                "last_activity_at": p.get("last_activity_at"),
                "gitlab_id": pid_num,
            },
        )
        ingest_edge(parent, "CONTAINS", pid, agent_id=self.agent_id)
        repo_id = f"gitlab:repo:{pid_num}"
        self._node(
            repo_id,
            type="Repo",
            title=f"{p.get('path') or pid_num}.git",
            tier="T2",
            parent_id=pid,
            tags=["repo"],
            props={"default_branch": p.get("default_branch"), "http_url_to_repo": p.get("http_url_to_repo")},
        )
        ingest_edge(pid, "CONTAINS", repo_id, agent_id=self.agent_id)
        self.counts["projects"] += 1

        if not self.deep:
            return

        # Issues
        try:
            issues = self.c.paginate(
                f"/projects/{pid_num}/issues",
                {"state": "all", "order_by": "updated_at", "sort": "desc"},
                max_items=self.max_issues,
                per_page=min(50, self.max_issues),
            )
            for iss in issues:
                self._ingest_issue(pid_num, pid, iss)
        except Exception:
            self.counts["errors"] += 1

        # MRs
        try:
            mrs = self.c.paginate(
                f"/projects/{pid_num}/merge_requests",
                {"state": "all", "order_by": "updated_at", "sort": "desc"},
                max_items=self.max_mrs,
                per_page=min(50, self.max_mrs),
            )
            for mr in mrs:
                self._ingest_mr(pid_num, pid, mr)
        except Exception:
            self.counts["errors"] += 1

        # Wiki
        try:
            wikis = self.c.get(f"/projects/{pid_num}/wikis", {"with_content": "1"})
            if isinstance(wikis, list):
                for w in wikis[: self.max_wiki]:
                    self._ingest_wiki(pid_num, pid, w)
        except Exception:
            pass

        # Labels / milestones / boards — best effort (often 401 public)
        for kind, path, typ, counter in [
            ("labels", f"/projects/{pid_num}/labels", "Label", "labels"),
            ("milestones", f"/projects/{pid_num}/milestones", "Milestone", "milestones"),
            ("boards", f"/projects/{pid_num}/boards", "Board", "boards"),
        ]:
            try:
                items = self.c.get(path, {"per_page": 50})
                if not isinstance(items, list):
                    continue
                for item in items[:40]:
                    iid = item.get("id") or item.get("name")
                    nid = f"gitlab:{kind}:{pid_num}:{iid}"
                    title = item.get("name") or item.get("title") or str(iid)
                    content = item.get("description") or ""
                    self._node(
                        nid,
                        type=typ,
                        title=title,
                        tier="T2" if typ != "Label" else "T3",
                        parent_id=pid,
                        tags=[kind],
                        content=content[:4000] if content else None,
                        props={"raw_id": iid, "state": item.get("state")},
                    )
                    ingest_edge(pid, f"HAS_{typ.upper()}", nid, agent_id=self.agent_id)
                    self.counts[counter] += 1
            except Exception:
                pass

        # Releases
        try:
            rels = self.c.get(f"/projects/{pid_num}/releases", {"per_page": 10})
            if isinstance(rels, list):
                for r in rels[:10]:
                    tag = r.get("tag_name") or r.get("name")
                    rid = f"gitlab:release:{pid_num}:{tag}"
                    self._node(
                        rid,
                        type="Release",
                        title=r.get("name") or str(tag),
                        tier="T2",
                        uri=r.get("web_url") or (p.get("web_url") and f"{p['web_url']}/-/releases/{tag}"),
                        parent_id=pid,
                        tags=["release"],
                        content=(r.get("description") or "")[:8000],
                        props={"tag": tag, "released_at": r.get("released_at")},
                    )
                    ingest_edge(pid, "HAS_RELEASE", rid, agent_id=self.agent_id)
                    self.counts["releases"] += 1
        except Exception:
            pass

        # Pipelines summary
        try:
            pipes = self.c.get(
                f"/projects/{pid_num}/pipelines",
                {"per_page": 8, "order_by": "updated_at", "sort": "desc"},
            )
            if isinstance(pipes, list) and pipes:
                for pl in pipes[:8]:
                    plid = f"gitlab:pipeline:{pid_num}:{pl.get('id')}"
                    self._node(
                        plid,
                        type="Pipeline",
                        title=f"pipeline #{pl.get('id')} {pl.get('status')}",
                        tier="T3",
                        uri=pl.get("web_url"),
                        parent_id=pid,
                        tags=["pipeline", pl.get("status") or ""],
                        props={
                            "status": pl.get("status"),
                            "ref": pl.get("ref"),
                            "source": pl.get("source"),
                            "created_at": pl.get("created_at"),
                        },
                    )
                    ingest_edge(pid, "HAS_PIPELINE", plid, agent_id=self.agent_id)
                    self.counts["pipelines"] += 1
        except Exception:
            pass

        # Repo tree + key docs
        try:
            self._ingest_repo_docs(pid_num, pid, repo_id, p.get("default_branch") or "main")
        except Exception:
            self.counts["errors"] += 1

    def _ingest_issue(self, pid_num: int, pid: str, iss: dict) -> None:
        iid = iss.get("iid")
        nid = f"gitlab:issue:{pid_num}:{iid}"
        labels = iss.get("labels") or []
        body = iss.get("description") or ""
        self._node(
            nid,
            type="Issue",
            title=iss.get("title") or f"#{iid}",
            tier="T1",
            uri=iss.get("web_url"),
            parent_id=pid,
            tags=["issue"] + [str(l).lower()[:40] for l in labels[:6]],
            content=body[:12000],
            props={
                "iid": iid,
                "state": iss.get("state"),
                "updated_at": iss.get("updated_at"),
                "author": (iss.get("author") or {}).get("username"),
            },
        )
        ingest_edge(pid, "HAS_ISSUE", nid, agent_id=self.agent_id)
        self.counts["issues"] += 1
        # cross-ref issue keys / MRs
        blob = f"{iss.get('title') or ''} {body}"
        for key in set(re.findall(r"\b([A-Z][A-Z0-9]+-\d+)\b", blob)):
            ingest_edge(nid, "REFERENCES", f"jira:issue:{key}", agent_id=self.agent_id)
        self._ingest_notes(f"/projects/{pid_num}/issues/{iid}/notes", nid, "IssueComment")

    def _ingest_mr(self, pid_num: int, pid: str, mr: dict) -> None:
        iid = mr.get("iid")
        mid = f"gitlab:mr:{pid_num}:{iid}"
        body = mr.get("description") or ""
        labels = mr.get("labels") or []
        self._node(
            mid,
            type="MergeRequest",
            title=mr.get("title") or f"!{iid}",
            tier="T2",
            uri=mr.get("web_url"),
            parent_id=pid,
            tags=["mr"] + [str(l).lower()[:40] for l in labels[:6]],
            content=body[:12000],
            props={
                "iid": iid,
                "state": mr.get("state"),
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "merged_at": mr.get("merged_at"),
                "author": (mr.get("author") or {}).get("username"),
            },
        )
        ingest_edge(pid, "HAS_MR", mid, agent_id=self.agent_id)
        self.counts["mrs"] += 1
        blob = f"{mr.get('title') or ''} {body}"
        for key in set(re.findall(r"\b([A-Z][A-Z0-9]+-\d+)\b", blob)):
            ingest_edge(mid, "REFERENCES", f"jira:issue:{key}", agent_id=self.agent_id)
        for m in re.findall(r"#(\d+)", blob):
            ingest_edge(mid, "REFERENCES", f"gitlab:issue:{pid_num}:{m}", agent_id=self.agent_id)
        self._ingest_notes(f"/projects/{pid_num}/merge_requests/{iid}/notes", mid, "MRComment")

    def _ingest_notes(self, path: str, parent_id: str, typ: str) -> None:
        try:
            notes = self.c.paginate(path, {"sort": "desc", "order_by": "updated_at"}, max_items=self.max_notes, per_page=20)
        except Exception:
            return
        for n in notes:
            if n.get("system"):
                continue
            cid = f"gitlab:note:{n.get('id')}"
            author = (n.get("author") or {}).get("username") or "?"
            self._node(
                cid,
                type=typ,
                title=f"comment by {author}",
                tier="T3",
                parent_id=parent_id,
                tags=["comment", "note"],
                content=(n.get("body") or "")[:6000],
                props={"author": author, "created_at": n.get("created_at")},
            )
            ingest_edge(parent_id, "HAS_COMMENT", cid, agent_id=self.agent_id)
            self.counts["notes"] += 1

    def _ingest_wiki(self, pid_num: int, pid: str, w: dict) -> None:
        slug = w.get("slug") or w.get("title") or "home"
        wid = f"gitlab:wiki:{pid_num}:{slug}"
        content = w.get("content") or ""
        # if content missing, fetch page
        if not content and w.get("slug"):
            try:
                page = self.c.get(f"/projects/{pid_num}/wikis/{urllib.parse.quote(str(w['slug']), safe='')}")
                if isinstance(page, dict):
                    content = page.get("content") or ""
                    w = {**w, **page}
            except Exception:
                pass
        self._node(
            wid,
            type="WikiPage",
            title=w.get("title") or slug,
            tier="T0",
            parent_id=pid,
            tags=["wiki", "docs"],
            content=content[:20000],
            props={"slug": slug, "format": w.get("format")},
        )
        ingest_edge(pid, "HAS_WIKI", wid, agent_id=self.agent_id)
        self.counts["wiki"] += 1

    def _ingest_repo_docs(self, pid_num: int, pid: str, repo_id: str, branch: str) -> None:
        try:
            tree = self.c.get(
                f"/projects/{pid_num}/repository/tree",
                {"ref": branch, "per_page": min(100, self.max_tree), "recursive": "false"},
            )
        except Exception:
            # try master
            try:
                tree = self.c.get(
                    f"/projects/{pid_num}/repository/tree",
                    {"ref": "master", "per_page": min(100, self.max_tree)},
                )
                branch = "master"
            except Exception:
                return
        if not isinstance(tree, list):
            return
        # store tree summary node
        names = [t.get("name") for t in tree if t.get("name")]
        tree_id = f"gitlab:tree:{pid_num}:{branch}"
        self._node(
            tree_id,
            type="RepoTree",
            title=f"tree@{branch}",
            tier="T3",
            parent_id=repo_id,
            tags=["tree", "code"],
            content="\n".join(names[:200]),
            props={"branch": branch, "entries": len(names)},
        )
        ingest_edge(repo_id, "HAS_TREE", tree_id, agent_id=self.agent_id)

        files_taken = 0
        for ent in tree:
            if files_taken >= self.max_files:
                break
            if ent.get("type") != "blob":
                continue
            name = (ent.get("name") or "").lower()
            if name not in DOC_NAMES and not name.startswith("readme"):
                continue
            path = ent.get("path") or ent.get("name")
            try:
                # raw file via repository/files
                enc = urllib.parse.quote(path, safe="")
                meta = self.c.get(
                    f"/projects/{pid_num}/repository/files/{enc}",
                    {"ref": branch},
                )
                if not isinstance(meta, dict):
                    continue
                import base64

                raw = meta.get("content") or ""
                if meta.get("encoding") == "base64" and raw:
                    try:
                        text = base64.b64decode(raw).decode("utf-8", errors="replace")
                    except Exception:
                        text = raw
                else:
                    text = raw
                text = text[:30000]
                fid = f"gitlab:file:{pid_num}:{path}"
                self._node(
                    fid,
                    type="SourceFile",
                    title=path,
                    tier="T2",
                    parent_id=repo_id,
                    tags=["code", "doc", name.split(".")[0]],
                    content=text,
                    props={"path": path, "ref": branch, "size": meta.get("size")},
                )
                ingest_edge(repo_id, "CONTAINS_FILE", fid, agent_id=self.agent_id)
                if name.startswith("readme"):
                    ingest_edge(pid, "HAS_README", fid, agent_id=self.agent_id)
                self.counts["files"] += 1
                files_taken += 1
            except Exception:
                continue

    def _ingest_epics(self, group_id: int, root_id: str) -> None:
        try:
            epics = self.c.paginate(f"/groups/{group_id}/epics", max_items=30, per_page=20)
        except Exception:
            return
        for ep in epics:
            eid = f"gitlab:epic:{group_id}:{ep.get('iid') or ep.get('id')}"
            self._node(
                eid,
                type="Epic",
                title=ep.get("title") or eid,
                tier="T1",
                uri=ep.get("web_url"),
                parent_id=root_id,
                tags=["epic", "plan"],
                content=(ep.get("description") or "")[:12000],
                props={"state": ep.get("state"), "iid": ep.get("iid")},
            )
            ingest_edge(root_id, "HAS_EPIC", eid, agent_id=self.agent_id)
            self.counts["epics"] += 1


def resolve_from_url(url: str) -> dict[str, str]:
    """
    Point at any GitLab page URL — find instance + root group/project path.

    Accepts:
      https://gitlab.gnome.org/GNOME
      https://gitlab.gnome.org/GNOME/gimp
      https://salsa.debian.org/debian/monit/-/issues/1
      gitlab.com/gitlab-org/gitlab
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("empty url")
    if "://" not in raw:
        raw = "https://" + raw
    u = urllib.parse.urlparse(raw)
    if not u.netloc:
        raise ValueError(f"bad url: {url}")
    instance = f"{u.scheme or 'https'}://{u.netloc}"
    parts = [p for p in (u.path or "").split("/") if p and p != "-"]
    # strip UI tails: issues, merge_requests, tree, blob, wikis, ...
    stop = {
        "issues", "merge_requests", "mrs", "tree", "blob", "wikis", "pipelines",
        "activity", "commits", "branches", "tags", "releases", "boards", "epics",
        "settings", "edit", "new", "groups", "explore",
    }
    clean: list[str] = []
    for p in parts:
        if p in stop:
            break
        # numeric iid after issues/
        if p.isdigit() and clean:
            break
        clean.append(p)
    if not clean:
        raise ValueError(f"could not find group/project path in {url}")
    # Prefer longest path as group root for recursive crawl (group/subgroup or group/project)
    # For project URLs (2+ segments) use first segment(s) as group root so we crawl siblings too
    if len(clean) >= 2:
        # crawl containing group (all projects under root namespace)
        group = clean[0] if len(clean) == 2 else "/".join(clean[:-1])
        # if looks like org/project, crawl org; if org/team/project crawl org/team
        if len(clean) == 2:
            group = clean[0]
        else:
            group = "/".join(clean[:-1])
    else:
        group = clean[0]
    return {"instance": instance, "group": group, "path_hint": "/".join(clean), "url": url}


def main() -> int:
    ap = argparse.ArgumentParser(description="Recursive GitLab → Private Brain power ingest")
    ap.add_argument("--preset", choices=list(PRESETS), help="Named public mega-instance")
    ap.add_argument("--url", default=os.environ.get("PB_INGEST_URL"), help="Any GitLab URL — auto-finds root group")
    ap.add_argument("--instance", default=os.environ.get("GITLAB_URL"), help="GitLab base URL")
    ap.add_argument("--group", default=os.environ.get("GITLAB_GROUP"), help="Root group path")
    ap.add_argument("--token", default=None, help="PRIVATE-TOKEN (or GITLAB_TOKEN env)")
    ap.add_argument("--deep", action="store_true", default=True, help="Full deep harvest (default on)")
    ap.add_argument("--shallow", action="store_true", help="Groups+projects only")
    ap.add_argument("--max", action="store_true", help="Max capture: higher limits, still polite interval")
    ap.add_argument("--max-projects", type=int, default=20)
    ap.add_argument("--max-issues", type=int, default=20)
    ap.add_argument("--max-mrs", type=int, default=12)
    ap.add_argument("--max-notes", type=int, default=10)
    ap.add_argument("--max-wiki", type=int, default=15)
    ap.add_argument("--max-tree", type=int, default=40)
    ap.add_argument("--max-files", type=int, default=6)
    ap.add_argument("--max-subgroups", type=int, default=60)
    ap.add_argument("--workers", type=int, default=1, help="Parallel project workers (be polite: 1-3)")
    ap.add_argument(
        "--min-interval",
        type=float,
        default=float(os.environ.get("PB_GITLAB_MIN_INTERVAL") or "0.12"),
        help="Seconds between API calls (polite). Capped by PB_GITLAB_INTER_REPO_SEC max 15s.",
    )
    ap.add_argument(
        "--inter-repo-wait",
        type=float,
        default=float(os.environ.get("PB_GITLAB_INTER_REPO_SEC") or "0"),
        help="Seconds to wait between GitLab repos/projects (hard max 15).",
    )
    ap.add_argument("--run-id", default=os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"gl-ingest-{int(time.time())}")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-presets", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose stderr progress")
    args = ap.parse_args()

    if args.list_presets:
        print(json.dumps(PRESETS, indent=2))
        return 0

    instance = args.instance
    group = args.group
    if args.url:
        resolved = resolve_from_url(args.url)
        instance = resolved["instance"]
        group = resolved["group"]
        print(
            f"url→root instance={instance} group={group} (from path {resolved['path_hint']})",
            file=sys.stderr,
        )
    if args.preset:
        p = PRESETS[args.preset]
        instance = instance or p["instance"]
        group = group or p["group"]
        print(f"preset={args.preset}: {p['note']}", file=sys.stderr)

    # Enterprise policy (Corporate Library pilot): block public presets/hosts even for direct Python CLI.
    # Fail closed under PB_ENTERPRISE — never swallow policy errors.
    # CI exception: PB_ALLOW_PUBLIC_INGEST=1 (force-feed / Windows MVP public OSS only).
    if (os.environ.get("PB_ALLOW_PUBLIC_INGEST") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        print("PB_ALLOW_PUBLIC_INGEST=1 — public OSS ingest override active", file=sys.stderr)
    try:
        from enterprise import assert_ingest_allowed
    except Exception as e:
        if (os.environ.get("PB_ENTERPRISE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enterprise",
        } and (os.environ.get("PB_ALLOW_PUBLIC_INGEST") or "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            print(
                f"ERROR: enterprise policy required under PB_ENTERPRISE but unavailable: {e}",
                file=sys.stderr,
            )
            return 2
    else:
        try:
            assert_ingest_allowed(url=instance, preset=args.preset)
        except PermissionError as e:
            # Intelligent path: heal from state → suggest internal URL → pending scenario for Codex ask
            try:
                from ingest_scenario import handle_blocked_ingest

                sc = handle_blocked_ingest(
                    blocked_url=instance or args.url,
                    reason=str(e),
                )
                print(f"ERROR: enterprise policy blocked ingest: {e}", file=sys.stderr)
                if sc.get("suggested_gitlab"):
                    print(
                        f"SELF-HEAL: known internal GitLab from state → {sc['suggested_gitlab']}\n"
                        f"  Re-run: gitlab_ingest.py --url {sc['suggested_gitlab']} ...\n"
                        f"  Or: beastMode -ingestion {sc['suggested_gitlab']}",
                        file=sys.stderr,
                    )
                    # Auto-retry once with healed URL when blocked target was public/unknown
                    healed_u = sc["suggested_gitlab"]
                    if healed_u and healed_u.rstrip("/") != (instance or "").rstrip("/"):
                        print(f"SELF-HEAL retry with {healed_u}", file=sys.stderr)
                        instance = healed_u
                        # re-parse group if needed
                        if not group and args.url:
                            try:
                                resolved = resolve_from_url(healed_u)
                                group = resolved.get("group") or group
                            except Exception:
                                pass
                        try:
                            assert_ingest_allowed(url=instance, preset=None)
                        except PermissionError as e2:
                            print(f"ERROR: healed URL still blocked: {e2}", file=sys.stderr)
                            print(sc.get("inject") or "", file=sys.stderr)
                            return int(sc.get("exit_code") or 2)
                        # fall through with healed instance
                    else:
                        print(sc.get("inject") or "", file=sys.stderr)
                        return int(sc.get("exit_code") or 2)
                else:
                    print(
                        "SCENARIO: no internal hosts in state. Codex must ASK for GitLab/Jira/Confluence URLs "
                        "(synthesizer agent registered). Not a silent nah.",
                        file=sys.stderr,
                    )
                    print(sc.get("inject") or "", file=sys.stderr)
                    return int(sc.get("exit_code") or 2)
            except Exception as se:
                print(f"ERROR: enterprise policy blocked ingest: {e}", file=sys.stderr)
                print(f"ingest_scenario soft-fail: {se}", file=sys.stderr)
                return 2

    if args.max:
        args.max_projects = max(args.max_projects, 80)
        args.max_issues = max(args.max_issues, 40)
        args.max_mrs = max(args.max_mrs, 25)
        args.max_notes = max(args.max_notes, 15)
        args.max_wiki = max(args.max_wiki, 40)
        args.max_tree = max(args.max_tree, 100)
        args.max_files = max(args.max_files, 12)
        args.max_subgroups = max(args.max_subgroups, 200)
        args.workers = max(args.workers, 2)
        args.min_interval = max(0.08, min(args.min_interval, 0.1))
        if args.verbose:
            print("MAX capture limits armed (still rate-limited/polite)", file=sys.stderr)

    if not instance or not group:
        print(
            "Need --url <gitlab-url>, or --instance + --group, or --preset gnome|salsa|gitlab|freexian",
            file=sys.stderr,
        )
        return 2

    ensure_tree()
    os.environ["PRIVATE_BRAIN_RUN_ID"] = args.run_id
    os.environ.setdefault("PRIVATE_BRAIN_AGENT_ID", "gitlab-ingest")
    os.environ.setdefault("PRIVATE_BRAIN_ROLE", "gitlab-ingest")

    # Cap inter-repo wait at 15s (MVP law)
    inter_repo = max(0.0, min(15.0, float(args.inter_repo_wait)))
    os.environ["PB_GITLAB_INTER_REPO_SEC"] = str(inter_repo)
    # Cap API min_interval so throttle never exceeds 15s either
    args.min_interval = max(0.05, min(15.0, float(args.min_interval)))
    client = GitLabClient(instance, token=args.token, min_interval=args.min_interval)
    eng = GitLabIngestor(
        client,
        agent_id="gitlab-ingest-1",
        run_id=args.run_id,
        deep=not args.shallow,
        max_projects=args.max_projects,
        max_issues=args.max_issues,
        max_mrs=args.max_mrs,
        max_notes=args.max_notes,
        max_wiki=args.max_wiki,
        max_tree=args.max_tree,
        max_files=args.max_files,
        max_subgroups=args.max_subgroups,
        workers=args.workers,
    )
    print(f"brain: {resolve_brain_root()}", file=sys.stderr)
    print(f"target: {instance} group={group} deep={not args.shallow}", file=sys.stderr)
    result = eng.crawl_group_tree(group)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        raise
