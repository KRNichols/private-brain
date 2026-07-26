#!/usr/bin/env python3
"""Config-of-config preflight — scripted inventory BEFORE intelligent Day-1 / shim analysis.

Runs first on DAY1. Discovers what is *already on board* (no secrets printed):
  - Codex sideload surfaces (hooks, profiles, prompts, AGENTS)
  - Agent board (agents/*.md, codex-agents/*.toml) — configuration of configuration
  - Package/backend/enterprise/model routing files
  - AppGate client presence (process/binary hints only)
  - AWS CLI · profiles · region · SSO · SSM plugin (for localhost loopback shim)
  - Source tokens present? (boolean only: GITLAB_TOKEN, JIRA_*, CONFLUENCE_*)
  - Prior day1_map / crawl state

Writes:
  .brain/state/config_of_config.json   — machine-readable board
  .brain/state/agent_board.json        — roles already shipped
  ~/.codex/prompts/private-brain-config-board.md — Codex-readable summary

Usage:
  python config_of_config.py
  python config_of_config.py --json
  python config_of_config.py --suggest-route   # print recommended PB_PACKAGE_ROUTE
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _home() -> Path:
    return Path.home()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (_home() / ".codex"))


def brain_home() -> Path:
    return Path(os.environ.get("PRIVATE_BRAIN_HOME") or (codex_home() / "private-brain"))


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out[:2000]
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 1, str(e)[:200]


def _bool_env(*keys: str) -> dict[str, bool]:
    return {k: bool(os.environ.get(k)) for k in keys}


def _read_text(path: Path, limit: int = 4000) -> str | None:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        pass
    return None


def inventory_codex_sideload() -> dict[str, Any]:
    ch = codex_home()
    bh = brain_home()
    profiles = []
    for name in (
        "config.toml",
        "beast.config.toml",
        "beast-enterprise.config.toml",
        "hooks.json",
    ):
        p = ch / name
        if p.exists():
            profiles.append(name)
    prompts = []
    pd = ch / "prompts"
    if pd.is_dir():
        prompts = sorted(x.name for x in pd.glob("*.md"))[:40]
    agents_md = [p.name for p in ch.glob("AGENTS*.md")]
    return {
        "CODEX_HOME": str(ch),
        "PRIVATE_BRAIN_HOME": str(bh),
        "sideload_only": True,
        "note": "Private Brain is Codex sideload — no separate product CLI",
        "profiles_present": profiles,
        "hooks_json": (ch / "hooks.json").exists(),
        "prompts": prompts,
        "agents_fragments": agents_md,
        "brain_scripts": (bh / "scripts" / "orchestrate.py").exists(),
        "beastMode": bool(_which("beastMode") or (bh / "scripts" / "beastMode").exists()),
        "enterprise_flag": (bh / ".brain" / "state" / "enterprise.on").exists()
        or os.environ.get("PB_ENTERPRISE") == "1",
    }


def inventory_agent_board() -> dict[str, Any]:
    """Configuration of configuration — agents already shipped on disk."""
    bh = brain_home()
    board: dict[str, Any] = {
        "purpose": (
            "On-board agent catalog. Codex roles (code/plan/docs/retrieve/audit) "
            "map to these files; AWS later runs same role names as tasks."
        ),
        "markdown_agents": [],
        "codex_toml_agents": [],
        "role_families": {
            "code_assistant": ["orchestrator", "retriever", "graph-writer", "synthesizer"],
            "planning_assistant": ["orchestrator", "metrics-master", "optimizer", "rater"],
            "technical_documentor": ["synthesizer", "confluence-deep", "confluence-topo", "auditor"],
            "source_crawlers": [
                "gitlab-topo",
                "gitlab-deep",
                "jira-topo",
                "jira-deep",
                "confluence-topo",
                "confluence-deep",
            ],
            "security_ops": ["security_auditor", "auditor", "cost_manager", "watcher"],
            "config_of_config": ["config_board", "day1_map", "shim_preflight"],
        },
    }
    for base in (bh / "agents", _ROOT / "agents"):
        if base.is_dir():
            board["markdown_agents"] = sorted(p.stem for p in base.glob("*.md") if p.name != "README.md")
            board["agents_dir"] = str(base)
            break
    for base in (bh / "codex-agents", _ROOT / "codex-agents"):
        if base.is_dir():
            board["codex_toml_agents"] = sorted(p.stem for p in base.glob("*.toml"))
            board["codex_agents_dir"] = str(base)
            break
    # scripts that act as agents
    script_agents = []
    for name in (
        "day1_first_start.py",
        "config_of_config.py",
        "internal_crawl_swarm.py",
        "agent_swarm.py",
        "validate_enterprise.py",
        "orchestrate.py",
        "roles.py",
    ):
        if (bh / "scripts" / name).exists() or (_SCRIPTS / name).exists():
            script_agents.append(name)
    board["script_agents"] = script_agents
    board["count_md"] = len(board["markdown_agents"])
    board["count_toml"] = len(board["codex_toml_agents"])
    return board


def inventory_config_files() -> dict[str, Any]:
    bh = brain_home()
    cfg = bh / "config"
    files = {}
    for name in (
        "enterprise.yaml",
        "backend.yaml",
        "model_routing.json",
        "grok_model_routing.json",
        "agent_board.yaml",
        "aws_shim.yaml",
    ):
        p = cfg / name
        files[name] = {"exists": p.exists(), "path": str(p) if p.exists() else None}
        if p.exists() and name.endswith((".yaml", ".yml", ".json")):
            text = _read_text(p, 800) or ""
            # redacted peek: keys only for yaml-ish
            keys = re.findall(r"^([A-Za-z0-9_]+)\s*:", text, re.M)
            files[name]["top_keys"] = keys[:30]
    # backend region hint
    backend = _read_text(cfg / "backend.yaml") or ""
    region = None
    m = re.search(r"^region:\s*(\S+)", backend, re.M)
    if m:
        region = m.group(1).strip().strip("\"'")
    return {
        "config_dir": str(cfg),
        "files": files,
        "backend_region": region,
        "model_routing_exists": (cfg / "model_routing.json").exists(),
    }


def inventory_appgate() -> dict[str, Any]:
    """Detect AppGate client presence — not session secrets."""
    bins = []
    for name in (
        "appgate",
        "AppGate",
        "sdp-driver",
        "appgate-driver",
    ):
        w = _which(name)
        if w:
            bins.append(w)
    # mac app bundle
    mac_apps = []
    for p in (
        Path("/Applications/AppGate SDP.app"),
        Path("/Applications/AppGate.app"),
        _home() / "Applications" / "AppGate SDP.app",
    ):
        if p.exists():
            mac_apps.append(str(p))
    # process hint (name only)
    rc, out = _run(["ps", "ax", "-o", "comm="], timeout=5)
    procs = []
    if rc == 0 and out:
        for line in out.splitlines():
            low = line.lower()
            if "appgate" in low or "sdp-driver" in low:
                procs.append(line.strip()[:80])
                if len(procs) >= 5:
                    break
    env_hints = _bool_env("APPGATE_DEVICE_ID", "APPGATE_PROFILE", "PB_APPGATE_REQUIRED")
    return {
        "binaries": bins,
        "mac_apps": mac_apps,
        "processes_hint": procs,
        "env_flags_set": env_hints,
        "likely_installed": bool(bins or mac_apps or procs),
        "session_active_guess": bool(procs),
        "note": "AppGate protects Confluence/Jira/GitLab; crawl only after ZTNA up",
    }


def inventory_aws_shim() -> dict[str, Any]:
    """AWS CLI + SSM readiness for Codex→localhost loopback→Government Cloud."""
    aws = _which("aws")
    session_mgr = _which("session-manager-plugin")
    rc_ver, ver = _run(["aws", "--version"], timeout=5) if aws else (127, "")
    region = (
        os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("PB_AWS_REGION")
        or ""
    )
    profile = os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or ""
    # list profiles without secrets
    profiles: list[str] = []
    cfg_path = _home() / ".aws" / "config"
    if cfg_path.exists():
        text = _read_text(cfg_path, 8000) or ""
        profiles = re.findall(r"^\[profile\s+([^\]]+)\]", text, re.M)
        if re.search(r"^\[default\]", text, re.M):
            profiles = ["default", *profiles]
    # ssm document / port forward capability = plugin present
    gov = region.startswith("us-gov-") if region else None
    recommend_region = region or "gov-region-1"
    return {
        "aws_cli": aws,
        "aws_version": ver.split("\n")[0] if ver else None,
        "session_manager_plugin": session_mgr,
        "ssm_loopback_ready": bool(aws and session_mgr),
        "AWS_PROFILE_set": bool(profile),
        "AWS_PROFILE": profile or None,
        "region_env": region or None,
        "profiles_configured": profiles[:20],
        "govcloud_region_hint": gov,
        "recommend_region": recommend_region,
        "env_token_flags": _bool_env(
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "CODEARTIFACT_AUTH_TOKEN",
        ),
        "shim_pattern": {
            "steps": [
                "1. AppGate connects laptop to corporate + AWS management path",
                "2. aws sso login / credential process (Government Cloud)",
                "3. aws ssm start-session --document AWS-StartPortForwardingSession "
                "   (or StartPortForwardingSessionToRemoteHost) → localhost:PORT",
                "4. Codex / beastMode uses OPENAI_BASE_URL or PB_LLM_BASE_URL=http://127.0.0.1:PORT",
                "5. RAG dual-write optional → OpenSearch+Neptune in gov-region-1 VPC",
            ],
            "codex_is": "edge orchestrator (sideload), not the model host",
            "models_live_in": "AWS (OpenAI GSS 120B · Nova Pro · Nova Mini · Bedrock as approved)",
        },
    }


def inventory_sources() -> dict[str, Any]:
    return {
        "urls_env": {
            "PB_GITLAB_URL": os.environ.get("PB_GITLAB_URL"),
            "PB_JIRA_URL": os.environ.get("PB_JIRA_URL"),
            "PB_CONFLUENCE_URL": os.environ.get("PB_CONFLUENCE_URL"),
            "GITLAB_URL": os.environ.get("GITLAB_URL"),
            "JIRA_URL": os.environ.get("JIRA_URL"),
            "CONFLUENCE_URL": os.environ.get("CONFLUENCE_URL"),
        },
        "tokens_present_boolean": _bool_env(
            "GITLAB_TOKEN",
            "PRIVATE_TOKEN",
            "PB_GITLAB_TOKEN",
            "JIRA_TOKEN",
            "JIRA_API_TOKEN",
            "JIRA_USER",
            "CONFLUENCE_TOKEN",
            "CONFLUENCE_API_TOKEN",
            "ATLASSIAN_TOKEN",
        ),
        "allowlist_hosts_env": os.environ.get("PB_ALLOWLIST_HOSTS"),
        "crawl_min_interval": os.environ.get("PB_CRAWL_MIN_INTERVAL") or "0.35",
    }


def inventory_package_route_hints() -> dict[str, Any]:
    return {
        "PB_PACKAGE_ROUTE": os.environ.get("PB_PACKAGE_ROUTE"),
        "PIP_INDEX_URL_set": bool(os.environ.get("PIP_INDEX_URL") or os.environ.get("PB_PIP_INDEX_URL")),
        "corporate-package-index_env_files": [
            str(p)
            for p in (
                brain_home() / "corporate-package-index.env",
                brain_home() / "day1.env",
                codex_home() / "corporate-package-index.env",
                Path.cwd() / "corporate-package-index.env",
            )
            if p.exists()
        ],
    }


def inventory_prior_state() -> dict[str, Any]:
    st = brain_home() / ".brain" / "state"
    out: dict[str, Any] = {"state_dir": str(st), "files": {}}
    for name in (
        "day1_map.json",
        "config_of_config.json",
        "agent_board.json",
        "corpus_purity.json",
        "internal_crawl_swarm.json",
        "validate_enterprise.json",
    ):
        p = st / name
        out["files"][name] = p.exists()
        if p.exists() and name == "day1_map.json":
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out["prior_day1_route"] = d.get("route")
                out["prior_program_id"] = d.get("program_id")
            except Exception:
                pass
    return out


def suggest_route(board: dict[str, Any]) -> dict[str, Any]:
    """Scripted recommendation before interactive intelligence."""
    aws = board.get("aws_shim") or {}
    pkg = board.get("package_route") or {}
    app = board.get("appgate") or {}
    scores = {"corporate-library": 0, "aws": 0, "headless": 1}
    if pkg.get("PIP_INDEX_URL_set") or pkg.get("corporate-package-index_env_files"):
        scores["corporate-library"] += 3
    if aws.get("region_env") and str(aws.get("region_env")).startswith("us-gov"):
        scores["aws"] += 3
    if aws.get("profiles_configured") or aws.get("AWS_PROFILE_set"):
        scores["aws"] += 2
    if aws.get("ssm_loopback_ready"):
        scores["aws"] += 2
    if aws.get("env_token_flags", {}).get("CODEARTIFACT_AUTH_TOKEN"):
        scores["aws"] += 2
    if app.get("likely_installed"):
        scores["corporate-library"] += 1
        scores["aws"] += 1
    # prior
    prior = (board.get("prior_state") or {}).get("prior_day1_route")
    if prior in scores:
        scores[prior] += 2
    if pkg.get("PB_PACKAGE_ROUTE") in scores:
        scores[str(pkg["PB_PACKAGE_ROUTE"])] += 4
    best = max(scores, key=scores.get)
    return {
        "recommended_route": best,
        "scores": scores,
        "rationale": {
            "corporate-library": "Corporate Library Corporate Package Index / corporate pip when index env present",
            "aws": "Government Cloud CLI/SSM/CodeArtifact signals → AWS package + LLM shim",
            "headless": "safe default — stdlib RAG until approved index exists",
        },
        "next_after_route": [
            "Confirm AppGate session if crawling internal hosts",
            "Set PB_GITLAB_URL / PB_JIRA_URL / PB_CONFLUENCE_URL",
            "DAY1 continues → intelligent day1_first_start uses this board",
            "If aws: configure localhost SSM port-forward before model calls",
        ],
    }


def analyze_shim(board: dict[str, Any]) -> dict[str, Any]:
    """Intelligent-ish analysis AFTER pure scripting inventory (still deterministic)."""
    aws = board.get("aws_shim") or {}
    app = board.get("appgate") or {}
    codex = board.get("codex") or {}
    gaps: list[str] = []
    ready: list[str] = []
    if codex.get("hooks_json") and codex.get("brain_scripts"):
        ready.append("codex_sideload_present")
    else:
        gaps.append("run SETUP / DAY1 install for Codex sideload hooks + scripts")
    if app.get("likely_installed"):
        ready.append("appgate_client_seen")
        if not app.get("session_active_guess"):
            gaps.append("start AppGate SDP session before internal crawl")
    else:
        gaps.append("install/login AppGate if Confluence/Jira/GitLab are ZTNA-only")
    if aws.get("aws_cli"):
        ready.append("aws_cli")
    else:
        gaps.append("install AWS CLI v2 for Government Cloud")
    if aws.get("session_manager_plugin"):
        ready.append("ssm_plugin")
    else:
        gaps.append("install session-manager-plugin for localhost port-forward shim")
    if not aws.get("profiles_configured") and not aws.get("AWS_PROFILE_set"):
        gaps.append("configure ~/.aws/config profile for gov-region-1 (or approved region)")
    region = aws.get("region_env") or aws.get("recommend_region")
    if region and not str(region).startswith("us-gov-"):
        gaps.append(
            f"region_env={region} is not us-gov-* — confirm commercial vs Government Cloud ATO before production"
        )
    return {
        "ready": ready,
        "gaps": gaps,
        "shim_green": len([g for g in gaps if "ssm" in g or "aws_cli" in g]) == 0
        and bool(aws.get("aws_cli")),
        "crawl_green": bool(app.get("session_active_guess") or os.environ.get("PB_APPGATE_REQUIRED") == "0"),
        "architecture_ok": True,
        "architecture_notes": [
            "Codex CLI = edge orchestrator (sideload only)",
            "LLM + RAG data plane intended on AWS (GSS 120B / Nova / Bedrock as approved)",
            "AppGate = path to internal sources + often to AWS control plane",
            "SSM port-forward to localhost = safe loopback activation of AWS-hosted API",
            "gov-region-1 is correct default IF account ATO + model enablement live there",
        ],
    }


def build_board() -> dict[str, Any]:
    board: dict[str, Any] = {
        "ts": _ts(),
        "version": 1,
        "phase": "config_of_config",
        "order": "scripted_inventory → suggest_route → shim_analysis → day1_intelligent",
        "os": {
            "system": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
        },
        "python": {
            "executable": sys.executable,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "ok": sys.version_info >= (3, 10),
        },
        "codex": inventory_codex_sideload(),
        "agent_board": inventory_agent_board(),
        "config_files": inventory_config_files(),
        "appgate": inventory_appgate(),
        "aws_shim": inventory_aws_shim(),
        "sources": inventory_sources(),
        "package_route": inventory_package_route_hints(),
        "prior_state": inventory_prior_state(),
    }
    board["suggest"] = suggest_route(board)
    board["shim_analysis"] = analyze_shim(board)
    return board


def persist(board: dict[str, Any]) -> dict[str, str]:
    bh = brain_home()
    state = bh / ".brain" / "state"
    state.mkdir(parents=True, exist_ok=True)
    paths = {}
    main = state / "config_of_config.json"
    main.write_text(json.dumps(board, indent=2, default=str), encoding="utf-8")
    paths["config_of_config"] = str(main)
    ab = state / "agent_board.json"
    ab.write_text(json.dumps(board.get("agent_board") or {}, indent=2, default=str), encoding="utf-8")
    paths["agent_board"] = str(ab)
    # Codex-readable board
    prompts = codex_home() / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    sug = board.get("suggest") or {}
    shim = board.get("shim_analysis") or {}
    aws = board.get("aws_shim") or {}
    agents = board.get("agent_board") or {}
    md = f"""---
