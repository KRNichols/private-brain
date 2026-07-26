#!/usr/bin/env python3
"""AWS CodeCommit harvest → Private Brain (when AWS CLI + credentials available).

Uses `aws codecommit` CLI (stdlib subprocess). Regions: gov-region-1 preferred.

  python codecommit_ingest.py --list
  python codecommit_ingest.py --repo my-repo --region gov-region-1
  python codecommit_ingest.py --all --max-repos 30
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from typing import Any

from audit_lib import audit
from brain_lib import ensure_tree, status, utc_now
from ingest_bus import ingest_edge, ingest_node


def aws_json(args: list[str], region: str) -> Any:
    cmd = ["aws", "codecommit", *args, "--region", region, "--output", "json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return {"_error": "aws_cli_missing"}
    if p.returncode != 0:
        return {"_error": (p.stderr or p.stdout or "aws_failed")[:400], "_rc": p.returncode}
    try:
        return json.loads(p.stdout or "null")
    except json.JSONDecodeError:
        return {"_error": "bad_json", "raw": (p.stdout or "")[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description="CodeCommit → Private Brain")
    ap.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("PB_AWS_REGION") or "gov-region-1")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--max-repos", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not shutil.which("aws"):
        print(json.dumps({"ok": False, "error": "aws CLI not on PATH — install AWS CLI + configure profile"}))
        return 2

    ensure_tree()
    agent = "codecommit-ingest"
    region = args.region

    names: list[str] = []
    if args.list or args.all or not args.repo:
        data = aws_json(["list-repositories"], region)
        if isinstance(data, dict) and data.get("_error"):
            print(json.dumps({"ok": False, "error": data.get("_error"), "region": region, "hint": "SSO login / AppGate / profile"}))
            return 2
        repos = (data or {}).get("repositories") or []
        names = [r.get("repositoryName") for r in repos if r.get("repositoryName")]
        if args.list:
            print(json.dumps({"region": region, "repositories": names}, indent=2))
            return 0
        names = names[: args.max_repos]
    if args.repo:
        names = [args.repo]

    if not names:
        print(json.dumps({"ok": False, "error": "no repositories", "region": region}))
        return 1

    audit("crawl_start", agent_id=agent, role="codecommit", detail=f"region={region} n={len(names)}")
    hub = f"codecommit:region:{region}"
    ingest_node(
        hub,
        type="Group",
        source="codecommit",
        title=f"CodeCommit {region}",
        tier="T1",
        labels=["codecommit", "aws"],
        tags=["codecommit", region],
        props={"region": region, "host": "codecommit.amazonaws.com"},
        agent_id=agent,
        role="codecommit",
    )
    results = []
    for name in names:
        meta = aws_json(["get-repository", "--repository-name", name], region)
        if isinstance(meta, dict) and meta.get("_error"):
            results.append({"repo": name, "ok": False, "error": meta.get("_error")})
            continue
        md = (meta or {}).get("repositoryMetadata") or {}
        rid = f"codecommit:repo:{region}:{name}"
        ingest_node(
            rid,
            type="Repo",
            source="codecommit",
            title=name,
            tier="T1",
            content=(md.get("repositoryDescription") or "")[:4000],
            labels=["codecommit", "repo"],
            tags=["codecommit", region],
            props={
                "region": region,
                "arn": md.get("Arn"),
                "clone_http": (md.get("cloneUrlHttp") or "")[:200],
                "host": "codecommit.amazonaws.com",
            },
            agent_id=agent,
            role="codecommit",
        )
        ingest_edge(hub, "CONTAINS", rid, agent_id=agent)
        # branches
        br = aws_json(["list-branches", "--repository-name", name], region)
        branches = (br or {}).get("branches") or []
        for b in branches[:40]:
            bid = f"codecommit:branch:{region}:{name}:{b}"
            ingest_node(
                bid,
                type="Branch",
                source="codecommit",
                title=f"{name}:{b}",
                tier="T2",
                parent_id=rid,
                labels=["codecommit", "branch"],
                tags=["codecommit", "branch"],
                props={"branch": b, "region": region, "host": "codecommit.amazonaws.com"},
                agent_id=agent,
                role="codecommit",
            )
            ingest_edge(rid, "HAS_BRANCH", bid, agent_id=agent)
        results.append({"repo": name, "ok": True, "branches": len(branches)})

    st = status() or {}
    report = {
        "ok": any(r.get("ok") for r in results),
        "region": region,
        "repos": len(names),
        "results": results,
        "brain": {"nodes": st.get("node_count"), "edges": st.get("edge_count"), "by_source": st.get("by_source")},
        "ts": utc_now(),
    }
    audit("crawl_end", agent_id=agent, role="codecommit", result="ok" if report["ok"] else "partial")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
