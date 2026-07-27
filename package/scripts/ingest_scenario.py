#!/usr/bin/env python3
"""Blocked-ingest intelligence — heal from known hosts, then ask once, then synthesize.

Product law (interactive pilot):
  1. Self-heal: env / day1_map / golden_config / allowlist — no user if known
  2. If still unknown + interactive (not PB_CI): write pending scenario + ASK for URLs
  3. Register synthesizer agent role so Codex can map self-host vs GitLab/Jira/Confluence

Not for unattended CI: PB_ALLOW_PUBLIC_INGEST handles public OSS force-feed.
CLI still exits non-zero on hard block after heal fails — conversation path carries the ask.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    from brain_lib import STATE_DIR

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _interactive() -> bool:
    if (os.environ.get("PB_CI") or "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    if (os.environ.get("PB_NONINTERACTIVE") or "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    return True


def _safe_url(u: str) -> str:
    if not u:
        return ""
    try:
        p = urlparse(u.strip())
        if not p.scheme or not p.netloc:
            return ""
        return f"{p.scheme}://{p.netloc}{(p.path or '').rstrip('/')}"
    except Exception:
        return ""


def heal_hosts_from_state() -> dict[str, str]:
    """Self-heal: known hosts without asking the human."""
    found: dict[str, str] = {}
    # Env first
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

    st = _state()
    # day1_map
    try:
        dm = json.loads((st / "day1_map.json").read_text(encoding="utf-8"))
        answers = dm.get("answers") or dm
        for name, keys in (
            ("gitlab", ("gitlab_url", "gitlab", "PB_GITLAB_URL")),
            ("jira", ("jira_url", "jira", "PB_JIRA_URL")),
            ("confluence", ("confluence_url", "confluence", "PB_CONFLUENCE_URL")),
        ):
            if name in found:
                continue
            for k in keys:
                u = _safe_url(str(answers.get(k) or dm.get(k) or ""))
                if u:
                    found[name] = u
                    break
    except Exception:
        pass

    # golden_config.json
    try:
        g = json.loads((st / "golden_config.json").read_text(encoding="utf-8"))
        envm = g.get("env") or g.get("hosts") or g
        for name, keys in (
            ("gitlab", ("gitlab", "gitlab_url")),
            ("jira", ("jira", "jira_url")),
            ("confluence", ("confluence", "confluence_url")),
        ):
            if name in found:
                continue
            for k in keys:
                u = _safe_url(str(envm.get(k) or ""))
                if u:
                    found[name] = u
                    break
    except Exception:
        pass

    # allowlist hosts → suggest https://host (no path)
    try:
        from enterprise import load_policy

        pol = load_policy()
        hosts = [str(h).lower() for h in (pol.get("allowlist_hosts") or []) if h]
        for h in hosts:
            if "gitlab" in h and "gitlab" not in found:
                found["gitlab"] = f"https://{h}"
            if "jira" in h and "jira" not in found:
                found["jira"] = f"https://{h}"
            if "confluence" in h or "wiki" in h:
                if "confluence" not in found:
                    found["confluence"] = f"https://{h}"
    except Exception:
        pass

    return found


def write_pending_scenario(
    *,
    blocked_url: str | None,
    reason: str,
    healed: dict[str, str],
) -> dict[str, Any]:
    """Persist scenario for SessionStart / UPS inject + synthesizer agent."""
    st = _state()
    scenario = {
        "ts": _ts(),
        "kind": "ingest_blocked_public_or_unknown",
        "blocked_url": blocked_url or "",
        "reason": str(reason)[:500],
        "healed_hosts": healed,
        "status": "awaiting_user_confirm" if _interactive() and not healed.get("gitlab") else "healed_partial",
        "questions": [
            "What is your internal GitLab base URL (group path OK)? e.g. https://gitlab.corp.example/mygroup",
            "Jira base URL? (or say 'none')",
            "Confluence base URL? (or say 'none')",
            "Self-hosted GitLab / Jira / Confluence, or SaaS behind AppGate?",
        ],
        "agent_role": "synthesizer",
        "instruction": (
            "Do NOT invent hosts. Do NOT use gitlab.com/github.com unless PB_ALLOW_PUBLIC_INGEST=1. "
            "Ask the human for missing internal URLs. Then set env / day1_map / golden and re-run ingest."
        ),
    }
    path = st / "pending_ingest_scenario.json"
    path.write_text(json.dumps(scenario, indent=2), encoding="utf-8")

    # Register synthesizer agent instance (prompt materialization for orchestrator)
    agents = st / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    aid = f"synthesizer-ingest-{_ts().replace(':', '')}"
    reg = {
        "agent_id": aid,
        "role": "synthesizer",
        "status": "spawned",
        "run_id": os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"ingest-scenario-{_ts()}",
        "scope": {"scenario": "ingest_blocked", "blocked_url": blocked_url},
        "spawned_at": _ts(),
        "prompt_path": str(st / "pending_ingest_scenario.json"),
    }
    (agents / f"{aid}.json").write_text(json.dumps(reg, indent=2), encoding="utf-8")
    scenario["agent_id"] = aid

    try:
        from audit_lib import audit

        audit(
            "ingest_scenario",
            agent_id=aid,
            role="synthesizer",
            run_id=reg["run_id"],
            result="pending" if scenario["status"].startswith("awaiting") else "healed",
            detail=str(reason)[:240],
        )
    except Exception:
        pass

    return scenario


def conversation_inject(scenario: dict[str, Any] | None = None) -> str:
    """Text for UserPromptSubmit / SessionStart when ingest is blocked or pending."""
    st = _state()
    if scenario is None:
        p = st / "pending_ingest_scenario.json"
        if not p.exists():
            return ""
        try:
            scenario = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return ""
    if not scenario:
        return ""

    healed = scenario.get("healed_hosts") or {}
    lines = [
        "=== INGEST SCENARIO (enterprise block / unknown hosts) ===",
        f"status: {scenario.get('status')}",
        f"blocked: {scenario.get('blocked_url') or '(none)'}",
        f"reason: {scenario.get('reason')}",
        "",
        "SELF-HEAL already tried: env, day1_map, golden_config, allowlist.",
    ]
    if healed:
        lines.append("Known hosts from state (use these — do not invent):")
        for k, v in healed.items():
            lines.append(f"  - {k}: {v}")
        lines.append(
            "If these are correct: run beastMode -ingestion <gitlab_url> (or say "
            "'ingest gitlab <url>'). If wrong: ask human to correct."
        )
    else:
        lines.append(
            "NO internal hosts in state. YOU MUST ASK the human (one short question set):"
        )
        for q in scenario.get("questions") or []:
            lines.append(f"  • {q}")
        lines.append(
            "After answers: update day1_map / golden / env, then re-run ingest. "
            "Never claim crawl succeeded without graph evidence."
        )
    lines.append(
        f"Synthesizer agent registered: {scenario.get('agent_id') or 'synthesizer'} "
        "— map self-host vs GitLab/Jira/Confluence; no public forge under enterprise."
    )
    lines.append(scenario.get("instruction") or "")
    return "\n".join(lines)[:12000]


def handle_blocked_ingest(
    *,
    blocked_url: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """
    Called when assert_ingest_allowed raises or CLI is about to exit 2.
    Returns {ok, healed, scenario, inject, suggested_gitlab, exit_code}.
    """
    healed = heal_hosts_from_state()
    out: dict[str, Any] = {
        "ok": False,
        "healed": healed,
        "suggested_gitlab": healed.get("gitlab") or "",
        "interactive": _interactive(),
        "ci": not _interactive(),
    }

    # If we healed a gitlab URL and blocked was public, suggest retry with healed URL
    if healed.get("gitlab"):
        out["ok"] = True
        out["status"] = "healed_retry"
        scenario = write_pending_scenario(
            blocked_url=blocked_url,
            reason=reason or "public/unknown blocked; healed internal hosts from state",
            healed=healed,
        )
        scenario["status"] = "healed_use_internal"
        (_state() / "pending_ingest_scenario.json").write_text(
            json.dumps(scenario, indent=2), encoding="utf-8"
        )
        out["scenario"] = scenario
        out["inject"] = conversation_inject(scenario)
        out["exit_code"] = 0  # caller may re-run with healed URL
        return out

    scenario = write_pending_scenario(
        blocked_url=blocked_url,
        reason=reason or "enterprise blocked public/unknown host; no internal host in state",
        healed=healed,
    )
    out["scenario"] = scenario
    out["inject"] = conversation_inject(scenario)
    out["status"] = scenario["status"]
    # CLI: still non-zero so automation doesn't pretend success; conversation carries the ask
    out["exit_code"] = 3 if _interactive() else 2
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Ingest scenario heal / ask / synthesize")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "heal", "handle", "inject"])
    ap.add_argument("--url", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "heal":
        h = heal_hosts_from_state()
        print(json.dumps(h, indent=2) if args.json else h)
        return 0 if h else 1
    if args.cmd == "handle":
        r = handle_blocked_ingest(blocked_url=args.url or None, reason=args.reason)
        print(json.dumps(r, indent=2, default=str))
        return int(r.get("exit_code") or 0)
    if args.cmd == "inject":
        print(conversation_inject())
        return 0
    # status
    p = _state() / "pending_ingest_scenario.json"
    if p.exists():
        print(p.read_text(encoding="utf-8"))
        return 0
    print(json.dumps({"pending": False, "healed": heal_hosts_from_state()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