description: Private Brain config-of-config board (pre-Day-1)
---
# Config-of-config board (scripted · before intelligent Day-1)

Generated: **{board.get("ts")}**

## Sideload
- Codex sideload **only** (no product CLI)
- hooks: `{board.get("codex", {}).get("hooks_json")}` · brain scripts: `{board.get("codex", {}).get("brain_scripts")}`

## Agent board already on disk
- Markdown agents: **{agents.get("count_md", 0)}** — `{agents.get("agents_dir", "")}`
- Codex TOML agents: **{agents.get("count_toml", 0)}**
- Role families: code · plan · docs · crawlers · security · config_of_config

## Recommended package route (scripted)
- **{sug.get("recommended_route")}** (scores: `{json.dumps(sug.get("scores"))}`)

## AppGate
- installed guess: `{board.get("appgate", {}).get("likely_installed")}`
- session process guess: `{board.get("appgate", {}).get("session_active_guess")}`

## AWS shim (SSM localhost loopback)
- aws CLI: `{bool(aws.get("aws_cli"))}` · SSM plugin: `{bool(aws.get("session_manager_plugin"))}`
- ssm_loopback_ready: `{aws.get("ssm_loopback_ready")}`
- region: `{aws.get("region_env") or aws.get("recommend_region")}`
- profiles: `{aws.get("profiles_configured")}`

