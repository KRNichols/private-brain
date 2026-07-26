#!/usr/bin/env python3
"""
Public open-source crawls into the filesystem RAG-DAG (no secrets required).

Multi-source *light* crawl (GitLab + Jira + Confluence topology). For a full
recursive GitLab harvest (issues, MRs, wikis, tree, epics), use gitlab_ingest.py
instead — preferred by orchestrate stage_crawl_gap when PB_GITLAB_PRESET or
GITLAB_URL+GITLAB_GROUP is set:

  python gitlab_ingest.py --preset gnome --deep
  python gitlab_ingest.py --instance https://YOUR/gitlab --group YOUR/group --token $GITLAB_TOKEN --deep

Defaults (override with env or flags):
  GitLab:     https://gitlab.com  group gitlab-org
  Jira:       https://issues.apache.org/jira
  Confluence: https://cwiki.apache.org/confluence

Usage:
  python crawl_public.py --all
  python crawl_public.py --gitlab --max-projects 15
  python crawl_public.py --jira --max-projects 20 --max-issues 40
  python crawl_public.py --confluence --max-spaces 10 --max-pages 30
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
from typing import Any

from audit_lib import audit
from brain_lib import (
    STATE_DIR,
    build_snapshot,
    ensure_tree,
    read_json,
    resolve_brain_root,
    write_edge,
    write_json,
    write_node,
)

UA = "PrivateBrainPublicCrawler/1.0 (+airgapped-dev; educational)"


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 45) -> Any:
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    # Optional tokens if present (corporate later)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if not body:
                return None
            return json.loads(body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code} {url}: {detail}") from e


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_cursors() -> dict:
    ensure_tree()
    p = STATE_DIR / "cursors.json"
    if p.exists():
        return read_json(p)
    return {}


def save_cursors(c: dict) -> None:
    ensure_tree()
    write_json(STATE_DIR / "cursors.json", c)


# ── GitLab ─────────────────────────────────────────────────────


def crawl_gitlab(
    base: str,
    group_path: str,
    max_projects: int,
    max_mrs: int,
    agent_id: str,
    run_id: str,
) -> dict[str, int]:
    base = base.rstrip("/")
    token = os.environ.get("GITLAB_TOKEN")
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token

    audit(
        "crawl_start",
        agent_id=agent_id,
        role="gitlab-topo",
        run_id=run_id,
        detail=f"gitlab group={group_path}",
        props={"base": base, "max_projects": max_projects},
    )

    # Resolve group
    enc = urllib.parse.quote(group_path, safe="")
    group = http_get(f"{base}/api/v4/groups/{enc}?with_projects=false", headers)
    gid = f"gitlab:group:{group['id']}"
    write_node(
        gid,
        type="Group",
        source="gitlab",
        title=group.get("full_path") or group.get("name"),
        tier="T2",
        uri=group.get("web_url"),
        tags=["gitlab", "public-oss", group_path.split("/")[0]],
        labels=["root-group"],
        props={"path": group.get("full_path"), "visibility": group.get("visibility")},
    )
    counts = {"groups": 1, "projects": 0, "mrs": 0, "comments": 0}

    # Subgroups (one level)
    page = 1
    while page <= 5:
        subs = http_get(
            f"{base}/api/v4/groups/{group['id']}/subgroups?per_page=50&page={page}",
            headers,
        )
        if not subs:
            break
        for sg in subs:
            sid = f"gitlab:group:{sg['id']}"
            write_node(
                sid,
                type="Subgroup",
                source="gitlab",
                title=sg.get("full_path") or sg.get("name"),
                tier="T2",
                uri=sg.get("web_url"),
                parent_id=gid,
                tags=["gitlab", "public-oss"],
                props={"path": sg.get("full_path")},
            )
            write_edge(gid, "PARENT_OF", sid)
            counts["groups"] += 1
        if len(subs) < 50:
            break
        page += 1

    # Projects in group (include subgroups)
    page = 1
    projects: list[dict] = []
    while len(projects) < max_projects and page <= 20:
        batch = http_get(
            f"{base}/api/v4/groups/{group['id']}/projects"
            f"?per_page=50&page={page}&include_subgroups=true&simple=true&order_by=last_activity_at",
            headers,
        )
        if not batch:
            break
        for p in batch:
            projects.append(p)
            if len(projects) >= max_projects:
                break
        if len(batch) < 50:
            break
        page += 1
        time.sleep(0.15)

    for p in projects:
        pid = f"gitlab:project:{p['id']}"
        parent = f"gitlab:group:{p['namespace']['id']}" if p.get("namespace") else gid
        write_node(
            pid,
            type="Project",
            source="gitlab",
            title=p.get("path_with_namespace") or p.get("name"),
            tier="T2",
            uri=p.get("web_url"),
            parent_id=parent,
            tags=["gitlab", "public-oss", "project"],
            labels=["service"] if "gitlab" in (p.get("path") or "") else [],
            props={
                "path_with_namespace": p.get("path_with_namespace"),
                "default_branch": p.get("default_branch"),
            },
            content=p.get("description") or "",
        )
        write_edge(parent, "CONTAINS", pid)
        repo_id = f"gitlab:repo:{p['id']}"
        write_node(
            repo_id,
            type="Repo",
            source="gitlab",
            title=f"{p.get('path')}.git",
            tier="T2",
            parent_id=pid,
            tags=["gitlab", "repo"],
        )
        write_edge(pid, "CONTAINS", repo_id)
        counts["projects"] += 1

        # Deep: recent MRs
        try:
            mrs = http_get(
                f"{base}/api/v4/projects/{p['id']}/merge_requests"
                f"?state=all&per_page={min(max_mrs, 20)}&order_by=updated_at",
                headers,
            )
        except Exception as e:
            audit(
                "crawl_error",
                agent_id=agent_id,
                role="gitlab-deep",
                run_id=run_id,
                object_id=pid,
                result="fail",
                detail=str(e)[:200],
            )
            continue
        for mr in mrs or []:
            mid = f"gitlab:mr:{p['id']}:{mr['iid']}"
            body = mr.get("description") or ""
            write_node(
                mid,
                type="MergeRequest",
                source="gitlab",
                title=mr.get("title") or f"!{mr['iid']}",
                tier="T2",
                uri=mr.get("web_url"),
                parent_id=pid,
                tags=["gitlab", "mr", "public-oss"],
                content=body[:12000],
                props={"iid": mr.get("iid"), "state": mr.get("state")},
            )
            write_edge(pid, "HAS_MR", mid)
            counts["mrs"] += 1
            # Jira-like keys in MR text
            for key in set(re.findall(r"\b([A-Z][A-Z0-9]+-\d+)\b", (mr.get("title") or "") + " " + body)):
                write_edge(mid, "REFERENCES", f"jira:issue:{key}")
            # one page of notes
            try:
                notes = http_get(
                    f"{base}/api/v4/projects/{p['id']}/merge_requests/{mr['iid']}/notes?per_page=10",
                    headers,
                )
            except Exception:
                notes = []
            for n in notes or []:
                if n.get("system"):
                    continue
                cid = f"gitlab:mr_comment:{p['id']}:{mr['iid']}:{n['id']}"
                write_node(
                    cid,
                    type="MRComment",
                    source="gitlab",
                    title=f"comment by {(n.get('author') or {}).get('username', '?')}",
                    tier="T3",
                    parent_id=mid,
                    tags=["gitlab", "comment"],
                    content=(n.get("body") or "")[:4000],
                )
                write_edge(mid, "HAS_COMMENT", cid)
                counts["comments"] += 1
        time.sleep(0.1)

    cursors = load_cursors()
    cursors.setdefault("gitlab", {})["last_topo"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cursors["gitlab"]["public_group"] = group_path
    save_cursors(cursors)
    audit(
        "crawl_end",
        agent_id=agent_id,
        role="gitlab-deep",
        run_id=run_id,
        result="ok",
        detail=json.dumps(counts),
        props=counts,
    )
    return counts


# ── Jira (Apache) ──────────────────────────────────────────────


def crawl_jira(
    base: str,
    max_projects: int,
    max_issues: int,
    project_keys: list[str] | None,
    agent_id: str,
    run_id: str,
) -> dict[str, int]:
    base = base.rstrip("/")
    # Apache uses /jira prefix often already in base
    api = base if base.endswith("/jira") or "/rest/" in base else base
    # issues.apache.org/jira
    rest = f"{api}/rest/api/2"

    audit(
        "crawl_start",
        agent_id=agent_id,
        role="jira-topo",
        run_id=run_id,
        detail=f"jira base={base}",
    )
    counts = {"projects": 0, "issues": 0}

    projects = http_get(f"{rest}/project")
    if not isinstance(projects, list):
        raise RuntimeError(f"unexpected jira project payload: {type(projects)}")

    # Prefer known active OSS projects if no filter
    preferred = project_keys or ["KAFKA", "HADOOP", "SPARK", "FLINK", "CASSANDRA", "BEAM", "ARROW", "SOLR"]
    by_key = {p["key"]: p for p in projects if isinstance(p, dict) and "key" in p}
    selected = []
    for k in preferred:
        if k in by_key:
            selected.append(by_key[k])
        if len(selected) >= max_projects:
            break
    if len(selected) < max_projects:
        for p in projects:
            if p not in selected:
                selected.append(p)
            if len(selected) >= max_projects:
                break

    for p in selected:
        key = p["key"]
        jid = f"jira:project:{key}"
        write_node(
            jid,
            type="JiraProject",
            source="jira",
            title=p.get("name") or key,
            tier="T1",
            uri=f"{api}/browse/{key}",
            tags=["jira", "public-oss", key.lower()],
            props={"key": key},
            content=strip_html((p.get("description") or "")[:4000]),
        )
        counts["projects"] += 1

        # recent issues
        jql = urllib.parse.quote(f"project = {key} ORDER BY updated DESC")
        try:
            data = http_get(
                f"{rest}/search?jql={jql}&maxResults={min(20, max_issues)}&fields=summary,description,status,issuetype,updated,comment"
            )
        except Exception as e:
            audit(
                "crawl_error",
                agent_id=agent_id,
                role="jira-deep",
                run_id=run_id,
                object_id=jid,
                result="fail",
                detail=str(e)[:200],
            )
            continue
        for issue in (data or {}).get("issues") or []:
            ikey = issue["key"]
            fields = issue.get("fields") or {}
            iid = f"jira:issue:{ikey}"
            desc = fields.get("description")
            if isinstance(desc, dict):
                # ADF rarely on server v2 - usually string
                desc = json.dumps(desc)[:2000]
            desc_s = strip_html(str(desc or ""))[:8000]
            write_node(
                iid,
                type="Issue",
                source="jira",
                title=fields.get("summary") or ikey,
                tier="T1",
                uri=f"{api}/browse/{ikey}",
                parent_id=jid,
                tags=["jira", "issue", "public-oss", key.lower()],
                content=desc_s,
                props={
                    "status": (fields.get("status") or {}).get("name"),
                    "issuetype": (fields.get("issuetype") or {}).get("name"),
                },
            )
            write_edge(jid, "CONTAINS", iid)
            counts["issues"] += 1
            # comments
            comments = ((fields.get("comment") or {}).get("comments")) or []
            for c in comments[:5]:
                cid = f"jira:comment:{ikey}:{c.get('id')}"
                write_node(
                    cid,
                    type="Comment",
                    source="jira",
                    title=f"comment on {ikey}",
                    tier="T3",
                    parent_id=iid,
                    tags=["jira", "comment"],
                    content=strip_html(str(c.get("body") or ""))[:4000],
                )
                write_edge(iid, "HAS_COMMENT", cid)
        time.sleep(0.2)
        if counts["issues"] >= max_issues:
            break

    cursors = load_cursors()
    cursors.setdefault("jira", {})["last_topo"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cursors["jira"]["public_base"] = base
    save_cursors(cursors)
    audit(
        "crawl_end",
        agent_id=agent_id,
        role="jira-deep",
        run_id=run_id,
        result="ok",
        detail=json.dumps(counts),
        props=counts,
    )
    return counts


# ── Confluence ─────────────────────────────────────────────────


def crawl_confluence(
    base: str,
    max_spaces: int,
    max_pages: int,
    space_keys: list[str] | None,
    agent_id: str,
    run_id: str,
) -> dict[str, int]:
    base = base.rstrip("/")
    # cwiki.apache.org/confluence
    rest = f"{base}/rest/api"

    audit(
        "crawl_start",
        agent_id=agent_id,
        role="confluence-topo",
        run_id=run_id,
        detail=f"confluence base={base}",
    )
    counts = {"spaces": 0, "pages": 0}

    spaces_payload = http_get(f"{rest}/space?limit=50")
    results = (spaces_payload or {}).get("results") or []
    preferred = space_keys or ["KAFKA", "SPARK", "HADOOP", "FLINK", "CASSANDRA", "BEAM"]
    by_key = {s["key"]: s for s in results if "key" in s}
    selected = []
    for k in preferred:
        if k in by_key:
            selected.append(by_key[k])
    for s in results:
        if s not in selected:
            selected.append(s)
        if len(selected) >= max_spaces:
            break

    for s in selected:
        key = s["key"]
        sid = f"confluence:space:{key}"
        write_node(
            sid,
            type="Space",
            source="confluence",
            title=s.get("name") or key,
            tier="T0",
            uri=f"{base}/display/{key}",
            tags=["confluence", "public-oss", key.lower()],
            props={"key": key, "type": s.get("type")},
        )
        counts["spaces"] += 1

        # pages in space
        start = 0
        got = 0
        while got < max(1, max_pages // max(1, len(selected))) and start < 200:
            limit = min(25, max_pages - got)
            data = http_get(
                f"{rest}/content?spaceKey={urllib.parse.quote(key)}&type=page"
                f"&limit={limit}&start={start}&expand=body.storage,space,version"
            )
            pages = (data or {}).get("results") or []
            if not pages:
                break
            for page in pages:
                pid = f"confluence:page:{page['id']}"
                body = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
                text = strip_html(body)[:12000]
                link = (page.get("_links") or {}).get("webui") or ""
                uri = f"{base}{link}" if link.startswith("/") else (link or f"{base}/pages/viewpage.action?pageId={page['id']}")
                write_node(
                    pid,
                    type="Page",
                    source="confluence",
                    title=page.get("title") or pid,
                    tier="T0",
                    uri=uri,
                    parent_id=sid,
                    tags=["confluence", "page", "public-oss", key.lower()],
                    content=text,
                    props={"space": key, "version": (page.get("version") or {}).get("number")},
                )
                write_edge(sid, "CONTAINS", pid)
                counts["pages"] += 1
                got += 1
                if counts["pages"] >= max_pages:
                    break
            if counts["pages"] >= max_pages:
                break
            start += len(pages)
            time.sleep(0.15)
        if counts["pages"] >= max_pages:
            break

    cursors = load_cursors()
    cursors.setdefault("confluence", {})["last_topo"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cursors["confluence"]["public_base"] = base
    save_cursors(cursors)
    audit(
        "crawl_end",
        agent_id=agent_id,
        role="confluence-deep",
        run_id=run_id,
        result="ok",
        detail=json.dumps(counts),
        props=counts,
    )
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--gitlab", action="store_true")
    ap.add_argument("--jira", action="store_true")
    ap.add_argument("--confluence", action="store_true")
    ap.add_argument("--gitlab-base", default=os.environ.get("GITLAB_URL", "https://gitlab.com"))
    ap.add_argument("--gitlab-group", default=os.environ.get("GITLAB_GROUP", "gitlab-org"))
    ap.add_argument("--jira-base", default=os.environ.get("JIRA_URL", "https://issues.apache.org/jira"))
    ap.add_argument(
        "--confluence-base",
        default=os.environ.get("CONFLUENCE_URL", "https://cwiki.apache.org/confluence"),
    )
    ap.add_argument("--max-projects", type=int, default=12)
    ap.add_argument("--max-mrs", type=int, default=5)
    ap.add_argument("--max-issues", type=int, default=40)
    ap.add_argument("--max-spaces", type=int, default=8)
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--run-id", default=os.environ.get("PRIVATE_BRAIN_RUN_ID", "public-crawl"))
    args = ap.parse_args()

    do_gl = args.all or args.gitlab
    do_jira = args.all or args.jira
    do_cf = args.all or args.confluence
    if not (do_gl or do_jira or do_cf):
        do_gl = do_jira = do_cf = True

    ensure_tree()
    run_id = args.run_id
    os.environ["PRIVATE_BRAIN_RUN_ID"] = run_id
    os.environ.setdefault("PRIVATE_BRAIN_AGENT_ID", "public-crawler")
    os.environ.setdefault("PRIVATE_BRAIN_ROLE", "orchestrator")

    print(f"brain root: {resolve_brain_root()}")
    print(f"run_id: {run_id}")
    summary: dict[str, Any] = {}

    if do_gl:
        print("=== GitLab public crawl ===")
        summary["gitlab"] = crawl_gitlab(
            args.gitlab_base,
            args.gitlab_group,
            args.max_projects,
            args.max_mrs,
            "gitlab-public-1",
            run_id,
        )
        print(summary["gitlab"])

    if do_jira:
        print("=== Jira public crawl (Apache) ===")
        summary["jira"] = crawl_jira(
            args.jira_base,
            args.max_projects,
            args.max_issues,
            None,
            "jira-public-1",
            run_id,
        )
        print(summary["jira"])

    if do_cf:
        print("=== Confluence public crawl (Apache cwiki) ===")
        summary["confluence"] = crawl_confluence(
            args.confluence_base,
            args.max_spaces,
            args.max_pages,
            None,
            "confluence-public-1",
            run_id,
        )
        print(summary["confluence"])

    snap = build_snapshot()
    print("snapshot:", snap.get("stats"))
    audit(
        "public_crawl_complete",
        agent_id="orchestrator",
        role="orchestrator",
        run_id=run_id,
        result="ok",
        detail=json.dumps(summary),
        props=summary,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        raise
