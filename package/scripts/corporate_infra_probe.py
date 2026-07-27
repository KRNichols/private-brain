#!/usr/bin/env python3
"""Corporate infrastructure probe — AppGate-aware harmony check (no secrets printed).

Uses hosts from: env, day1_map, golden_config, golden_join, allowlist.
Probes reachability of GitLab/Jira/Confluence/Corporate Library/AWS shim.
Does NOT invent hosts. Soft when AppGate down; hard only if you claim READY with zero path.

Typical Corporate sequence (from golden_join human_steps):
  1. AppGate connect
  2. Probe internal hosts
  3. Crawl / package index / AWS SHIM

Usage:
  PB_ENTERPRISE=1 python corporate_infra_probe.py
  python corporate_infra_probe.py --json
  python corporate_infra_probe.py --write   # → .brain/state/corporate_infra_probe.json
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

UA = "PrivateBrain-CorporateInfraProbe/1.0"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    from brain_lib import STATE_DIR

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _safe(u: str) -> str:
    if not u:
        return ""
    try:
        p = urlparse(u.strip())
        if not p.scheme or not p.netloc:
            return ""
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return ""


def collect_targets() -> dict[str, list[str]]:
    """Map surface → candidate base URLs (deduped)."""
    buckets: dict[str, list[str]] = {
        "gitlab": [],
        "jira": [],
        "confluence": [],
        "package_index": [],
        "llm_shim": [],
        "opensearch": [],
        "neptune": [],
    }

    def add(surface: str, url: str) -> None:
        u = _safe(url)
        if u and u not in buckets[surface]:
            buckets[surface].append(u)

    env_map = (
        ("gitlab", ("PB_GITLAB_URL", "GITLAB_URL")),
        ("jira", ("PB_JIRA_URL", "JIRA_URL")),
        ("confluence", ("PB_CONFLUENCE_URL", "CONFLUENCE_URL")),
        ("package_index", ("PIP_INDEX_URL", "PB_PIP_INDEX_URL")),
        ("llm_shim", ("PB_LLM_BASE_URL",)),
        ("opensearch", ("PB_OPENSEARCH_ENDPOINT",)),
        ("neptune", ("PB_NEPTUNE_ENDPOINT",)),
    )
    for surface, keys in env_map:
        for k in keys:
            add(surface, os.environ.get(k) or "")

    st = _state()
    for fname in ("day1_map.json", "golden_config.json", "golden_join.json"):
        p = st / fname
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        answers = d.get("answers") if isinstance(d.get("answers"), dict) else d
        envg = d.get("env") if isinstance(d.get("env"), dict) else d
        for blob in (answers, envg, d):
            if not isinstance(blob, dict):
                continue
            add("gitlab", str(blob.get("gitlab_url") or blob.get("gitlab") or ""))
            add("jira", str(blob.get("jira_url") or blob.get("jira") or ""))
            add("confluence", str(blob.get("confluence_url") or blob.get("confluence") or ""))
            add("package_index", str(blob.get("pip_index_url") or blob.get("pip_index") or ""))
            add("llm_shim", str(blob.get("llm_shim_url") or blob.get("llm_shim") or ""))
            add("opensearch", str(blob.get("opensearch_endpoint") or ""))
            add("neptune", str(blob.get("neptune_endpoint") or ""))
            for h in blob.get("allowlist_hosts") or []:
                hl = str(h).lower()
                if "gitlab" in hl:
                    add("gitlab", f"https://{h}")
                if "jira" in hl:
                    add("jira", f"https://{h}")
                if "confluence" in hl or "wiki" in hl:
                    add("confluence", f"https://{h}")
                if "package" in hl or "gateway" in hl or "artifactory" in hl or "corporate" in hl:
                    add("package_index", f"https://{h}")

    try:
        from enterprise import load_policy

        for h in load_policy().get("allowlist_hosts") or []:
            hl = str(h).lower()
            if "gitlab" in hl:
                add("gitlab", f"https://{h}")
            if "jira" in hl:
                add("jira", f"https://{h}")
            if "confluence" in hl or "wiki" in hl:
                add("confluence", f"https://{h}")
    except Exception:
        pass

    return buckets


def _tcp(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "error": ""}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _http(url: str, timeout: float = 8.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            body = resp.read(200)
            return {
                "ok": True,
                "http_code": int(code),
                "reachable": True,
                "auth_required": int(code) in (401, 403),
                "snippet_len": len(body),
                "error": "",
            }
    except urllib.error.HTTPError as e:
        # 401/403 still means AppGate path + host is reachable
        return {
            "ok": True,
            "http_code": int(e.code),
            "reachable": True,
            "auth_required": e.code in (401, 403),
            "error": f"HTTP {e.code}",
        }
    except Exception as e:
        err = str(e)[:200]
        # Classify AppGate / ZTNA-ish failures
        low = err.lower()
        appgate_ish = any(
            x in low
            for x in (
                "timed out",
                "timeout",
                "network is unreachable",
                "nodename nor servname",
                "name or service not known",
                "connection refused",
                "connection reset",
                "certificate",
                "ssl",
                "proxy",
            )
        )
        return {
            "ok": False,
            "http_code": None,
            "reachable": False,
            "auth_required": False,
            "error": err,
            "likely_appgate_or_network": appgate_ish,
        }


def probe_surface(surface: str, base: str) -> dict[str, Any]:
    """Probe one base URL with surface-aware paths."""
    p = urlparse(base)
    host = p.hostname or ""
    port = p.port or (443 if p.scheme == "https" else 80)
    out: dict[str, Any] = {
        "surface": surface,
        "base": base,
        "host": host,
        "tcp": _tcp(host, port) if host else {"ok": False, "error": "no host"},
    }
    paths: list[str] = ["/"]
    if surface == "gitlab":
        paths = ["/api/v4/version", "/api/v4/groups", "/"]
    elif surface == "jira":
        paths = ["/rest/api/2/serverInfo", "/rest/api/2/project", "/"]
    elif surface == "confluence":
        paths = ["/rest/api/space", "/wiki/rest/api/space", "/"]
    elif surface == "package_index":
        # Corporate Package Index / simple index
        paths = [p.path or "/simple/", "/"]
        if not (p.path or "").endswith("simple") and "simple" not in (p.path or ""):
            paths = ["/simple/", p.path or "/", "/"]
    elif surface == "llm_shim":
        paths = ["/v1/models", "/health", "/"]
    elif surface in ("opensearch", "neptune"):
        paths = ["/", "/_cluster/health"]

    http_hits = []
    for path in paths[:3]:
        if path.startswith("http"):
            url = path
        else:
            url = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
        r = _http(url)
        r["url"] = url
        http_hits.append(r)
        if r.get("reachable"):
            break
    out["http"] = http_hits
    out["reachable"] = bool(out["tcp"].get("ok")) or any(h.get("reachable") for h in http_hits)
    out["auth_required"] = any(h.get("auth_required") for h in http_hits)
    out["likely_appgate_block"] = (not out["reachable"]) and any(
        h.get("likely_appgate_or_network") for h in http_hits
    ) or (not out["tcp"].get("ok") and not out["reachable"])
    return out


def run_probe() -> dict[str, Any]:
    targets = collect_targets()
    results: dict[str, Any] = {}
    for surface, urls in targets.items():
        results[surface] = {
            "candidates": urls,
            "probes": [probe_surface(surface, u) for u in urls[:4]],
        }
        if not urls:
            results[surface]["status"] = "no_host_in_state"
        elif any(p.get("reachable") for p in results[surface]["probes"]):
            results[surface]["status"] = "reachable"
        elif any(p.get("likely_appgate_block") for p in results[surface]["probes"]):
            results[surface]["status"] = "likely_appgate_or_network_down"
        else:
            results[surface]["status"] = "unreachable"

    # Harmony score: how many critical surfaces we can talk to
    critical = ("gitlab", "jira", "confluence", "package_index")
    known = sum(1 for s in critical if targets.get(s))
    up = sum(1 for s in critical if results.get(s, {}).get("status") == "reachable")
    missing_host = [s for s in critical if results.get(s, {}).get("status") == "no_host_in_state"]
    appgate_blocked = [
        s for s in critical if results.get(s, {}).get("status") == "likely_appgate_or_network_down"
    ]

    advice: list[str] = []
    if missing_host:
        advice.append(
            "HEAL/ASK: missing hosts in day1_map/golden/env for: "
            + ", ".join(missing_host)
            + " — ask human once or place golden_join.json (see config/corporate_golden_join.example.json)."
        )
    if appgate_blocked:
        advice.append(
            "APPGATE: hosts known but not reachable for: "
            + ", ".join(appgate_blocked)
            + " — connect AppGate/ZTNA, then re-run probe; do not invent public gitlab.com."
        )
    if up == 0 and known == 0:
        advice.append(
            "EMPTY MAP: no Corporate hosts configured. Day-1 prompt: map environment; "
            "human_steps say 'AppGate then internal crawl' (golden_join)."
        )
    if up > 0:
        advice.append(f"HARMONY: {up}/{known or 1} critical surfaces reachable — crawl those first.")

    doc = {
        "ts": _ts(),
        "schema": "private-brain.corporate_infra_probe.v1",
        "appgate_hint": "Corporate path: AppGate → internal GitLab/Jira/Confluence/Library (KINGDOM_KEYS + golden_join)",
        "critical_known": known,
        "critical_reachable": up,
        "missing_host_surfaces": missing_host,
        "likely_appgate_blocked": appgate_blocked,
        "surfaces": results,
        "advice": advice,
        "docs_that_answer_this": [
            "package/docs/KINGDOM_KEYS.md — API shapes for GitLab/Jira/Confluence/Corporate Library/AWS",
            "config/corporate_golden_join.example.json — host fields + AppGate then internal crawl",
            "DAY1_PROMPTS.md — auto-discover kingdom prompt",
            "package/CORPORATE_PACKAGE_INDEX.md — PIP_INDEX_URL model",
            "config/enterprise.yaml — allowlist_hosts / block_public_presets",
        ],
        "docs_do_not_contain": [
            "Real Corporate hostnames (examples only until golden_join filled)",
            "Real tokens (secrets_store only)",
            "Live AppGate status (must probe on laptop with tunnel up)",
        ],
    }
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="Corporate infra / AppGate harmony probe")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    doc = run_probe()
    if args.write:
        path = _state() / "corporate_infra_probe.json"
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)
        # Also open scenario gaps if hosts missing
        try:
            from scenario_heal import synthesize_all

            if doc.get("missing_host_surfaces") or doc.get("likely_appgate_blocked"):
                synthesize_all(reason="corporate_infra_probe")
        except Exception:
            pass
    text = json.dumps(doc, indent=2)
    print(text if args.json or True else text)
    # exit 0 always for probe (informational); CI should not hard-fail on AppGate
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
