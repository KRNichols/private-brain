#!/usr/bin/env python3
"""General heal → ask-once → synthesize for pilot soft/dead-end paths.

Surfaces (max 64-agent swarm can fan these as role scopes later):
  ingest_hosts   — GitLab/Jira/Confluence URLs (public blocked / unknown)
  tokens         — GITLAB/JIRA/CONFLUENCE tokens missing for private API
  package_index  — PIP_INDEX_URL / Corporate Library / Protected Gateway
  aws_cloud      — AWS_PROFILE / region / LLM shim / OpenSearch / Neptune
  sessions       — no Codex sessions harvested
  godseye        — pygame/GL missing; headless continue or install path
  codex_cli      — codex binary missing (point at install-loop / pin)

Law:
  1. HEAL from env, day1_map, golden_config, allowlist, secrets_store — no human
  2. If still open + interactive: write pending_scenario + ASK once (Codex conversation)
  3. Register synthesizer (or role) agent JSON for orchestrator fan-out (cap 64)
  4. Never invent hosts/tokens; never soft-pass a hard corporate block in CI without ALLOW_PUBLIC
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _interactive() -> bool:
    if (os.environ.get("PB_CI") or "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if (os.environ.get("PB_NONINTERACTIVE") or "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return True


def _state() -> Path:
    from brain_lib import STATE_DIR

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _safe_url(u: str) -> str:
    if not u:
        return ""
    try:
        p = urlparse(str(u).strip())
        if not p.scheme or not p.netloc:
            return ""
        return f"{p.scheme}://{p.netloc}{(p.path or '').rstrip('/')}"
    except Exception:
        return ""


def _j(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _day1_golden_blobs() -> tuple[dict[str, Any], dict[str, Any]]:
    st = _state()
    day1 = _j(st / "day1_map.json")
    golden = _j(st / "golden_config.json")
    answers = day1.get("answers") if isinstance(day1.get("answers"), dict) else day1
    envg = golden.get("env") if isinstance(golden.get("env"), dict) else golden
    return answers or {}, envg or {}


def heal_ingest_hosts() -> dict[str, str]:
    found: dict[str, str] = {}
    for key, name in (
        ("PB_GITLAB_URL", "gitlab"),
        ("GITLAB_URL", "gitlab"),
        ("PB_JIRA_URL", "jira"),
        ("JIRA_URL", "jira"),
        ("PB_CONFLUENCE_URL", "confluence"),
        ("CONFLUENCE_URL", "confluence"),
    ):
        u = _safe_url(os.environ.get(key) or "")
        if u and name not in found:
            found[name] = u
    day1, envg = _day1_golden_blobs()
    for name, keys in (
        ("gitlab", ("gitlab_url", "gitlab", "PB_GITLAB_URL")),
        ("jira", ("jira_url", "jira", "PB_JIRA_URL")),
        ("confluence", ("confluence_url", "confluence", "PB_CONFLUENCE_URL")),
    ):
        if name in found:
            continue
        for k in keys:
            u = _safe_url(str(day1.get(k) or envg.get(k) or ""))
            if u:
                found[name] = u
                break
    try:
        from enterprise import load_policy

        for h in [str(x).lower() for x in (load_policy().get("allowlist_hosts") or []) if x]:
            if "gitlab" in h and "gitlab" not in found:
                found["gitlab"] = f"https://{h}"
            if "jira" in h and "jira" not in found:
                found["jira"] = f"https://{h}"
            if ("confluence" in h or "wiki" in h) and "confluence" not in found:
                found["confluence"] = f"https://{h}"
    except Exception:
        pass
    return found


def heal_tokens() -> dict[str, bool]:
    """Presence only — never print secret values."""
    keys = {
        "gitlab": ("GITLAB_TOKEN", "PB_GITLAB_TOKEN", "PRIVATE_TOKEN"),
        "jira": ("JIRA_TOKEN", "PB_JIRA_TOKEN"),
        "confluence": ("CONFLUENCE_TOKEN", "PB_CONFLUENCE_TOKEN"),
        "github": ("GITHUB_TOKEN", "GH_TOKEN"),
    }
    out: dict[str, bool] = {}
    for name, envs in keys.items():
        out[name] = any(bool((os.environ.get(e) or "").strip()) for e in envs)
    # secrets_store presence (not values)
    try:
        from secrets_store import list_keys  # type: ignore

        sk = {str(k).lower() for k in (list_keys() or [])}
        for name in out:
            if not out[name] and any(name in k or k in name for k in sk):
                out[name] = True
                out[f"{name}_from_store"] = True  # type: ignore
    except Exception:
        pass
    return out


def heal_package_index() -> dict[str, str]:
    found: dict[str, str] = {}
    for k in ("PIP_INDEX_URL", "PB_PIP_INDEX_URL", "UV_INDEX_URL"):
        v = (os.environ.get(k) or "").strip()
        if v:
            found["pip_index"] = _safe_url(v) or v.split("?")[0]
            break
    day1, envg = _day1_golden_blobs()
    if "pip_index" not in found:
        for k in ("pip_index", "PIP_INDEX_URL", "package_index", "corporate_library"):
            v = str(day1.get(k) or envg.get(k) or "").strip()
            if v:
                found["pip_index"] = _safe_url(v) or v
                break
    th = (os.environ.get("PIP_TRUSTED_HOST") or os.environ.get("PB_PIP_TRUSTED_HOST") or "").strip()
    if th:
        found["trusted_host"] = th
    return found


def heal_aws_cloud() -> dict[str, str]:
    found: dict[str, str] = {}
    mapping = (
        ("AWS_PROFILE", "aws_profile"),
        ("PB_AWS_REGION", "aws_region"),
        ("AWS_DEFAULT_REGION", "aws_region"),
        ("PB_LLM_BASE_URL", "llm_shim"),
        ("PB_OPENSEARCH_ENDPOINT", "opensearch"),
        ("PB_NEPTUNE_ENDPOINT", "neptune"),
    )
    for ek, name in mapping:
        v = (os.environ.get(ek) or "").strip()
        if v and name not in found:
            found[name] = _safe_url(v) if "URL" in ek or "ENDPOINT" in ek or "BASE" in ek else v
    day1, envg = _day1_golden_blobs()
    for name, keys in (
        ("aws_profile", ("aws_profile", "AWS_PROFILE")),
        ("aws_region", ("aws_region", "PB_AWS_REGION")),
        ("llm_shim", ("llm_base_url", "llm_shim", "PB_LLM_BASE_URL")),
        ("opensearch", ("opensearch_endpoint", "opensearch")),
        ("neptune", ("neptune_endpoint", "neptune")),
    ):
        if name in found:
            continue
        for k in keys:
            v = str(day1.get(k) or envg.get(k) or "").strip()
            if v:
                found[name] = v
                break
    if "aws_region" not in found:
        found["aws_region"] = "gov-region-1"  # product default — not a secret
    return found


def heal_sessions() -> dict[str, Any]:
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    sess = codex / "sessions"
    n_files = 0
    if sess.is_dir():
        n_files = sum(1 for _ in sess.rglob("*.jsonl"))
    empty_ack = (os.environ.get("PB_SESSIONS_EMPTY_ACK") or "").lower() in ("1", "true", "yes")
    return {
        "sessions_dir": str(sess),
        "jsonl_count": n_files,
        "empty_ack": empty_ack,
        "ok": n_files > 0 or empty_ack,
    }


def heal_godseye() -> dict[str, Any]:
    out: dict[str, Any] = {"pygame": False, "opengl": False, "flag_on": False}
    try:
        import pygame  # noqa: F401

        out["pygame"] = True
    except Exception as e:
        out["pygame_err"] = str(e)[:120]
    try:
        from OpenGL.GL import glGetString  # noqa: F401

        out["opengl"] = True
    except Exception as e:
        out["opengl_err"] = str(e)[:120]
    try:
        st = _state()
        out["flag_on"] = (st / "godseye.on").exists() or os.environ.get("PB_GODSEYE") == "1"
    except Exception:
        pass
    out["ok"] = out["pygame"]  # CPU backend enough; GL optional
    out["headless_ok"] = True  # core RAG never depends on GUI
    return out


def heal_codex_cli() -> dict[str, Any]:
    pin = (os.environ.get("PB_CODEX_VERSION") or "0.144.3").strip()
    path = shutil.which("codex") or shutil.which("codex.cmd")
    return {
        "binary": path or "",
        "pin": pin,
        "ok": bool(path),
        "install_hint": f"npm install -g @openai/codex@{pin}",
    }


def _register_agent(role: str, scope: dict[str, Any], scenario_id: str) -> str:
    st = _state()
    agents = st / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    # Cap concurrent scenario agents at 64 (MVP law)
    existing = list(agents.glob("synthesizer-*.json")) + list(agents.glob("scenario-*.json"))
    if len(existing) >= 64:
        # reuse oldest slot name
        aid = f"scenario-{role}-cap"
    else:
        aid = f"scenario-{role}-{_ts().replace(':', '')}"
    reg = {
        "agent_id": aid,
        "role": role,
        "status": "spawned",
        "run_id": os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"scenario-{scenario_id}",
        "scope": scope,
        "spawned_at": _ts(),
        "prompt_path": str(st / "pending_scenarios.json"),
    }
    (agents / f"{aid}.json").write_text(json.dumps(reg, indent=2), encoding="utf-8")
    try:
        from audit_lib import audit

        audit(
            "scenario_agent",
            agent_id=aid,
            role=role,
            run_id=reg["run_id"],
            result="spawned",
            detail=scenario_id[:200],
        )
    except Exception:
        pass
    return aid


def open_gaps() -> list[dict[str, Any]]:
    """Probe all surfaces; return list of open gaps needing ask/synthesize."""
    gaps: list[dict[str, Any]] = []
    hosts = heal_ingest_hosts()
    if not hosts.get("gitlab"):
        gaps.append(
            {
                "id": "ingest_hosts_gitlab",
                "surface": "ingest_hosts",
                "severity": "high",
                "healed": hosts,
                "ask": [
                    "What is your internal GitLab base URL (group path OK)?",
                    "Self-hosted GitLab or SaaS behind AppGate?",
                ],
                "agent_role": "synthesizer",
            }
        )
    # jira/confluence optional but useful
    if not hosts.get("jira"):
        gaps.append(
            {
                "id": "ingest_hosts_jira",
                "surface": "ingest_hosts",
                "severity": "medium",
                "healed": hosts,
                "ask": ["Jira base URL? (or say 'none / not used')"],
                "agent_role": "synthesizer",
            }
        )
    if not hosts.get("confluence"):
        gaps.append(
            {
                "id": "ingest_hosts_confluence",
                "surface": "ingest_hosts",
                "severity": "medium",
                "healed": hosts,
                "ask": ["Confluence base URL? (or say 'none / not used')"],
                "agent_role": "synthesizer",
            }
        )

    toks = heal_tokens()
    if hosts.get("gitlab") and not toks.get("gitlab"):
        gaps.append(
            {
                "id": "token_gitlab",
                "surface": "tokens",
                "severity": "high",
                "healed": {k: bool(v) for k, v in toks.items()},
                "ask": [
                    "GitLab private API token available? Prefer secrets_store / env GITLAB_TOKEN — never paste into chat if policy forbids."
                ],
                "agent_role": "security_auditor",
            }
        )

    pkg = heal_package_index()
    if not pkg.get("pip_index") and (os.environ.get("PB_ENTERPRISE") or "").strip() in (
        "1",
        "true",
        "yes",
        "on",
        "",
    ):
        # enterprise flag file may exist — still ask if no index for optional deps
        gaps.append(
            {
                "id": "package_index",
                "surface": "package_index",
                "severity": "medium",
                "healed": pkg,
                "ask": [
                    "Corporate Library / Protected Gateway PIP_INDEX_URL? (or 'public pypi for lab only')"
                ],
                "agent_role": "synthesizer",
            }
        )

    aws = heal_aws_cloud()
    if not aws.get("aws_profile") and not aws.get("llm_shim"):
        gaps.append(
            {
                "id": "aws_cloud",
                "surface": "aws_cloud",
                "severity": "medium",
                "healed": aws,
                "ask": [
                    "AWS profile name for gov region?",
                    "LLM shim base URL if not using local edge only? (or 'edge only')",
                ],
                "agent_role": "synthesizer",
            }
        )

    sess = heal_sessions()
    if not sess.get("ok"):
        gaps.append(
            {
                "id": "sessions_empty",
                "surface": "sessions",
                "severity": "low",
                "healed": sess,
                "ask": [
                    "No Codex sessions found — open Codex once so sessions harvest, or set PB_SESSIONS_EMPTY_ACK=1 for empty pilot?"
                ],
                "agent_role": "retriever",
            }
        )

    ge = heal_godseye()
    if ge.get("flag_on") and not ge.get("pygame"):
        gaps.append(
            {
                "id": "godseye_missing_pygame",
                "surface": "godseye",
                "severity": "low",
                "healed": ge,
                "ask": [
                    "GodsEye requested but pygame missing — install from Corporate Library index, or continue headless?"
                ],
                "agent_role": "visualizer",
            }
        )

    cx = heal_codex_cli()
    if not cx.get("ok") and _interactive():
        gaps.append(
            {
                "id": "codex_cli_missing",
                "surface": "codex_cli",
                "severity": "high",
                "healed": cx,
                "ask": [f"Codex CLI missing — install pin {cx.get('pin')}? ({cx.get('install_hint')})"],
                "agent_role": "orchestrator",
            }
        )

    return gaps


def synthesize_all(*, reason: str = "") -> dict[str, Any]:
    """Write pending_scenarios.json + spawn up to 64 role agents for open gaps."""
    gaps = open_gaps()
    st = _state()
    agents_spawned: list[str] = []
    # Priority order for agent slots
    priority = {"high": 0, "medium": 1, "low": 2}
    gaps_sorted = sorted(gaps, key=lambda g: priority.get(str(g.get("severity")), 9))
    for g in gaps_sorted[:64]:
        aid = _register_agent(
            str(g.get("agent_role") or "synthesizer"),
            {"gap_id": g.get("id"), "surface": g.get("surface"), "ask": g.get("ask")},
            str(g.get("id")),
        )
        g["agent_id"] = aid
        agents_spawned.append(aid)

    doc = {
        "ts": _ts(),
        "reason": reason or "pilot_gap_scan",
        "interactive": _interactive(),
        "max_agents": 64,
        "gap_count": len(gaps),
        "gaps": gaps_sorted,
        "agents_spawned": agents_spawned,
        "healed_snapshot": {
            "hosts": heal_ingest_hosts(),
            "tokens_present": heal_tokens(),
            "package_index": heal_package_index(),
            "aws_cloud": heal_aws_cloud(),
            "sessions": heal_sessions(),
            "godseye": heal_godseye(),
            "codex_cli": heal_codex_cli(),
        },
        "instruction": (
            "HEAL first from healed_snapshot. ASK once only for open high/medium gaps. "
            "Never invent hosts or tokens. Fan-out synthesizer roles ≤64. "
            "CI: only PB_ALLOW_PUBLIC_INGEST for public forges."
        ),
    }
    (st / "pending_scenarios.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    # Keep ingest-specific file for session_start compat
    host_gaps = [g for g in gaps_sorted if g.get("surface") == "ingest_hosts"]
    if host_gaps:
        try:
            from ingest_scenario import write_pending_scenario

            write_pending_scenario(
                blocked_url="",
                reason=reason or "gap_scan_missing_hosts",
                healed=heal_ingest_hosts(),
            )
        except Exception:
            pass
    return doc


def conversation_inject() -> str:
    """Inject for SessionStart / UPS when scenarios pending."""
    st = _state()
    p = st / "pending_scenarios.json"
    if not p.exists():
        # fallback ingest-only file
        try:
            from ingest_scenario import conversation_inject as _ic

            return _ic()
        except Exception:
            return ""
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    gaps = doc.get("gaps") or []
    if not gaps:
        return ""
    lines = [
        "=== PILOT SCENARIOS (heal → ask-once → synthesize, max 64 agents) ===",
        f"ts: {doc.get('ts')}  open_gaps: {doc.get('gap_count')}  agents: {len(doc.get('agents_spawned') or [])}",
        doc.get("instruction") or "",
        "",
        "HEALED SNAPSHOT (use — do not invent):",
        json.dumps(doc.get("healed_snapshot") or {}, indent=2)[:4000],
        "",
        "OPEN GAPS (ask human only if still empty after heal):",
    ]
    for g in gaps[:16]:
        lines.append(
            f"- [{g.get('severity')}] {g.get('id')} role={g.get('agent_role')} agent={g.get('agent_id')}"
        )
        for q in g.get("ask") or []:
            lines.append(f"    • {q}")
    return "\n".join(lines)[:14000]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Pilot scenario heal/ask/synthesize")
    ap.add_argument(
        "cmd",
        nargs="?",
        default="scan",
        choices=["scan", "synthesize", "inject", "hosts", "all"],
    )
    ap.add_argument("--reason", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "hosts":
        h = heal_ingest_hosts()
        print(json.dumps(h, indent=2) if args.json else h)
        return 0
    if args.cmd == "inject":
        print(conversation_inject())
        return 0
    if args.cmd in ("scan", "all"):
        gaps = open_gaps()
        print(json.dumps({"gaps": gaps, "count": len(gaps)}, indent=2, default=str))
        if args.cmd == "scan":
            return 0 if not any(g.get("severity") == "high" for g in gaps) else 1
    if args.cmd in ("synthesize", "all"):
        doc = synthesize_all(reason=args.reason)
        print(json.dumps(doc, indent=2, default=str)[:8000])
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
