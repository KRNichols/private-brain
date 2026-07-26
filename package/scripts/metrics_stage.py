#!/usr/bin/env python3
"""
Metrics Stage — Master of Scrum Masters + eng neighbor metrics.

Aggregates delivery, cost, performance, knowledge, security, and planning
artifacts into the filesystem RAG-DAG. Produces burn series, scoreboards,
comment digests, and proposed epic/story nodes.

  python metrics_stage.py snapshot
  python metrics_stage.py sprint --name sprint-current
  python metrics_stage.py pi --name PI-26.1
  python metrics_stage.py review-comments
  python metrics_stage.py plan-propose --theme "resilience"
  python metrics_stage.py full
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from audit_lib import audit
from brain_lib import (
    BRAIN,
    STATE_DIR,
    ensure_tree,
    load_all_edges,
    load_all_nodes,
    status,
    utc_now,
    write_json,
)
from ingest_bus import ingest_edge, ingest_node
from orchestrate import load_cost_state


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26].replace("+00:00", "Z").rstrip("Z") + ("Z" if "T" in s else ""), fmt).replace(
                tzinfo=timezone.utc
            )
        except Exception:
            continue
    return None


def collect_universe() -> dict[str, Any]:
    nodes = load_all_nodes()
    edges = load_all_edges()
    by_type: dict[str, list] = defaultdict(list)
    by_source: dict[str, list] = defaultdict(list)
    for n in nodes:
        by_type[n.get("type") or "?"].append(n)
        by_source[n.get("source") or "?"].append(n)
    deg: dict[str, int] = defaultdict(int)
    for e in edges:
        deg[e["src"]] += 1
        deg[e["dst"]] += 1
    return {
        "nodes": nodes,
        "edges": edges,
        "by_type": by_type,
        "by_source": by_source,
        "degree": deg,
        "status": status(),
    }


def kpi_scoreboard(u: dict[str, Any]) -> dict[str, Any]:
    nodes = u["nodes"]
    st = u["status"]
    cost = load_cost_state()
    worths = [float(n.get("knowledge_worth") or 0) for n in nodes if n.get("knowledge_worth") is not None]
    bands = Counter(n.get("knowledge_band") or "UNRATED" for n in nodes)

    # Low-value operational noise that dragged mean quality yellow on a healthy corpus
    _QUALITY_SKIP = frozenset({
        "SwarmCrumb", "SwarmTag", "SwarmScout", "SwarmRate",
        "CodexArtifact", "SessionTurn", "Pipeline", "Probe", "PerfProbe",
        "CodexThreadMeta", "Note", "Comment", "MRComment",
    })
    content_worths = [
        float(n.get("knowledge_worth") or 0)
        for n in nodes
        if n.get("knowledge_worth") is not None
        and n.get("type") not in _QUALITY_SKIP
        and (n.get("content_path") or n.get("type") in (
            "Issue", "MergeRequest", "WikiPage", "Page", "Epic", "Story",
            "CodexSession", "SourceFile", "Release", "Repo",
        ))
    ]

    issues = u["by_type"].get("Issue", [])
    comments = u["by_type"].get("Comment", []) + u["by_type"].get("MRComment", [])
    mrs = u["by_type"].get("MergeRequest", [])
    pages = u["by_type"].get("Page", [])
    sessions = u["by_type"].get("CodexSession", [])
    stories = u["by_type"].get("Story", [])
    epics = u["by_type"].get("Epic", [])

    # effort / delivery proxies from graph
    open_issues = sum(1 for i in issues if (i.get("props") or {}).get("status", "").lower() not in ("done", "closed", "resolved"))
    # if no status, treat all as open-ish
    if not any((i.get("props") or {}).get("status") for i in issues):
        open_issues = len(issues)

    avg_all = round(sum(worths) / max(1, len(worths)), 2) if worths else 0
    avg_content = (
        round(sum(content_worths) / max(1, len(content_worths)), 2) if content_worths else avg_all
    )
    gold_silver = int(bands.get("GOLD", 0)) + int(bands.get("SILVER", 0))
    rated_n = max(1, sum(bands.values()) or len(worths) or 1)
    gold_silver_frac = gold_silver / rated_n

    kpis = {
        "knowledge_nodes": st.get("node_count"),
        "knowledge_edges": st.get("edge_count"),
        "vectors_proxy": sum(1 for n in nodes if n.get("content_path")),
        "avg_knowledge_worth": avg_all,
        "avg_content_worth": avg_content,
        "gold_silver_frac": round(gold_silver_frac, 3),
        "band_counts": dict(bands),
        "jira_issues": len(issues),
        "jira_comments": len([c for c in comments if c.get("source") == "jira"]),
        "merge_requests": len(mrs),
        "wiki_pages": len(pages),
        "codex_sessions": len(sessions),
        "planned_epics": len(epics),
        "planned_stories": len(stories),
        "open_issue_proxy": open_issues,
        "api_calls_window": cost.get("window_calls"),
        "crawl_batches": cost.get("crawl_batches"),
        "retrieves": cost.get("retrieves"),
        "sources": st.get("by_source"),
    }

    # traffic lights
    def light(val, good, warn) -> str:
        if val >= good:
            return "green"
        if val >= warn:
            return "yellow"
        return "red"

    # Quality: content-bearing avg (not diluted by swarm crumbs / session turns)
    # green if content avg ≥ 45 OR solid gold+silver share OR overall ≥ 40
    if avg_content >= 45 or gold_silver_frac >= 0.18 or avg_all >= 40:
        kq = "green"
    elif avg_content >= 30 or avg_all >= 28:
        kq = "yellow"
    else:
        kq = "red"

    signals = {
        "corpus_health": light(int(kpis["knowledge_nodes"] or 0), 100, 20),
        "knowledge_quality": kq,
        "planning_coverage": light(int(kpis["planned_stories"] or 0) + int(kpis["planned_epics"] or 0), 5, 1),
        "wiki_presence": light(int(kpis["wiki_pages"] or 0), 10, 1),
        "session_harvest": light(int(kpis["codex_sessions"] or 0), 3, 1),
        "cost_budget": "green" if int(cost.get("window_calls") or 0) < int(cost.get("max_api_calls_per_hour") or 500) * 0.8 else "yellow",
    }

    return {"kpis": kpis, "signals": signals, "cost": cost, "ts": utc_now()}


def burn_series(u: dict[str, Any], days: int = 14) -> dict[str, Any]:
    """
    Synthetic burn-up/down from available timestamps on issues/MRs/sessions.
    When Jira status history is absent, use crawled_at/updated_at as event stream.
    """
    nodes = u["nodes"]
    end = _now()
    start = end - timedelta(days=days)
    # events: +scope (issues/stories appeared), +done (closed status or MR merged heuristic)
    daily_scope = Counter()
    daily_done = Counter()

    for n in nodes:
        t = n.get("type")
        if t not in ("Issue", "Story", "MergeRequest", "Epic", "SessionTurn"):
            continue
        ts = _parse_ts(n.get("updated_at") or n.get("crawled_at") or n.get("created_at"))
        if not ts or ts < start:
            continue
        day = ts.strftime("%Y-%m-%d")
        daily_scope[day] += 1
        status = str((n.get("props") or {}).get("status") or "").lower()
        title = (n.get("title") or "").lower()
        if status in ("done", "closed", "resolved", "merged") or "merged" in title or t == "MergeRequest" and status in ("merged", "closed"):
            daily_done[day] += 1

    days_list = []
    cur = start.date()
    end_d = end.date()
    scope_cum = 0
    done_cum = 0
    remaining = []
    while cur <= end_d:
        ds = cur.isoformat()
        scope_cum += daily_scope.get(ds, 0)
        done_cum += daily_done.get(ds, 0)
        # burn-down style remaining = scope_cum - done_cum (floor 0)
        rem = max(0, scope_cum - done_cum)
        days_list.append(
            {
                "date": ds,
                "scope_added": daily_scope.get(ds, 0),
                "done_added": daily_done.get(ds, 0),
                "burn_up_done": done_cum,
                "burn_up_scope": scope_cum,
                "burn_down_remaining": rem,
            }
        )
        remaining.append(rem)
        cur += timedelta(days=1)

    # ideal burn-down line
    if days_list:
        start_rem = days_list[0]["burn_down_remaining"] or days_list[-1]["burn_up_scope"] or 1
        n = max(1, len(days_list) - 1)
        for i, row in enumerate(days_list):
            row["ideal_remaining"] = round(start_rem * (1 - i / n), 2)

    return {
        "window_days": days,
        "series": days_list,
        "note": "Derived from catalog timestamps/status when Jira history not present; improves as deep crawls add status fields.",
    }


def review_comments(u: dict[str, Any], limit: int = 50) -> dict[str, Any]:
    comments = [
        n
        for n in u["nodes"]
        if n.get("type") in ("Comment", "MRComment", "SessionTurn")
        and (n.get("type") != "SessionTurn" or (n.get("props") or {}).get("role") == "user")
    ]
    # load content snippets
    actions = []
    noise = 0
    for c in comments[:200]:
        text = c.get("title") or ""
        cpath = c.get("content_path")
        if cpath:
            fp = BRAIN / cpath
            if fp.exists():
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")[:2000]
                except OSError:
                    pass
        low = text.lower()
        # actionability heuristics
        score = 0
        reasons = []
        for kw, w in (
            ("blocker", 5),
            ("blocked", 5),
            ("risk", 3),
            ("security", 4),
            ("deadline", 3),
            ("customer", 2),
            ("must", 2),
            ("need to", 2),
            ("action:", 4),
            ("todo", 3),
            ("fix", 2),
            ("lgtm", -2),
            ("nit", -1),
            ("+1", -2),
        ):
            if kw in low:
                score += w
                reasons.append(kw)
        if len(text) < 40:
            score -= 2
            noise += 1
        if score >= 3:
            actions.append(
                {
                    "id": c.get("id"),
                    "tier": c.get("tier"),
                    "score": score,
                    "reasons": reasons,
                    "excerpt": re.sub(r"\s+", " ", text)[:240],
                    "parent_id": c.get("parent_id"),
                    "source": c.get("source"),
                }
            )
    actions.sort(key=lambda x: x["score"], reverse=True)
    return {
        "comments_scanned": min(200, len(comments)),
        "actionable": actions[:limit],
        "noise_short": noise,
        "ts": utc_now(),
    }


def wiki_management(u: dict[str, Any]) -> dict[str, Any]:
    pages = u["by_type"].get("Page", [])
    spaces = u["by_type"].get("Space", [])
    stale = []
    for p in pages:
        worth = float(p.get("knowledge_worth") or 0)
        clen = 0
        if p.get("content_path"):
            fp = BRAIN / p["content_path"]
            if fp.exists():
                clen = fp.stat().st_size
        if worth < 35 or clen < 200:
            stale.append(
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "worth": worth,
                    "action": "update_or_archive",
                    "tier": p.get("tier"),
                }
            )
    missing = []
    # if we have many services/projects but few runbooks
    projects = u["by_type"].get("Project", [])
    if len(projects) > len(pages) and len(pages) < 5:
        missing.append(
            {
                "action": "create_runbook_set",
                "detail": f"{len(projects)} projects vs {len(pages)} wiki pages — propose architecture/runbook pages",
            }
        )
    return {
        "spaces": len(spaces),
        "pages": len(pages),
        "stale_or_thin": stale[:30],
        "missing_suggestions": missing,
        "ts": utc_now(),
    }


def engineering_neighbor(u: dict[str, Any]) -> dict[str, Any]:
    """DevSecOps / cloud / data scientist checklist from brain state."""
    try:
        from vector_manager import status as vs

        vec = vs()
    except Exception as e:
        vec = {"error": str(e)[:120]}
    try:
        from backends import load_backend_config, recommend_govcloud

        backend = load_backend_config().to_dict()
        gov = recommend_govcloud().get("summary")
    except Exception as e:
        backend, gov = {"error": str(e)[:120]}, None
    try:
        from audit_lib import scan_content_for_secrets, verify_chain

        chain = verify_chain()
        secrets = scan_content_for_secrets()
    except Exception as e:
        chain, secrets = {"ok": False, "error": str(e)[:120]}, []

    cost = load_cost_state()
    return {
        "devsecops": {
            "audit_chain_ok": chain.get("ok"),
            "secret_pattern_hits": len(secrets),
            "actions": [
                "Rotate any real secrets if hits are not placeholders",
                "Keep audit pack generation in PI Definition of Done",
            ],
        },
        "cloud": {
            "backend": backend,
            "govcloud_guidance": gov,
            "actions": [
                "If PB_OPENSEARCH_ENDPOINT/PB_NEPTUNE_ENDPOINT unset → local-only is fine",
                "gov-region-1: OpenSearch k-NN + Neptune graph + Titan embed preferred",
            ],
        },
        "data_science": {
            "vectors": vec,
            "band_distribution": dict(Counter(n.get("knowledge_band") or "UNRATED" for n in u["nodes"])),
            "actions": [
                "Track GOLD growth as knowledge wealth KPI",
                "Reindex vectors after large crawls",
            ],
        },
        "cost_performance": {
            "cost": cost,
            "actions": [
                "Watch window_calls vs max_api_calls_per_hour",
                "Prefer targeted deep crawl over --all during sprint freeze",
            ],
        },
        "ts": utc_now(),
    }


def plan_propose(u: dict[str, Any], theme: str = "delivery-hardening") -> dict[str, Any]:
    """Create proposed Epic/Story nodes from gaps (not inventing real Jira keys)."""
    board = kpi_scoreboard(u)
    comments = review_comments(u, limit=15)
    wiki = wiki_management(u)
    eng = engineering_neighbor(u)

    epic_id = f"plan:epic:{re.sub(r'[^a-z0-9]+', '-', theme.lower())[:40]}"
    stories = []

    # story ideas from signals
    if board["signals"].get("knowledge_quality") != "green":
        stories.append(("raise-knowledge-worth", "Improve knowledge_worth: promote GOLD pages and fill thin wiki", "T1"))
    if board["signals"].get("planning_coverage") != "green":
        stories.append(("seed-backlog", "Seed backlog stories from open Jira issues + session turns", "T1"))
    if comments.get("actionable"):
        stories.append(("triage-actionable-comments", f"Triage top {min(10, len(comments['actionable']))} actionable comments into stories", "T1"))
    if wiki.get("stale_or_thin"):
        stories.append(("wiki-hygiene", f"Update/archive {len(wiki['stale_or_thin'])} thin/stale wiki pages", "T0"))
    if eng["devsecops"].get("secret_pattern_hits", 0) > 0:
        stories.append(("secret-hygiene", "Review secret-pattern hits and redact/rotate as needed", "T0"))
    if not stories:
        stories.append(("maintain-metrics", "Maintain metrics stage scoreboard and burn charts each sprint", "T2"))

    ingest_node(
        epic_id,
        type="Epic",
        source="metrics",
        title=f"Epic: {theme}",
        tier="T1",
        tags=["metrics", "planning", "epic", "proposed", theme],
        labels=["planning", "scrum"],
        content=f"# Epic: {theme}\n\nProposed by metrics-master from graph gaps.\n\nSignals: {json.dumps(board['signals'])}\n",
        props={"proposed": True, "theme": theme, "ownership": "metrics-master"},
        agent_id="metrics-master",
        role="metrics-master",
    )

    created = []
    for slug, title, tier in stories:
        sid = f"plan:story:{slug}"
        ingest_node(
            sid,
            type="Story",
            source="metrics",
            title=title,
            tier=tier,
            parent_id=epic_id,
            tags=["metrics", "planning", "story", "proposed"],
            labels=["planning", "scrum"],
            content=f"# Story\n\n{title}\n\nAcceptance:\n- Traceable to brain evidence\n- Metric moves green or documented exception\n",
            props={"proposed": True, "epic_id": epic_id, "ownership": "metrics-master"},
            agent_id="metrics-master",
            role="metrics-master",
        )
        ingest_edge(epic_id, "PARENT_OF", sid, agent_id="metrics-master")
        created.append({"id": sid, "title": title, "tier": tier})

    return {"epic_id": epic_id, "stories": created, "theme": theme}


def persist_snapshot(name: str, payload: dict[str, Any]) -> str:
    ensure_tree()
    nid = f"metrics:snapshot:{name}:{utc_now().replace(':', '').replace('-', '')[:15]}"
    body = json.dumps(payload, indent=2, default=str)
    ingest_node(
        nid,
        type="MetricsSnapshot",
        source="metrics",
        title=f"Metrics snapshot {name}",
        tier="T1",
        tags=["metrics", "snapshot", name, "scoreboard"],
        labels=["metrics-master"],
        content=body[:50000],
        props={"snapshot_name": name, "ts": utc_now()},
        agent_id="metrics-master",
        role="metrics-master",
    )
    # also write file for dashboards
    path = STATE_DIR / "metrics" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, payload)
    # markdown scoreboard
    md_path = STATE_DIR / "metrics" / f"{name}.md"
    k = payload.get("scoreboard", {}).get("kpis", {})
    sig = payload.get("scoreboard", {}).get("signals", {})
    lines = [
        f"# Metrics — {name}",
        f"ts: {payload.get('ts')}",
        "",
        "## Signals",
    ]
    for sk, sv in (sig or {}).items():
        lines.append(f"- {sk}: **{sv}**")
    lines += ["", "## KPIs"]
    for kk, kv in (k or {}).items():
        lines.append(f"- {kk}: `{kv}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return nid


def run_snapshot(name: str = "current") -> dict[str, Any]:
    u = collect_universe()
    payload = {
        "ts": utc_now(),
        "scoreboard": kpi_scoreboard(u),
        "burn": burn_series(u),
        "comments": review_comments(u),
        "wiki": wiki_management(u),
        "engineering": engineering_neighbor(u),
    }
    sid = persist_snapshot(name, payload)
    payload["snapshot_node_id"] = sid
    audit(
        "metrics_snapshot",
        agent_id="metrics-master",
        role="metrics-master",
        result="ok",
        object_id=sid,
        detail=name,
        props=payload["scoreboard"]["signals"],
    )
    return payload


def run_sprint(name: str) -> dict[str, Any]:
    snap = run_snapshot(f"sprint-{name}")
    # sprint planning pack
    pack = {
        "sprint": name,
        "goal_suggestions": [],
        "committed_proxy": snap["scoreboard"]["kpis"].get("open_issue_proxy"),
        "velocity_proxy_note": "Velocity requires historical done counts — using burn series done_added sum",
        "burn": snap["burn"],
        "top_actions_from_comments": snap["comments"]["actionable"][:10],
        "wiki_hygiene": snap["wiki"]["stale_or_thin"][:10],
    }
    done_sum = sum(p.get("done_added", 0) for p in snap["burn"]["series"])
    pack["velocity_proxy_14d"] = done_sum
    pack["goal_suggestions"] = [
        "Reduce red/yellow signals on scoreboard",
        "Clear top actionable comment blockers",
        "Close wiki thin-page debt for in-sprint services",
    ]
    sprint_id = f"plan:sprint:{re.sub(r'[^a-z0-9]+', '-', name.lower())[:40]}"
    ingest_node(
        sprint_id,
        type="Sprint",
        source="metrics",
        title=f"Sprint {name}",
        tier="T1",
        tags=["metrics", "sprint", "planning"],
        labels=["scrum", "metrics-master"],
        content=json.dumps(pack, indent=2, default=str)[:40000],
        props={"sprint": name, "velocity_proxy_14d": done_sum},
        agent_id="metrics-master",
        role="metrics-master",
    )
    pack["sprint_node_id"] = sprint_id
    pack["snapshot_node_id"] = snap.get("snapshot_node_id")
    write_json(STATE_DIR / "metrics" / f"sprint-{name}.json", pack)
    return pack


def run_pi(name: str) -> dict[str, Any]:
    snap = run_snapshot(f"pi-{name}")
    eng = snap["engineering"]
    pi = {
        "pi": name,
        "objectives": [
            "Knowledge GOLD growth and wiki coverage for critical services",
            "Predictable delivery: burn-down tracks ideal within 20%",
            "Government Cloud dual-write readiness (OpenSearch+Neptune+Titan) if ATO path open",
            "Session harvest + secret hygiene continuous",
        ],
        "risks": [],
        "scoreboard": snap["scoreboard"]["signals"],
        "capacity_notes": "Capacity not in graph — load PI capacity from team input next",
        "engineering": eng,
        "features_suggested": [
            "Metrics stage automation in Definition of Done",
            "Comment triage SLA (actionable comments < 48h)",
            "Vector reindex after each PI system demo",
        ],
    }
    if snap["scoreboard"]["signals"].get("knowledge_quality") != "green":
        pi["risks"].append({"risk": "Low knowledge_worth average", "mitigation": "Wiki + session promotion sprint"})
    if eng["devsecops"].get("secret_pattern_hits", 0):
        pi["risks"].append({"risk": "Secret pattern hits in corpus", "mitigation": "Security auditor pack + redaction"})

    pi_id = f"plan:pi:{re.sub(r'[^a-z0-9]+', '-', name.lower())[:40]}"
    ingest_node(
        pi_id,
        type="ProgramIncrement",
        source="metrics",
        title=f"PI {name}",
        tier="T1",
        tags=["metrics", "pi", "planning", "safe"],
        labels=["scrum", "metrics-master", "pi-planning"],
        content=json.dumps(pi, indent=2, default=str)[:40000],
        props={"pi": name},
        agent_id="metrics-master",
        role="metrics-master",
    )
    pi["pi_node_id"] = pi_id
    pi["snapshot_node_id"] = snap.get("snapshot_node_id")
    write_json(STATE_DIR / "metrics" / f"pi-{name}.json", pi)
    return pi


def run_full() -> dict[str, Any]:
    u = collect_universe()
    snap = run_snapshot("current")
    sprint = run_sprint("current")
    pi = run_pi("current")
    plan = plan_propose(u, theme="metrics-driven-delivery")
    out = {
        "role": "metrics-master",
        "ok": True,
        "scoreboard": snap["scoreboard"],
        "burn": snap["burn"],
        "comments": {"actionable_count": len(snap["comments"]["actionable"]), "top": snap["comments"]["actionable"][:5]},
        "wiki": snap["wiki"],
        "engineering": snap["engineering"],
        "sprint": {"id": sprint.get("sprint_node_id"), "velocity_proxy_14d": sprint.get("velocity_proxy_14d")},
        "pi": {"id": pi.get("pi_node_id"), "objectives": pi.get("objectives")},
        "plan": plan,
        "ts": utc_now(),
    }
    write_json(STATE_DIR / "metrics" / "full.json", out)
    audit("metrics_full", agent_id="metrics-master", role="metrics-master", result="ok", detail="full stage")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Metrics Stage — Master of Scrum Masters")
    ap.add_argument(
        "cmd",
        choices=["snapshot", "sprint", "pi", "review-comments", "plan-propose", "full", "scoreboard"],
    )
    ap.add_argument("--name", default="current")
    ap.add_argument("--theme", default="delivery-hardening")
    ap.add_argument("--days", type=int, default=14)
    args = ap.parse_args()
    ensure_tree()

    if args.cmd == "snapshot" or args.cmd == "scoreboard":
        out = run_snapshot(args.name)
    elif args.cmd == "sprint":
        out = run_sprint(args.name)
    elif args.cmd == "pi":
        out = run_pi(args.name)
    elif args.cmd == "review-comments":
        out = review_comments(collect_universe())
    elif args.cmd == "plan-propose":
        out = plan_propose(collect_universe(), theme=args.theme)
    else:
        out = run_full()

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
