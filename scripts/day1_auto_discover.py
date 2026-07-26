#!/usr/bin/env python3
"""Day-1 auto discovery + intelligent kickoff (sanitized Corporate model).

Finds and acts on (soft-fail if missing — never invent secrets):

  1. Codex sessions under ~/.codex (and $CODEX_HOME) → ingest into graph
  2. Corporate Library package index (PIP_INDEX_URL / env / pip.conf / day1.env)
  3. Protected Gateway (trusted host / proxy / corporate-package-index env)
  4. Corporate GitLab roots → recursive crawl when URL+token available
  5. Local Neo4j (bolt://localhost etc.) → intelligent profile; keep-set only on GO

Public language only:
  Corporate Library = approved package repos
  Protected Gateway = proxied protected package gateway
  Corporate GitLab  = internal code forge
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from brain_lib import STATE_DIR, ensure_tree, read_json, resolve_brain_root, utc_now, write_json  # noqa: E402


def _log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(f"  · {msg}")


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


def _codex_homes() -> list[Path]:
    homes: list[Path] = []
    for key in ("CODEX_HOME",):
        v = os.environ.get(key)
        if v:
            homes.append(Path(v).expanduser())
    homes.append(_home() / ".codex")
    out: list[Path] = []
    seen: set[str] = set()
    for h in homes:
        try:
            r = str(h.resolve())
        except Exception:
            r = str(h)
        if r not in seen and Path(r).is_dir():
            seen.add(r)
            out.append(Path(r))
    return out


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            # bash export FOO=bar or FOO=bar or $env:FOO = "bar"
            line = re.sub(r"^export\s+", "", line)
            line = re.sub(r"^\$env:", "", line, flags=re.I)
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip().strip('"').strip("'")
                v = v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
    except Exception:
        pass
    return out


def _merge_env(d: dict[str, str]) -> None:
    for k, v in d.items():
        if v and not os.environ.get(k):
            os.environ[k] = v


def discover_env_files() -> dict[str, Any]:
    """Load day1 / corporate-package-index env fragments into process env (no overwrite)."""
    root = resolve_brain_root()
    candidates = [
        root / "day1.env",
        root / "corporate-package-index.env",
        root / "corporate.env",
        root / ".brain" / "state" / "day1.env",
        Path.cwd() / "tools" / "install" / "day1.env",
        Path.cwd() / "tools" / "install" / "corporate-package-index.env",
        Path.cwd() / "day1.env",
    ]
    kit = os.environ.get("PB_KIT_ROOT")
    if kit:
        candidates.extend(
            [
                Path(kit) / "tools" / "install" / "day1.env",
                Path(kit) / "tools" / "install" / "corporate-package-index.env",
            ]
        )
    loaded: list[str] = []
    merged: dict[str, str] = {}
    for p in candidates:
        d = _read_env_file(p)
        if d:
            loaded.append(str(p))
            merged.update({k: v for k, v in d.items() if k not in merged})
            _merge_env(d)
    return {"files": loaded, "keys": sorted(merged.keys())}


def discover_corporate_library() -> dict[str, Any]:
    """Corporate Library = approved pip/simple index (PIP_INDEX_URL / PB_PIP_INDEX_URL)."""
    idx = (
        os.environ.get("PB_PIP_INDEX_URL")
        or os.environ.get("PIP_INDEX_URL")
        or os.environ.get("UV_INDEX_URL")
        or ""
    ).strip()
    trusted = (
        os.environ.get("PB_PIP_TRUSTED_HOST")
        or os.environ.get("PIP_TRUSTED_HOST")
        or ""
    ).strip()
    sources: list[str] = []
    if idx:
        sources.append("env")

    # pip.conf / pip.ini
    pip_conf_paths = [
        _home() / ".pip" / "pip.conf",
        _home() / "pip" / "pip.ini",
        _home() / "AppData" / "Roaming" / "pip" / "pip.ini",
        Path("/etc/pip.conf"),
    ]
    for conf in pip_conf_paths:
        if not conf.is_file():
            continue
        try:
            text = conf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        m = re.search(r"index-url\s*=\s*(\S+)", text, re.I)
        if m and not idx:
            idx = m.group(1).strip()
            sources.append(str(conf))
        m2 = re.search(r"trusted-host\s*=\s*(\S+)", text, re.I)
        if m2 and not trusted:
            trusted = m2.group(1).strip()

    # day1 map prior
    map_path = STATE_DIR / "day1_map.json"
    if map_path.is_file() and not idx:
        try:
            m = read_json(map_path)
            ans = (m.get("answers") or m) if isinstance(m, dict) else {}
            idx = str(ans.get("index_url") or ans.get("pip_index_url") or "").strip() or idx
            if idx:
                sources.append("day1_map")
        except Exception:
            pass

    if idx:
        os.environ.setdefault("PIP_INDEX_URL", idx)
        os.environ.setdefault("PB_PIP_INDEX_URL", idx)
    if trusted:
        os.environ.setdefault("PIP_TRUSTED_HOST", trusted)
        os.environ.setdefault("PB_PIP_TRUSTED_HOST", trusted)

    host = ""
    if idx:
        try:
            host = urlparse(idx).hostname or ""
        except Exception:
            host = ""

    return {
        "found": bool(idx),
        "index_url": idx[:200] if idx else "",
        "trusted_host": trusted[:120] if trusted else host,
        "sources": sources,
        "label": "Corporate Library",
    }


def discover_protected_gateway() -> dict[str, Any]:
    """Protected Gateway = proxied/protected package or HTTPS path (proxy + trusted host)."""
    proxies = {
        "https_proxy": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "",
        "http_proxy": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "",
        "all_proxy": os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or "",
    }
    # Corporate package index env often names the gateway host
    gw = (
        os.environ.get("PB_PROTECTED_GATEWAY")
        or os.environ.get("PB_PIP_TRUSTED_HOST")
        or os.environ.get("PIP_TRUSTED_HOST")
        or ""
    ).strip()
    lib = discover_corporate_library()
    if not gw and lib.get("trusted_host"):
        gw = str(lib["trusted_host"])
    if not gw and lib.get("index_url"):
        try:
            gw = urlparse(str(lib["index_url"])).hostname or ""
        except Exception:
            pass

    found = bool(gw or any(proxies.values()))
    return {
        "found": found,
        "gateway_host": gw[:160],
        "proxies": {k: (v[:80] + "…" if len(v) > 80 else v) for k, v in proxies.items() if v},
        "label": "Protected Gateway",
        "note": "soft if missing — headless Corporate Library path still valid",
    }


def discover_gitlab_roots() -> dict[str, Any]:
    """Find Corporate GitLab instance + root groups for recursive crawl."""
    urls: list[str] = []
    groups: list[str] = []
    for key in (
        "PB_GITLAB_URL",
        "GITLAB_URL",
        "CI_SERVER_URL",
        "GITLAB_HOST",
    ):
        v = (os.environ.get(key) or "").strip().rstrip("/")
        if v and v not in urls:
            if not v.startswith("http"):
                v = "https://" + v
            urls.append(v)
    for key in ("PB_GITLAB_GROUP", "GITLAB_GROUP", "CI_PROJECT_NAMESPACE", "CI_PROJECT_ROOT_NAMESPACE"):
        v = (os.environ.get(key) or "").strip()
        if v and v not in groups:
            groups.append(v)

    # day1 map
    map_path = STATE_DIR / "day1_map.json"
    if map_path.is_file():
        try:
            m = read_json(map_path)
            ans = (m.get("answers") or m) if isinstance(m, dict) else {}
            gl = str(ans.get("gitlab_url") or "").strip()
            if gl and gl not in urls:
                urls.append(gl.rstrip("/"))
            gg = str(ans.get("gitlab_group") or ans.get("group") or "").strip()
            if gg and gg not in groups:
                groups.append(gg)
        except Exception:
            pass

    # git remotes in cwd / kit
    remotes: list[str] = []
    for base in (Path.cwd(), resolve_brain_root(), Path(os.environ.get("PB_KIT_ROOT") or ".")):
        git_cfg = base / ".git" / "config"
        if not git_cfg.is_file():
            # walk up one
            git_cfg = base.parent / ".git" / "config"
        if git_cfg.is_file():
            try:
                text = git_cfg.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r"url\s*=\s*(\S+)", text):
                    remotes.append(m.group(1))
            except Exception:
                pass
    for r in remotes:
        # git@host:group/proj.git or https://host/group/proj.git
        host = ""
        path = ""
        if r.startswith("git@"):
            m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", r)
            if m:
                host, path = m.group(1), m.group(2)
        elif "://" in r:
            try:
                u = urlparse(r)
                host = u.hostname or ""
                path = (u.path or "").lstrip("/").removesuffix(".git")
            except Exception:
                pass
        if host and "github.com" not in host.lower():
            url = f"https://{host}"
            if url not in urls:
                urls.append(url)
            if path and "/" in path:
                root = path.split("/")[0]
                if root and root not in groups:
                    groups.append(root)

    token = (
        os.environ.get("GITLAB_TOKEN")
        or os.environ.get("PB_GITLAB_TOKEN")
        or os.environ.get("CI_JOB_TOKEN")
        or ""
    ).strip()

    return {
        "found": bool(urls),
        "instances": urls[:8],
        "groups": groups[:12],
        "has_token": bool(token),
        "token_env": "set" if token else "missing",
        "remotes_seen": len(remotes),
        "label": "Corporate GitLab",
    }


def discover_neo4j() -> dict[str, Any]:
    """Probe local/common Neo4j bolt endpoints — no credentials printed."""
    uri = (
        os.environ.get("NEO4J_URI")
        or os.environ.get("PB_NEO4J_URI")
        or os.environ.get("GRAPHENEDB_BOLT_URL")
        or ""
    ).strip()
    candidates: list[tuple[str, int]] = []
    if uri:
        try:
            u = urlparse(uri if "://" in uri else "bolt://" + uri)
            host = u.hostname or "127.0.0.1"
            port = u.port or 7687
            candidates.append((host, port))
        except Exception:
            candidates.append(("127.0.0.1", 7687))
    else:
        candidates = [
            ("127.0.0.1", 7687),
            ("localhost", 7687),
            ("127.0.0.1", 7688),
            ("127.0.0.1", 7474),  # http (presence only)
        ]

    open_ports: list[str] = []
    for host, port in candidates:
        try:
            with socket.create_connection((host, port), timeout=0.6):
                open_ports.append(f"{host}:{port}")
        except OSError:
            continue

    user = os.environ.get("NEO4J_USER") or os.environ.get("PB_NEO4J_USER") or ""
    # never return password
    has_auth = bool(
        os.environ.get("NEO4J_PASSWORD")
        or os.environ.get("PB_NEO4J_PASSWORD")
        or os.environ.get("NEO4J_AUTH")
    )

    return {
        "found": bool(open_ports),
        "endpoints": open_ports[:6],
        "uri_env": bool(uri),
        "has_auth_env": has_auth,
        "user_env_set": bool(user),
        "label": "Local Neo4j",
        "policy": "profile → keep/quarantine/reject → ingest good only (never bulk-trust dirty)",
    }


def ingest_sessions(*, max_files: int = 5000, force: bool = False, quiet: bool = False) -> dict[str, Any]:
    _log("sessions · discover + ingest under CODEX_HOME / ~/.codex", quiet)
    try:
        from smart_discover import run_discover_ingest

        out = run_discover_ingest(
            max_files=max_files,
            force=force,
            agent_id="day1-auto-sessions",
        )
        return {
            "ok": True,
            "discovered": out.get("discovered"),
            "ingested": out.get("ingested"),
            "skipped": out.get("skipped"),
            "by_kind": out.get("by_kind"),
            "homes": [str(h) for h in _codex_homes()],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "homes": [str(h) for h in _codex_homes()]}


def crawl_gitlab(*, deep: bool = True, quiet: bool = False, max_projects: int = 25) -> dict[str, Any]:
    gl = discover_gitlab_roots()
    if not gl.get("found"):
        return {"ok": False, "skipped": True, "reason": "no_gitlab_root_found", **gl}
    if not gl.get("has_token") and os.environ.get("PB_GITLAB_ALLOW_ANON") not in ("1", "true", "yes"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "no_token_set_GITLAB_TOKEN_or_PB_GITLAB_TOKEN",
            **gl,
            "hint": "set token in secrets store / env then re-run day1_auto_discover --gitlab",
        }

    instance = (gl.get("instances") or [""])[0]
    group = (gl.get("groups") or [""])[0]
    if not instance:
        return {"ok": False, "skipped": True, "reason": "empty_instance", **gl}

    _log(f"gitlab · recursive crawl instance={instance} group={group or '(root-auto)'}", quiet)
    py = sys.executable
    script = _SCRIPTS / "gitlab_ingest.py"
    if not script.is_file():
        return {"ok": False, "error": "gitlab_ingest.py missing", **gl}

    args = [
        py,
        str(script),
        "--instance",
        instance,
        "--deep" if deep else "--shallow",
        "--max-projects",
        str(max_projects),
        "--max-subgroups",
        "80",
        "--json",
    ]
    if group:
        args += ["--group", group]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    env["PB_ENTERPRISE"] = "1"
    try:
        proc = subprocess.run(
            args,
            env=env,
            cwd=str(resolve_brain_root()),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("PB_GITLAB_CRAWL_TIMEOUT", "1800")),
        )
        body = (proc.stdout or "").strip()
        parsed: dict[str, Any] = {}
        if body.startswith("{"):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                pass
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "instance": instance,
            "group": group,
            "result": parsed or {"stdout_tail": body[-1500:], "stderr_tail": (proc.stderr or "")[-800:]},
            **{k: gl[k] for k in ("has_token", "instances", "groups")},
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "gitlab_crawl_timeout", "instance": instance, "group": group}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "instance": instance, "group": group}


def profile_neo4j(*, quiet: bool = False, ingest_keep: bool = False) -> dict[str, Any]:
    """Intelligent Neo4j: connect if possible, profile labels, never bulk-trust."""
    neo = discover_neo4j()
    if not neo.get("found") and not neo.get("uri_env"):
        return {"ok": False, "skipped": True, "reason": "no_local_neo4j_detected", **neo}

    _log(f"neo4j · endpoints={neo.get('endpoints')} uri_env={neo.get('uri_env')}", quiet)

    # Optional driver
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        report = {
            "ok": True,
            "profiled": False,
            "reason": "neo4j_driver_not_installed",
            "policy": neo.get("policy"),
            "endpoints": neo.get("endpoints"),
            "next": "pip install neo4j from Corporate Library, set NEO4J_URI + secrets, re-run",
            "intelligent": {
                "phase": "detect_only",
                "keep": [],
                "quarantine": ["all_until_profiled"],
                "reject": [],
            },
        }
        write_json(STATE_DIR / "neo4j_day1_profile.json", {"ts": utc_now(), **report})
        return report

    uri = os.environ.get("NEO4J_URI") or os.environ.get("PB_NEO4J_URI") or ""
    if not uri and neo.get("endpoints"):
        hostport = neo["endpoints"][0]
        # prefer bolt
        if hostport.endswith(":7474"):
            hostport = hostport.rsplit(":", 1)[0] + ":7687"
        uri = f"bolt://{hostport}"
    user = os.environ.get("NEO4J_USER") or os.environ.get("PB_NEO4J_USER") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD") or os.environ.get("PB_NEO4J_PASSWORD") or ""
    if not password:
        report = {
            "ok": True,
            "profiled": False,
            "reason": "no_password_in_env",
            "uri": uri[:80],
            "policy": neo.get("policy"),
            "next": "set NEO4J_PASSWORD via secrets store (never commit)",
            "intelligent": {
                "phase": "auth_required",
                "keep": [],
                "quarantine": ["awaiting_auth"],
                "reject": [],
            },
        }
        write_json(STATE_DIR / "neo4j_day1_profile.json", {"ts": utc_now(), **report})
        return report

    labels: list[dict[str, Any]] = []
    rels: list[dict[str, Any]] = []
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # label counts
            recs = session.run(
                "CALL db.labels() YIELD label "
                "CALL { WITH label MATCH (n) WHERE label IN labels(n) RETURN count(n) AS c } "
                "RETURN label, c ORDER BY c DESC LIMIT 40"
            )
            # fallback simpler if procedure fails
            try:
                labels = [{"label": r["label"], "count": int(r["c"])} for r in recs]
            except Exception:
                r2 = session.run(
                    "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c "
                    "ORDER BY c DESC LIMIT 40"
                )
                labels = [{"label": r["label"], "count": int(r["c"])} for r in r2]
            try:
                r3 = session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c "
                    "ORDER BY c DESC LIMIT 40"
                )
                rels = [{"type": r["t"], "count": int(r["c"])} for r in r3]
            except Exception:
                rels = []
        driver.close()
    except Exception as e:
        report = {
            "ok": False,
            "profiled": False,
            "error": str(e)[:240],
            "uri": uri[:80],
            "policy": neo.get("policy"),
        }
        write_json(STATE_DIR / "neo4j_day1_profile.json", {"ts": utc_now(), **report})
        return report

    # Intelligent rules (no bulk ingest by default)
    keep: list[str] = []
    quarantine: list[str] = []
    reject: list[str] = []
    publicish = re.compile(r"web|scrape|http|public|www|crawl|external", re.I)
    junk = re.compile(r"test|tmp|temp|debug|foo|bar|sample", re.I)
    for row in labels:
        lab = str(row.get("label") or "")
        c = int(row.get("count") or 0)
        if junk.search(lab) or c == 0:
            reject.append(lab)
        elif publicish.search(lab):
            quarantine.append(lab)
        elif c >= 1:
            keep.append(lab)

    intelligent = {
        "phase": "profiled",
        "keep": keep[:40],
        "quarantine": quarantine[:40],
        "reject": reject[:40],
        "rule": "ingest KEEP only after explicit GO (PB_NEO4J_INGEST_KEEP=1)",
    }

    ingested = None
    if ingest_keep or os.environ.get("PB_NEO4J_INGEST_KEEP") in ("1", "true", "yes"):
        # Minimal safe ingest: write profile + keep labels as schema nodes (not full dump)
        try:
            from ingest_bus import ingest_node

            for lab in keep[:30]:
                ingest_node(
                    {
                        "id": f"neo4j:label:{lab}",
                        "type": "schema",
                        "source": "neo4j_intelligent",
                        "title": f"Neo4j label {lab}",
                        "tier": "T2",
                        "tags": ["neo4j", "keep", lab],
                        "content": f"Neo4j KEEP label `{lab}` from intelligent profile. Full node dump not performed.",
                    }
                )
            ingested = {"labels_as_schema": len(keep[:30]), "mode": "schema_only_not_bulk"}
        except Exception as e:
            ingested = {"error": str(e)[:160]}

    report = {
        "ok": True,
        "profiled": True,
        "uri": uri[:80],
        "labels": labels[:40],
        "rel_types": rels[:40],
        "intelligent": intelligent,
        "ingested": ingested,
        "policy": neo.get("policy"),
    }
    write_json(STATE_DIR / "neo4j_day1_profile.json", {"ts": utc_now(), **report})
    return report


def run(
    *,
    sessions: bool = True,
    library: bool = True,
    gateway: bool = True,
    gitlab: bool = True,
    neo4j: bool = True,
    gitlab_crawl: bool = True,
    neo4j_ingest_keep: bool = False,
    quiet: bool = False,
    force_sessions: bool = False,
) -> dict[str, Any]:
    ensure_tree()
    report: dict[str, Any] = {
        "ts": utc_now(),
        "suite": "day1_auto_discover",
        "phases": {},
    }
    if not quiet:
        print("==============================================")
        print(" Day-1 AUTO DISCOVER (Corporate-sanitized)")
        print(" sessions · library · gateway · gitlab · neo4j")
        print("==============================================")

    env_files = discover_env_files()
    report["env_files"] = env_files
    _log(f"env files loaded: {len(env_files.get('files') or [])}", quiet)

    if sessions:
        report["phases"]["sessions"] = ingest_sessions(force=force_sessions, quiet=quiet)
        s = report["phases"]["sessions"]
        _log(
            f"sessions: ok={s.get('ok')} discovered={s.get('discovered')} ingested={s.get('ingested')}",
            quiet,
        )

    if library:
        report["phases"]["corporate_library"] = discover_corporate_library()
        lib = report["phases"]["corporate_library"]
        _log(
            f"Corporate Library: found={lib.get('found')} host={lib.get('trusted_host') or 'n/a'}",
            quiet,
        )

    if gateway:
        report["phases"]["protected_gateway"] = discover_protected_gateway()
        gw = report["phases"]["protected_gateway"]
        _log(
            f"Protected Gateway: found={gw.get('found')} host={gw.get('gateway_host') or 'n/a'}",
            quiet,
        )

    if gitlab:
        gl_disc = discover_gitlab_roots()
        report["phases"]["gitlab_discover"] = gl_disc
        _log(
            f"GitLab: found={gl_disc.get('found')} instances={gl_disc.get('instances')} "
            f"groups={gl_disc.get('groups')} token={gl_disc.get('token_env')}",
            quiet,
        )
        if gitlab_crawl and gl_disc.get("found"):
            report["phases"]["gitlab_crawl"] = crawl_gitlab(quiet=quiet)
            c = report["phases"]["gitlab_crawl"]
            _log(
                f"GitLab crawl: ok={c.get('ok')} skipped={c.get('skipped')} reason={c.get('reason') or c.get('error') or 'ran'}",
                quiet,
            )
        else:
            report["phases"]["gitlab_crawl"] = {"skipped": True, "reason": "discover_only_or_not_found"}

    if neo4j:
        report["phases"]["neo4j"] = profile_neo4j(quiet=quiet, ingest_keep=neo4j_ingest_keep)
        n = report["phases"]["neo4j"]
        _log(
            f"Neo4j: found={n.get('found', n.get('profiled'))} profiled={n.get('profiled')} "
            f"phase={(n.get('intelligent') or {}).get('phase')}",
            quiet,
        )

    # Persist full report for Codex / GodsEye / doctor
    write_json(STATE_DIR / "day1_auto_discover.json", report)
    # Compact inject for hooks
    compact = {
        "ts": report["ts"],
        "sessions": (report.get("phases") or {}).get("sessions"),
        "corporate_library": {
            "found": ((report.get("phases") or {}).get("corporate_library") or {}).get("found"),
            "host": ((report.get("phases") or {}).get("corporate_library") or {}).get("trusted_host"),
        },
        "protected_gateway": {
            "found": ((report.get("phases") or {}).get("protected_gateway") or {}).get("found"),
            "host": ((report.get("phases") or {}).get("protected_gateway") or {}).get("gateway_host"),
        },
        "gitlab": {
            "found": ((report.get("phases") or {}).get("gitlab_discover") or {}).get("found"),
            "instances": ((report.get("phases") or {}).get("gitlab_discover") or {}).get("instances"),
            "crawl_ok": ((report.get("phases") or {}).get("gitlab_crawl") or {}).get("ok"),
        },
        "neo4j": {
            "found": bool(((report.get("phases") or {}).get("neo4j") or {}).get("endpoints")
                          or ((report.get("phases") or {}).get("neo4j") or {}).get("profiled")),
            "phase": (((report.get("phases") or {}).get("neo4j") or {}).get("intelligent") or {}).get("phase"),
        },
    }
    write_json(STATE_DIR / "day1_auto_discover_compact.json", compact)

    # Golden config = Phase-1 map law so Phase-2 can start (no secrets)
    try:
        from golden_config import write_golden

        g = write_golden(compact_chars=int(os.environ.get("PB_GOLDEN_COMPACT_CHARS", "12000")))
        report["phases"]["golden"] = {
            "ok": True,
            "complete": g.get("complete"),
            "paths": g.get("paths"),
            "coworker_join": g.get("coworker_join"),
        }
        _log(
            f"golden: written join={g.get('coworker_join')} complete={g.get('complete')}",
            quiet,
        )
    except Exception as e:
        report["phases"]["golden"] = {"ok": False, "error": str(e)[:200]}
        _log(f"golden: soft-fail {e}", quiet)

    if not quiet:
        print("----------------------------------------------")
        print(f" report: {STATE_DIR / 'day1_auto_discover.json'}")
        print(" soft-missing is OK — re-run after env/tokens set")
        print("==============================================")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Day-1 auto discover Corporate surfaces")
    ap.add_argument("--quiet", "-q", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--force-sessions", action="store_true")
    ap.add_argument("--no-sessions", action="store_true")
    ap.add_argument("--no-library", action="store_true")
    ap.add_argument("--no-gateway", action="store_true")
    ap.add_argument("--no-gitlab", action="store_true")
    ap.add_argument("--no-gitlab-crawl", action="store_true", help="Discover GitLab only, do not crawl")
    ap.add_argument("--no-neo4j", action="store_true")
    ap.add_argument("--neo4j-ingest-keep", action="store_true", help="After profile, ingest KEEP labels as schema nodes")
    args = ap.parse_args()
    r = run(
        sessions=not args.no_sessions,
        library=not args.no_library,
        gateway=not args.no_gateway,
        gitlab=not args.no_gitlab,
        neo4j=not args.no_neo4j,
        gitlab_crawl=not args.no_gitlab_crawl,
        neo4j_ingest_keep=args.neo4j_ingest_keep,
        quiet=args.quiet or args.json,
        force_sessions=args.force_sessions,
    )
    if args.json:
        print(json.dumps(r, indent=2, default=str))
    # soft success if sessions phase ran or anything found
    phases = r.get("phases") or {}
    sess_ok = (phases.get("sessions") or {}).get("ok")
    any_found = any(
        (phases.get(k) or {}).get("found")
        for k in ("corporate_library", "protected_gateway", "gitlab_discover")
    ) or (phases.get("neo4j") or {}).get("profiled") or (phases.get("neo4j") or {}).get("found")
    return 0 if sess_ok or any_found or args.json else 0  # always 0 soft — discovery never hard-fails Day-1


if __name__ == "__main__":
    raise SystemExit(main())