## Shim analysis
- ready: {shim.get("ready")}
- gaps: {shim.get("gaps")}

## What you (Codex) should do next
1. Respect this board before inventing infra.
2. Continue DAY1 intelligent map if gaps are acceptable.
3. For internal crawl: require AppGate session + enterprise allowlist hosts.
4. For AWS models: do not call public OpenAI — use localhost shim / approved base URL.
"""
    pp = prompts / "private-brain-config-board.md"
    pp.write_text(md, encoding="utf-8")
    paths["codex_prompt"] = str(pp)
    try:
        from audit_lib import audit

        audit(
            "config_of_config",
            agent_id="config-board",
            role="config_of_config",
            result="ok",
            detail=f"route_suggest={sug.get('recommended_route')} gaps={len(shim.get('gaps') or [])}",
            props={
                "recommended_route": sug.get("recommended_route"),
                "ssm_loopback_ready": aws.get("ssm_loopback_ready"),
            },
        )
    except Exception:
        pass
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Config-of-config preflight (before Day-1 intelligence)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--suggest-route", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    board = build_board()
    paths = {} if args.no_write else persist(board)
    board["paths"] = paths

    if args.suggest_route:
        print((board.get("suggest") or {}).get("recommended_route") or "headless")
        return 0

    print("==============================================")
    print(" Config-of-config (scripted preflight)")
    print("==============================================")
    print(f" Codex sideload: hooks={board['codex'].get('hooks_json')} scripts={board['codex'].get('brain_scripts')}")
    print(f" Agents on disk: md={board['agent_board'].get('count_md')} toml={board['agent_board'].get('count_toml')}")
    print(f" AppGate:        installed={board['appgate'].get('likely_installed')} session~={board['appgate'].get('session_active_guess')}")
    print(f" AWS CLI:        {bool(board['aws_shim'].get('aws_cli'))}  SSM plugin={bool(board['aws_shim'].get('session_manager_plugin'))}")
    print(f" SSM loopback:   {board['aws_shim'].get('ssm_loopback_ready')}")
    print(f" Region hint:    {board['aws_shim'].get('region_env') or board['aws_shim'].get('recommend_region')}")
    print(f" Suggest route:  {board['suggest'].get('recommended_route')}  scores={board['suggest'].get('scores')}")
    gaps = (board.get("shim_analysis") or {}).get("gaps") or []
    if gaps:
        print(" Gaps:")
        for g in gaps:
            print(f"   - {g}")
    else:
        print(" Gaps: (none critical)")
    if paths:
        print(f" Wrote: {paths.get('config_of_config')}")
        print(f" Codex: {paths.get('codex_prompt')}")
    print(" Next: intelligent Day-1 (day1_first_start) consumes this board")
    print("==============================================")
    if args.json:
        print(json.dumps(board, indent=2, default=str))
    # machine lines for shell
    print(f"COC_ROUTE={board['suggest'].get('recommended_route')}")
    print(f"COC_SSM_READY={1 if board['aws_shim'].get('ssm_loopback_ready') else 0}")
    print(f"COC_APPGATE={1 if board['appgate'].get('likely_installed') else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
