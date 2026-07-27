#!/usr/bin/env python3
"""Intelligent Day-1 first start - map environment and choose package route.

Routes:
  corporate_library   - Corporate Library (Corporate Package Index) (default Corporate approved pip index)
  aws    - AWS CodeArtifact / Government Cloud-style approved index
  headless - stdlib-only core (no third-party; GodsEye off)

Writes:
  - corporate-package-index.env / day1.env (kit root + brain home)
  - enterprise.yaml program/hosts/classification
  - .brain/state/day1_map.json (reproducible map + audit)
  - ~/.codex/prompts/private-brain-day1.md (Codex sees day-1 map)
  - vault/Inputs note if vault exists

Usage:
  python3 day1_first_start.py              # interactive
  python3 day1_first_start.py --yes --route corporate_library --program X
  python3 day1_first_start.py --probe-only # print map JSON, no writes
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Windows runners default to cp1252/charmap - box-drawing and em-dashes crash prints.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")


def _force_utf8_stdio() -> None:
    """Hard requirement: never die printing status on Windows charmap consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            try:
                import io

                buf = getattr(stream, "buffer", None)
                if buf is not None:
                    wrapper = io.TextIOWrapper(buf, encoding="utf-8", errors="replace", line_buffering=True)
                    if stream is sys.stdout:
                        sys.stdout = wrapper  # type: ignore[assignment]
                    else:
                        sys.stderr = wrapper  # type: ignore[assignment]
            except Exception:
                pass


def _safe_print(*args: Any, file: Any = None, **kwargs: Any) -> None:
    """Print that never raises UnicodeEncodeError (Windows cp1252)."""
    target = file if file is not None else sys.stdout
    try:
        print(*args, file=target, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        text = text.encode("ascii", errors="replace").decode("ascii")
        try:
            print(text, file=target, **kwargs)
        except Exception:
            pass


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _home() -> Path:
    return Path.home()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (_home() / ".codex"))


def brain_home() -> Path:
    return Path(os.environ.get("PRIVATE_BRAIN_HOME") or (codex_home() / "private-brain"))


def kit_root() -> Path:
    """Installer kit root (mac/ or windows/ folder)."""
    env = os.environ.get("PB_KIT_ROOT")
    if env:
        return Path(env)
    # scripts/ -> package/ -> kit root (mac|windows)
    here = Path(__file__).resolve()
    # .../package/scripts/day1_first_start.py -> kit = parents[2]
    if here.parent.name == "scripts" and here.parent.parent.name == "package":
        return here.parent.parent.parent
    if here.parent.name == "scripts":
        return here.parent.parent
    return Path.cwd()


def probe_environment() -> dict[str, Any]:
    """Map machine + Codex + Python without mutating state."""
    ch = codex_home()
    bh = brain_home()
    sysname = platform.system().lower()
    is_mac = sysname == "darwin"
    is_win = sysname == "windows" or sysname.startswith("win")
    py = sys.executable
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    codex_bin = (
        shutil.which("codex")
        or (str(Path("/Applications/ChatGPT.app/Contents/Resources/codex")) if is_mac else None)
        or (str(_home() / "AppData/Local/Programs/Codex/codex.exe") if is_win else None)
    )
    if codex_bin and not Path(codex_bin).exists():
        codex_bin = shutil.which("codex")

    hooks = ch / "hooks.json"
    beast = _home() / "bin" / ("beastMode.cmd" if is_win else "beastMode")
    if not beast.exists():
        beast = bh / "scripts" / ("beastMode.cmd" if is_win else "beastMode")

    map_path = bh / ".brain" / "state" / "day1_map.json"
    prior = {}
    if map_path.exists():
        try:
            prior = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception:
            prior = {"path": str(map_path), "parse_error": True}

    return {
        "ts": _ts(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "is_mac": is_mac,
            "is_windows": is_win,
            "platform": platform.platform(),
        },
        "python": {"executable": py, "version": py_ver, "ok": sys.version_info >= (3, 10)},
        "codex": {
            "CODEX_HOME": str(ch),
            "hooks_json": hooks.exists(),
            "binary": codex_bin,
            "binary_found": bool(codex_bin and Path(str(codex_bin)).exists()),
            "config_toml": (ch / "config.toml").exists() or (ch / "beast-enterprise.config.toml").exists(),
        },
        "private_brain": {
            "PRIVATE_BRAIN_HOME": str(bh),
            "installed": (bh / "scripts" / "orchestrate.py").exists(),
            "beastMode": str(beast) if beast.exists() else None,
            "enterprise_on": (bh / ".brain" / "state" / "enterprise.on").exists()
            or os.environ.get("PB_ENTERPRISE") == "1",
            "day1_map_exists": map_path.exists(),
            "day1_map_path": str(map_path),
            "prior_route": (prior.get("route") if isinstance(prior, dict) else None),
        },
        "env_hints": {
            "PIP_INDEX_URL": os.environ.get("PIP_INDEX_URL") or os.environ.get("PB_PIP_INDEX_URL"),
            "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION"),
            "AWS_PROFILE": os.environ.get("AWS_PROFILE"),
            "CODEARTIFACT_AUTH_TOKEN": bool(os.environ.get("CODEARTIFACT_AUTH_TOKEN")),
            "PB_PACKAGE_ROUTE": os.environ.get("PB_PACKAGE_ROUTE"),
        },
        "kit_root": str(kit_root()),
    }


ROUTES = {
    "corporate_library": {
        "label": "Corporate Library (Corporate Package Index)",
        "blurb": "Corporate Library PyPI remote (default Corporate). GodsEye optional wheels from Corporate Library.",
        "need_index": True,
        "index_kind": "corporate_library",
        "example_index": "https://REPLACE.corporate_library.corporate-package-index.example/corporate-package-index/api/pypi/pypi-virtual/simple",
        "example_host": "REPLACE.corporate_library.corporate-package-index.example",
        "require_corporate-package-index": True,
    },
    "aws": {
        "label": "AWS CodeArtifact / Government Cloud path",
        "blurb": "AWS-approved package index (CodeArtifact domain/repo). Use for Government Cloud / AWS-native teams.",
        "need_index": True,
        "index_kind": "aws",
        "example_index": "https://DOMAIN-ACCOUNT.d.codeartifact.REGION.amazonaws.com/pypi/REPO/simple/",
        "example_host": "DOMAIN-ACCOUNT.d.codeartifact.REGION.amazonaws.com",
        "require_corporate-package-index": True,
    },
    "headless": {
        "label": "Headless stdlib-only",
        "blurb": "No third-party pip. Core RAG-DAG + enterprise only. GodsEye OFF until an approved index is set.",
        "need_index": False,
        "index_kind": "none",
        "example_index": "",
        "example_host": "",
        "require_corporate-package-index": False,
    },
}


def _ask(prompt: str, default: str = "", noninteractive: bool = False) -> str:
    if noninteractive:
        return default
    try:
        raw = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    except EOFError:
        return default
    return raw if raw else default


def load_config_of_config() -> dict[str, Any]:
    """Consume scripted preflight board written by config_of_config.py."""
    path = Path(
        os.environ.get("PB_CONFIG_OF_CONFIG_JSON")
        or (brain_home() / ".brain" / "state" / "config_of_config.json")
    )
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def choose_route(probe: dict[str, Any], *, route: str | None, noninteractive: bool) -> str:
    env_route = (os.environ.get("PB_PACKAGE_ROUTE") or "").strip().lower()
    coc = load_config_of_config()
    coc_route = ((coc.get("suggest") or {}).get("recommended_route") or "").strip().lower()
    if route:
        r = route.strip().lower()
        if r in ("library", "corp", "corporate", "corporate-library"):
            r = "corporate_library"
        if r in ROUTES:
            return r
    if noninteractive:
        if env_route in ROUTES:
            return env_route
        if coc_route in ROUTES:
            return coc_route
        if probe.get("env_hints", {}).get("PIP_INDEX_URL"):
            return "corporate_library"
        if probe.get("env_hints", {}).get("AWS_DEFAULT_REGION") or probe.get("env_hints", {}).get(
            "CODEARTIFACT_AUTH_TOKEN"
        ):
            return "aws"
        return "headless"

    print()
    print("== Day-1 package route ==================================")
    print("Codex will use Private Brain as a sideload (not a separate product CLI).")
    print("Pick how optional packages (GodsEye pygame/OpenGL) are sourced.")
    print("Core RAG-DAG is always stdlib - it works on every route.")
    if coc:
        print(
            f"(config-of-config suggests: {coc_route or 'n/a'} | "
            f"SSM loopback ready={((coc.get('aws_shim') or {}).get('ssm_loopback_ready'))} | "
            f"AppGate~={((coc.get('appgate') or {}).get('likely_installed'))})"
        )
    print()
    # intelligent default: scripted board -> env -> heuristics
    default = "corporate_library"
    if probe.get("env_hints", {}).get("AWS_DEFAULT_REGION") or probe.get("env_hints", {}).get(
        "CODEARTIFACT_AUTH_TOKEN"
    ):
        default = "aws"
    if probe.get("private_brain", {}).get("prior_route") in ROUTES:
        default = str(probe["private_brain"]["prior_route"])
    if coc_route in ROUTES:
        default = coc_route
    if env_route in ROUTES:
        default = env_route

    for key, meta in ROUTES.items():
        print(f"  [{key}] {meta['label']}")
        print(f"       {meta['blurb']}")
    print()
    choice = _ask("Route (corporate_library / aws / headless)", default, noninteractive=False).lower()
    if choice not in ROUTES:
        print(f"Unknown route {choice!r} - using {default}")
        choice = default
    return choice


def collect_answers(
    probe: dict[str, Any],
    *,
    route: str,
    program: str | None,
    hosts: str | None,
    classification: str | None,
    index_url: str | None,
    trusted_host: str | None,
    ingest_url: str | None,
    godseye: bool | None,
    noninteractive: bool,
    gitlab: str | None = None,
    jira: str | None = None,
    confluence: str | None = None,
    codex_home_in: str | None = None,
    brain_home_in: str | None = None,
    aws_profile: str | None = None,
    aws_region: str | None = None,
    llm_base_url: str | None = None,
) -> dict[str, Any]:
    """Take as much user input as possible to point + configure the Codex install."""
    meta = ROUTES[route]
    prog = program or os.environ.get("PB_PROGRAM_ID") or ""
    klass = classification or os.environ.get("PB_CLASSIFICATION") or "INTERNAL"
    h = hosts if hosts is not None else os.environ.get("PB_ALLOWLIST_HOSTS") or ""
    idx = index_url or os.environ.get("PIP_INDEX_URL") or os.environ.get("PB_PIP_INDEX_URL") or ""
    th = trusted_host or os.environ.get("PIP_TRUSTED_HOST") or os.environ.get("PB_PIP_TRUSTED_HOST") or ""
    ing = ingest_url or ""
    ge = godseye
    gl = gitlab or os.environ.get("PB_GITLAB_URL") or os.environ.get("GITLAB_URL") or ""
    jr = jira or os.environ.get("PB_JIRA_URL") or os.environ.get("JIRA_URL") or ""
    cf = confluence or os.environ.get("PB_CONFLUENCE_URL") or os.environ.get("CONFLUENCE_URL") or ""
    ch_path = codex_home_in or os.environ.get("CODEX_HOME") or str(codex_home())
    bh_path = brain_home_in or os.environ.get("PRIVATE_BRAIN_HOME") or str(Path(ch_path) / "private-brain")
    aws_p = aws_profile or os.environ.get("AWS_PROFILE") or ""
    aws_r = aws_region or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "gov-region-1"
    llm = llm_base_url or os.environ.get("PB_LLM_BASE_URL") or ""
    appgate_ok = False
    model_pref = os.environ.get("PB_MODEL_PREFERENCE") or ""
    gl_tok = ""
    jr_tok = ""
    cf_tok = ""
    opensearch_ep = os.environ.get("PB_OPENSEARCH_ENDPOINT") or ""
    neptune_ep = os.environ.get("PB_NEPTUNE_ENDPOINT") or ""

    if not noninteractive:
        organism = os.environ.get("PB_ORGANISM_INTERVIEW", "") in ("1", "true", "yes")
        print()
        if organism:
            print("======================================================")
            print("  Hey - I'm wiring Private Brain into Codex.")
            print("  I'll ask a few things, then build the RAG-DAG myself.")
            print("  (Sessions under .codex are ingested automatically.)")
            print("======================================================")
        print()
        print("== Homes ================================================")
        print("Private Brain is a Codex SIDELOAD only (not a product CLI).")
        print(f"Detected CODEX_HOME={probe.get('codex', {}).get('CODEX_HOME')}")
        print(f"Detected brain={probe.get('private_brain', {}).get('PRIVATE_BRAIN_HOME')}")
        ch_path = _ask("CODEX_HOME (Codex install root)", ch_path)
        default_brain = str(Path(ch_path).expanduser() / "private-brain")
        if not brain_home_in and not os.environ.get("PRIVATE_BRAIN_HOME"):
            bh_path = default_brain
        bh_path = _ask("PRIVATE_BRAIN_HOME (sideload / .brain home)", bh_path or default_brain)

        print()
        print("== Identity =============================================")
        prog = _ask("Program id (what pilot program is this?)", prog or "corporate-pilot")
        klass = _ask("Classification", klass or "INTERNAL")
        h = _ask(
            "Internal host allowlist (comma-separated; empty = any non-public)",
            h,
        )

        # Packages first (human language)
        print()
        print("== Packages & libraries =================================")
        print("Hey - where can I download packages and libraries?")
        print("  (Corporate Library (Corporate Package Index) / CodeArtifact / or headless with no pip)")
        if meta["need_index"]:
            print(f"Route={route} | example: {meta['example_index']}")
            idx = _ask("Package index URL (PIP_INDEX_URL / Corporate Library simple URL)", idx or meta["example_index"])
            th = _ask("Trusted host for that index", th or meta["example_host"])
            _ask("Index username if needed (empty if anon/token-in-URL)", "")
            print("(Tokens stay local - never commit day1.env)")
        else:
            print("Headless route: core RAG needs no pip. GodsEye optional later.")

        print()
        print("== Code | plans | wiki ==================================")
        print("Where is the code stored? (GitLab group/project URL - blank to skip)")
        gl = _ask("GitLab URL", gl)
        print("Where are plans and issues stored? (Jira base URL - blank to skip)")
        jr = _ask("Jira URL", jr)
        print("Where is Confluence / the wiki? (blank to skip)")
        cf = _ask("Confluence URL", cf)
        app_raw = _ask("Is AppGate connected for those hosts right now? (y/N)", "n")
        appgate_ok = app_raw.lower() in ("y", "yes", "1", "true")
        print("Tokens (optional) - stored in secrets store / local env only:")
        gl_tok = _ask("GitLab token (empty=skip)", "")
        jr_tok = _ask("Jira token (empty=skip)", "")
        cf_tok = _ask("Confluence token (empty=skip)", "")

        print()
        print("== What happens next (automatic) ========================")
        print("  1) Ingest ALL Codex sessions under .codex/sessions")
        print("  2) Build local RAG-DAG + spin GodsEye for progress")
        print("  3) Polite crawls (no DDOS) if URLs given")
        print("  4) Max agent swarm on the shared graph")
        print("  5) Connect AWS gov-region-1 when you tell me how")

        # AWS - always ask (cloud RAG-DAG target); blanks = local-only until ready
        print()
        print("== AWS (where the RAG-DAG will live) ====================")
        print("How do you connect to AWS? Empty answers = stay local-only (still OK).")
        print("Target region default: gov-region-1 | models: edge gpt-5.1 | AWS enterprise-frontier-model")
        aws_p = _ask("AWS_PROFILE (SSO/profile name - empty if later)", aws_p)
        aws_r = _ask("AWS region", aws_r or "gov-region-1")
        llm = _ask(
            "LLM SHIM URL after SSM port-forward (e.g. http://127.0.0.1:8443/v1 - empty if not yet)",
            llm,
        )
        opensearch_ep = _ask("OpenSearch endpoint for vectors (empty if not yet)", opensearch_ep)
        neptune_ep = _ask("Neptune endpoint for graph (empty if not yet)", neptune_ep)
        model_pref = _ask(
            "When AWS is up, preferred frontier model (enterprise-frontier-model / nova-pro)",
            model_pref or "enterprise-frontier-model",
        )

        print()
        print("== GodsEye (live progress HUD) ==========================")
        print("GodsEye shows the graph while the system builds. Always-on recommended.")
        print("If you close it later, say 'show GodsEye' in Codex to reopen.")
        ge_raw = _ask("Spin up GodsEye when we build? (Y/n)", "y" if ge is not False else "y")
        ge = ge_raw.lower() not in ("n", "no", "0", "false")
        ing = _ask(
            "Optional extra seed URL (blank = use GitLab/Jira/Confluence above)",
            ing or gl or "",
        )
    else:
        prog = prog or "corporate-pilot"
        if meta["need_index"] and not idx:
            idx = meta["example_index"]
            th = th or meta["example_host"]
        if ge is None:
            ge = False
        gl_tok = os.environ.get("GITLAB_TOKEN") or ""
        jr_tok = os.environ.get("JIRA_TOKEN") or os.environ.get("JIRA_API_TOKEN") or ""
        cf_tok = os.environ.get("CONFLUENCE_TOKEN") or os.environ.get("CONFLUENCE_API_TOKEN") or ""
        appgate_ok = os.environ.get("PB_APPGATE_OK", "").lower() in ("1", "true", "yes")

    # Apply homes immediately so rest of process writes to the chosen install
    ch_path = str(Path(ch_path).expanduser())
    bh_path = str(Path(bh_path).expanduser())
    os.environ["CODEX_HOME"] = ch_path
    os.environ["PRIVATE_BRAIN_HOME"] = bh_path
    Path(bh_path).mkdir(parents=True, exist_ok=True)
    Path(ch_path).mkdir(parents=True, exist_ok=True)

    # Hosts from source URLs if allowlist empty
    host_list = [x.strip() for x in h.split(",") if x.strip()]
    if not host_list:
        for u in (gl, jr, cf):
            if u and u.startswith("http"):
                try:
                    host_list.append(urlparse(u).hostname or "")
                except Exception:
                    pass
        host_list = [x for x in host_list if x]

    return {
        "route": route,
        "route_label": meta["label"],
        "program_id": prog,
        "classification": klass,
        "allowlist_hosts": host_list,
        "pip_index_url": idx if meta["need_index"] else "",
        "pip_trusted_host": th if meta["need_index"] else "",
        "require_corporate-package-index": meta["require_corporate-package-index"],
        "godseye_wanted": bool(ge),
        "ingest_url": ing,
        "gitlab_url": gl,
        "jira_url": jr,
        "confluence_url": cf,
        "gitlab_token": gl_tok,
        "jira_token": jr_tok,
        "confluence_token": cf_tok,
        "appgate_connected": appgate_ok,
        "codex_home": ch_path,
        "private_brain_home": bh_path,
        "aws_profile": aws_p,
        "aws_region": aws_r,
        "llm_base_url": llm if (route == "aws" or llm) else "",
        "model_preference": model_pref,
        "opensearch_endpoint": opensearch_ep,
        "neptune_endpoint": neptune_ep,
        "probe": probe,
    }


def write_env_files(answers: dict[str, Any], kr: Path, bh: Path) -> list[str]:
    written: list[str] = []
    route = answers["route"]
    idx = answers.get("pip_index_url") or ""
    th = answers.get("pip_trusted_host") or ""
    prog = answers["program_id"]
    klass = answers["classification"]
    hosts = answers.get("allowlist_hosts") or []
    ch = answers.get("codex_home") or str(codex_home())

    def env_body_bash() -> str:
        lines = [
            "# Generated by day1_first_start.py - do not commit secrets",
            f"export PB_PACKAGE_ROUTE={route}",
            "export PB_ENTERPRISE=1",
            f'export PB_PROGRAM_ID="{prog}"',
            f'export PB_CLASSIFICATION="{klass}"',
            f'export CODEX_HOME="{ch}"',
            f'export PRIVATE_BRAIN_HOME="{bh}"',
            'export PATH="$HOME/bin:/Applications/ChatGPT.app/Contents/Resources:$PATH"',
        ]
        if hosts:
            lines.append(f'export PB_ALLOWLIST_HOSTS="{",".join(hosts)}"')
        if idx:
            lines.append(f'export PIP_INDEX_URL="{idx}"')
            lines.append(f'export PB_PIP_INDEX_URL="{idx}"')
        if th:
            lines.append(f'export PIP_TRUSTED_HOST="{th}"')
            lines.append(f'export PB_PIP_TRUSTED_HOST="{th}"')
        if answers.get("require_corporate-package-index"):
            lines.append("export PB_PIP_REQUIRE_CORPORATE_INDEX=1")
        else:
            lines.append("export PB_PIP_REQUIRE_CORPORATE_INDEX=0")
        if answers.get("godseye_wanted"):
            lines.append("export PB_GODSEYE_WANTED=1")
        if answers.get("gitlab_url"):
            lines.append(f'export PB_GITLAB_URL="{answers["gitlab_url"]}"')
        if answers.get("jira_url"):
            lines.append(f'export PB_JIRA_URL="{answers["jira_url"]}"')
        if answers.get("confluence_url"):
            lines.append(f'export PB_CONFLUENCE_URL="{answers["confluence_url"]}"')
        # Tokens go to secrets_store - day1.env only references "stored" (never plaintext tokens)
        if answers.get("gitlab_token"):
            lines.append("# GITLAB_TOKEN -> secrets_store (not written plaintext)")
            lines.append("export PB_SECRETS_LOADED=1")
        if answers.get("jira_token"):
            lines.append("# JIRA_TOKEN -> secrets_store")
        if answers.get("confluence_token"):
            lines.append("# CONFLUENCE_TOKEN -> secrets_store")
        if answers.get("appgate_connected"):
            lines.append("export PB_APPGATE_OK=1")
        if answers.get("aws_profile"):
            lines.append(f'export AWS_PROFILE="{answers["aws_profile"]}"')
        if answers.get("aws_region"):
            lines.append(f'export AWS_DEFAULT_REGION="{answers["aws_region"]}"')
            lines.append(f'export PB_AWS_REGION="{answers["aws_region"]}"')
        if answers.get("llm_base_url"):
            lines.append(f'export PB_LLM_BASE_URL="{answers["llm_base_url"]}"')
        if answers.get("model_preference"):
            lines.append(f'export PB_MODEL_PREFERENCE="{answers["model_preference"]}"')
        if answers.get("opensearch_endpoint"):
            lines.append(f'export PB_OPENSEARCH_ENDPOINT="{answers["opensearch_endpoint"]}"')
        if answers.get("neptune_endpoint"):
            lines.append(f'export PB_NEPTUNE_ENDPOINT="{answers["neptune_endpoint"]}"')
        return "\n".join(lines) + "\n"

    def env_body_ps1() -> str:
        lines = [
            "# Generated by day1_first_start.py - do not commit secrets",
            f'$env:PB_PACKAGE_ROUTE = "{route}"',
            '$env:PB_ENTERPRISE = "1"',
            f'$env:PB_PROGRAM_ID = "{prog}"',
            f'$env:PB_CLASSIFICATION = "{klass}"',
            f'$env:CODEX_HOME = "{ch}"',
            f'$env:PRIVATE_BRAIN_HOME = "{bh}"',
            f'$env:Path = "$env:USERPROFILE\\bin;" + $env:Path',
        ]
        if hosts:
            lines.append(f'$env:PB_ALLOWLIST_HOSTS = "{",".join(hosts)}"')
        if idx:
            lines.append(f'$env:PIP_INDEX_URL = "{idx}"')
            lines.append(f'$env:PB_PIP_INDEX_URL = "{idx}"')
        if th:
            lines.append(f'$env:PIP_TRUSTED_HOST = "{th}"')
            lines.append(f'$env:PB_PIP_TRUSTED_HOST = "{th}"')
        if answers.get("require_corporate-package-index"):
            lines.append('$env:PB_PIP_REQUIRE_CORPORATE_INDEX = "1"')
        else:
            lines.append('$env:PB_PIP_REQUIRE_CORPORATE_INDEX = "0"')
        if answers.get("godseye_wanted"):
            lines.append('$env:PB_GODSEYE_WANTED = "1"')
        if answers.get("gitlab_url"):
            lines.append(f'$env:PB_GITLAB_URL = "{answers["gitlab_url"]}"')
        if answers.get("jira_url"):
            lines.append(f'$env:PB_JIRA_URL = "{answers["jira_url"]}"')
        if answers.get("confluence_url"):
            lines.append(f'$env:PB_CONFLUENCE_URL = "{answers["confluence_url"]}"')
        if answers.get("gitlab_token") or answers.get("jira_token") or answers.get("confluence_token"):
            lines.append("# Tokens in secrets_store - load with: python scripts/secrets_store.py load-env")
            lines.append('$env:PB_SECRETS_LOADED = "1"')
        if answers.get("appgate_connected"):
            lines.append('$env:PB_APPGATE_OK = "1"')
        if answers.get("aws_profile"):
            lines.append(f'$env:AWS_PROFILE = "{answers["aws_profile"]}"')
        if answers.get("aws_region"):
            lines.append(f'$env:AWS_DEFAULT_REGION = "{answers["aws_region"]}"')
            lines.append(f'$env:PB_AWS_REGION = "{answers["aws_region"]}"')
        if answers.get("llm_base_url"):
            lines.append(f'$env:PB_LLM_BASE_URL = "{answers["llm_base_url"]}"')
        if answers.get("model_preference"):
            lines.append(f'$env:PB_MODEL_PREFERENCE = "{answers["model_preference"]}"')
        if answers.get("opensearch_endpoint"):
            lines.append(f'$env:PB_OPENSEARCH_ENDPOINT = "{answers["opensearch_endpoint"]}"')
        if answers.get("neptune_endpoint"):
            lines.append(f'$env:PB_NEPTUNE_ENDPOINT = "{answers["neptune_endpoint"]}"')
        return "\n".join(lines) + "\n"

    # Store tokens in secrets_store (DPAPI/keyring/file) - never leave in plaintext env files
    try:
        from secrets_store import put_secret

        for key, ans_key in (
            ("GITLAB_TOKEN", "gitlab_token"),
            ("JIRA_TOKEN", "jira_token"),
            ("CONFLUENCE_TOKEN", "confluence_token"),
        ):
            val = answers.get(ans_key) or ""
            if val:
                put_secret(key, val)
                os.environ[key] = val  # available this process only
    except Exception:
        pass

    for base in (kr, bh, codex_home()):
        base.mkdir(parents=True, exist_ok=True)
        bash_path = base / "day1.env"
        bash_path.write_text(env_body_bash(), encoding="utf-8")
        try:
            os.chmod(bash_path, 0o600)
        except Exception:
            pass
        written.append(str(bash_path))
        # Corporate Library/AWS index also as corporate-package-index.env for SETUP compatibility (no tokens)
        if idx:
            art = base / "corporate-package-index.env"
            art.write_text(env_body_bash(), encoding="utf-8")
            try:
                os.chmod(art, 0o600)
            except Exception:
                pass
            written.append(str(art))
        ps1 = base / "day1.env.ps1"
        ps1.write_text(env_body_ps1(), encoding="utf-8")
        try:
            os.chmod(ps1, 0o600)
        except Exception:
            pass
        written.append(str(ps1))
        corporate_ps1 = base / "corporate.env.ps1"
        corporate_ps1.write_text(env_body_ps1(), encoding="utf-8")
        written.append(str(corporate_ps1))
        corporate = base / "corporate.env"
        corporate.write_text(env_body_bash(), encoding="utf-8")
        written.append(str(corporate))

    return written


def write_enterprise_yaml(answers: dict[str, Any], bh: Path) -> str | None:
    path = bh / "config" / "enterprise.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # minimal template
        path.write_text(
            "mode: enterprise\nprogram_id: unassigned\ndefault_classification: INTERNAL\n"
            "block_public_presets: true\nallowlist_hosts:\n  []\n",
            encoding="utf-8",
        )
    text = path.read_text(encoding="utf-8")
    prog = answers["program_id"]
    klass = answers["classification"]
    hosts = answers.get("allowlist_hosts") or []

    def set_scalar(key: str, val: str, body: str) -> str:
        pat = re.compile(rf"^{re.escape(key)}\s*:.*$", re.M)
        line = f"{key}: {val}"
        if pat.search(body):
            return pat.sub(line, body, count=1)
        return body + f"\n{line}\n"

    text = set_scalar("program_id", prog, text)
    text = set_scalar("default_classification", klass, text)
    text = set_scalar("package_route", answers["route"], text)
    block = "allowlist_hosts:\n" + (
        "".join(f"  - {h}\n" for h in hosts) if hosts else "  []\n"
    )
    if "allowlist_hosts:" in text:
        text = re.sub(r"allowlist_hosts:\s*(?:\n(?:\s+-\s+.+)*)?", block, text, count=1)
    else:
        text += "\n" + block
    path.write_text(text, encoding="utf-8")
    return str(path)


def write_codex_day1_prompt(answers: dict[str, Any], map_doc: dict[str, Any]) -> str:
    """Codex-visible day-1 map so the agent asks/continues intelligently."""
    prompts = codex_home() / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    path = prompts / "private-brain-day1.md"
    hosts = ", ".join(answers.get("allowlist_hosts") or []) or "(any non-public)"
    body = f"""---
description: Private Brain Day-1 map (enterprise pilot)
---
# Private Brain - Day-1 map (auto-generated)

You are running **Private Brain as a Codex sideload** (`beastMode --enterprise`).
Do **not** invent a separate product CLI.

## Route chosen
- **Package route:** `{answers["route"]}` - {answers.get("route_label")}
- **Program:** `{answers["program_id"]}`
- **Classification:** `{answers["classification"]}`
- **Allowlist hosts:** {hosts}
- **GodsEye wanted:** {answers.get("godseye_wanted")}
- **Index set:** {"yes" if answers.get("pip_index_url") else "no (headless OK)"}

## What you should do next in conversation
1. Confirm the route still matches the user's network (Corporate Library vs AWS vs headless).
2. If route is **corporate_library** or **aws** and index still has `REPLACE`, ask for the real approved index URL.
3. Prefer **internal** GitLab/Jira/Confluence ingest only - never public OSS presets under enterprise.
4. After install: cite node_ids; respect quarantine / pilot_ops_ready.
5. Corpus `pilot_ready` (public_ratio < 15%) needs **internal re-ingest** - do not claim purity is fixed by quarantine alone.

## Launch lines (user runs shell - you do not replace beastMode)
- Mac: `source day1.env && beastMode --enterprise`
- Windows: `. .\\day1.env.ps1; beastMode --enterprise`

## Map artifact
`{map_doc.get("path", "")}`
Generated: {map_doc.get("ts", "")}
"""
    path.write_text(body, encoding="utf-8")
    # Also AGENTS fragment if present
    agents = codex_home() / "AGENTS.private-brain-day1.md"
    agents.write_text(
        "# Private Brain Day-1\n\n"
        f"Route={answers['route']} Program={answers['program_id']} "
        f"Class={answers['classification']}. "
        "Sideload only. See prompts/private-brain-day1.md.\n",
        encoding="utf-8",
    )
    return str(path)


def persist_map(answers: dict[str, Any], written: list[str], prompt_path: str) -> dict[str, Any]:
    bh = brain_home()
    state = bh / ".brain" / "state"
    state.mkdir(parents=True, exist_ok=True)
    doc = {
        "ts": _ts(),
        "version": 1,
        "route": answers["route"],
        "route_label": answers.get("route_label"),
        "program_id": answers["program_id"],
        "classification": answers["classification"],
        "allowlist_hosts": answers.get("allowlist_hosts"),
        "pip_index_configured": bool(answers.get("pip_index_url")),
        "require_corporate-package-index": answers.get("require_corporate-package-index"),
        "godseye_wanted": answers.get("godseye_wanted"),
        "ingest_url": answers.get("ingest_url") or None,
        "os": (answers.get("probe") or {}).get("os"),
        "codex": (answers.get("probe") or {}).get("codex"),
        "files_written": written,
        "codex_prompt": prompt_path,
        "complete": True,
        "next": [
            "Run SETUP if not installed",
            "beastMode --enterprise --heal",
            "beastMode --enterprise --doctor",
            "beastMode --quarantine-public",
            "internal re-ingest for pilot_ready",
        ],
    }
    # never store full secrets-looking index with credentials in map - strip userinfo
    idx = answers.get("pip_index_url") or ""
    if idx:
        doc["pip_index_host"] = re.sub(r"^https?://([^/]+@)?", "", idx).split("/")[0]
    # non-secret source + home pointers for later technical steps
    doc["codex_home"] = answers.get("codex_home")
    doc["private_brain_home"] = answers.get("private_brain_home")
    doc["sources"] = {
        "gitlab": answers.get("gitlab_url") or None,
        "jira": answers.get("jira_url") or None,
        "confluence": answers.get("confluence_url") or None,
        "appgate_connected": bool(answers.get("appgate_connected")),
        "tokens_set": {
            "gitlab": bool(answers.get("gitlab_token")),
            "jira": bool(answers.get("jira_token")),
            "confluence": bool(answers.get("confluence_token")),
        },
    }
    doc["aws"] = {
        "profile": answers.get("aws_profile") or None,
        "region": answers.get("aws_region") or None,
        "llm_base_url": answers.get("llm_base_url") or None,
        "model_preference": answers.get("model_preference") or None,
    }
    path = state / "day1_map.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    doc["path"] = str(path)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from audit_lib import audit  # type: ignore

        audit(
            "day1_first_start",
            agent_id="day1",
            role="installer",
            result="ok",
            detail=f"route={answers['route']} program={answers['program_id']}",
            props={
                "route": answers["route"],
                "program_id": answers["program_id"],
                "godseye_wanted": answers.get("godseye_wanted"),
            },
        )
    except Exception:
        pass
    return doc


def print_banner(probe: dict[str, Any]) -> None:
    print("==============================================")
    print(" Private Brain - Day-1 First Start (map)")
    print("==============================================")
    osinfo = probe.get("os") or {}
    codex = probe.get("codex") or {}
    pb = probe.get("private_brain") or {}
    py = probe.get("python") or {}
    print(f" OS:        {osinfo.get('system')} {osinfo.get('machine')}")
    print(f" Python:    {py.get('version')} ({'OK' if py.get('ok') else 'NEED 3.10+'})")
    print(f" Codex:     binary={'yes' if codex.get('binary_found') else 'not on PATH'}")
    print(f"            CODEX_HOME={codex.get('CODEX_HOME')}")
    print(f"            hooks.json={'yes' if codex.get('hooks_json') else 'no (SETUP will install)'}")
    print(f" Brain:     installed={'yes' if pb.get('installed') else 'no'}")
    print(f"            prior_route={pb.get('prior_route') or '(none)'}")
    print(f" Kit:       {probe.get('kit_root')}")
    print()


def find_golden_join() -> Path | None:
    """Co-worker join pack - no secrets. Skip re-interview when present."""
    candidates = []
    kit = os.environ.get("PB_KIT_ROOT")
    if kit:
        candidates.append(Path(kit) / "golden_join.json")
    candidates.append(Path.cwd() / "golden_join.json")
    candidates.append(brain_home() / ".brain" / "state" / "golden_join.json")
    # shared kit next to package/
    here = Path(__file__).resolve()
    if here.parent.name == "scripts" and here.parent.parent.name == "package":
        candidates.append(here.parent.parent.parent / "golden_join.json")
    for p in candidates:
        if p.is_file():
            return p
    return None


def apply_golden_join(path: Path) -> dict[str, Any]:
    """Load join kit into env defaults for non-interactive day1."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("package_route"):
        os.environ["PB_PACKAGE_ROUTE"] = str(data["package_route"])
    if data.get("program_id"):
        os.environ["PB_PROGRAM_ID"] = str(data["program_id"])
    if data.get("classification"):
        os.environ["PB_CLASSIFICATION"] = str(data["classification"])
    if data.get("pip_index_url"):
        os.environ["PIP_INDEX_URL"] = str(data["pip_index_url"])
        os.environ["PB_PIP_INDEX_URL"] = str(data["pip_index_url"])
    if data.get("gitlab_url"):
        os.environ["PB_GITLAB_URL"] = str(data["gitlab_url"])
    if data.get("jira_url"):
        os.environ["PB_JIRA_URL"] = str(data["jira_url"])
    if data.get("confluence_url"):
        os.environ["PB_CONFLUENCE_URL"] = str(data["confluence_url"])
    if data.get("aws_region"):
        os.environ["PB_AWS_REGION"] = str(data["aws_region"])
        os.environ["AWS_DEFAULT_REGION"] = str(data["aws_region"])
    if data.get("llm_shim_url"):
        os.environ["PB_LLM_BASE_URL"] = str(data["llm_shim_url"])
    if data.get("opensearch_endpoint"):
        os.environ["PB_OPENSEARCH_ENDPOINT"] = str(data["opensearch_endpoint"])
    if data.get("neptune_endpoint"):
        os.environ["PB_NEPTUNE_ENDPOINT"] = str(data["neptune_endpoint"])
    hosts = data.get("allowlist_hosts") or []
    if hosts:
        os.environ["PB_ALLOWLIST_HOSTS"] = ",".join(hosts)
    if data.get("godseye_default") in ("1", "true", True, "yes"):
        os.environ["PB_GODSEYE"] = "1"
    return data


def main() -> int:
    _force_utf8_stdio()
    ap = argparse.ArgumentParser(description="Private Brain intelligent Day-1 first start")
    ap.add_argument("--yes", "-y", action="store_true", help="non-interactive")
    ap.add_argument("--route", choices=sorted(ROUTES.keys()), default=None)
    ap.add_argument("--program", default=None)
    ap.add_argument("--hosts", default=None)
    ap.add_argument("--classification", default=None)
    ap.add_argument("--index-url", default=None)
    ap.add_argument("--trusted-host", default=None)
    ap.add_argument("--ingest-url", default=None)
    ap.add_argument("--gitlab", default=None)
    ap.add_argument("--jira", default=None)
    ap.add_argument("--confluence", default=None)
    ap.add_argument("--codex-home", default=None, help="override CODEX_HOME")
    ap.add_argument("--brain-home", default=None, help="override PRIVATE_BRAIN_HOME")
    ap.add_argument("--aws-profile", default=None)
    ap.add_argument("--aws-region", default=None)
    ap.add_argument("--llm-base-url", default=None)
    ap.add_argument("--godseye", action="store_true", default=None)
    ap.add_argument("--no-godseye", action="store_true")
    ap.add_argument("--probe-only", action="store_true")
    ap.add_argument("--json", action="store_true", help="print result JSON")
    ap.add_argument("--join", default=None, help="path to golden_join.json (co-worker)")
    args = ap.parse_args()

    probe = probe_environment()
    if args.probe_only:
        print(json.dumps(probe, indent=2))
        return 0

    if not (probe.get("python") or {}).get("ok"):
        print("ERROR: Python 3.10+ required", file=sys.stderr)
        return 2

    # Co-worker magic: apply shared Corporate map, skip re-interview
    join_path = Path(args.join) if args.join else find_golden_join()
    join_data = None
    if join_path and join_path.is_file():
        try:
            join_data = apply_golden_join(join_path)
            args.yes = True  # noninteractive - map is known
            if not args.route and join_data.get("package_route") in ROUTES:
                args.route = join_data["package_route"]
            if not args.program and join_data.get("program_id"):
                args.program = join_data["program_id"]
            if not args.classification and join_data.get("classification"):
                args.classification = join_data["classification"]
            if not args.index_url and join_data.get("pip_index_url"):
                args.index_url = join_data["pip_index_url"]
            if not args.gitlab and join_data.get("gitlab_url"):
                args.gitlab = join_data["gitlab_url"]
            if not args.jira and join_data.get("jira_url"):
                args.jira = join_data["jira_url"]
            if not args.confluence and join_data.get("confluence_url"):
                args.confluence = join_data["confluence_url"]
            if not args.aws_region and join_data.get("aws_region"):
                args.aws_region = join_data["aws_region"]
            if not args.llm_base_url and join_data.get("llm_shim_url"):
                args.llm_base_url = join_data["llm_shim_url"]
            if not args.hosts and join_data.get("allowlist_hosts"):
                args.hosts = ",".join(join_data["allowlist_hosts"])
            print(f"== Co-worker join kit applied: {join_path}")
            print("   Your sessions will ingest next. Put YOUR tokens in secrets_store.")
            print("   Connect AWS when ready - same map. Daily: beastMode only.")
        except Exception as e:
            print(f"WARN: golden_join failed ({e}) - falling back to interview", file=sys.stderr)

    print_banner(probe)
    route = choose_route(probe, route=args.route, noninteractive=args.yes)
    ge = True if args.godseye else (False if args.no_godseye else None)
    if ge is None and join_data and join_data.get("godseye_default") in ("1", "true", True, "yes"):
        ge = True
    answers = collect_answers(
        probe,
        route=route,
        program=args.program,
        hosts=args.hosts,
        classification=args.classification,
        index_url=args.index_url,
        trusted_host=args.trusted_host,
        ingest_url=args.ingest_url,
        godseye=ge,
        noninteractive=args.yes,
        gitlab=args.gitlab,
        jira=args.jira,
        confluence=args.confluence,
        codex_home_in=args.codex_home,
        brain_home_in=args.brain_home,
        aws_profile=args.aws_profile,
        aws_region=args.aws_region,
        llm_base_url=args.llm_base_url,
    )
    # join kit may also have cloud endpoints not in collect CLI
    if join_data:
        if join_data.get("opensearch_endpoint") and not answers.get("opensearch_endpoint"):
            answers["opensearch_endpoint"] = join_data["opensearch_endpoint"]
            os.environ["PB_OPENSEARCH_ENDPOINT"] = str(join_data["opensearch_endpoint"])
        if join_data.get("neptune_endpoint") and not answers.get("neptune_endpoint"):
            answers["neptune_endpoint"] = join_data["neptune_endpoint"]
            os.environ["PB_NEPTUNE_ENDPOINT"] = str(join_data["neptune_endpoint"])

    kr = kit_root()
    # homes already applied in collect_answers
    bh = brain_home()
    bh.mkdir(parents=True, exist_ok=True)
    written = write_env_files(answers, kr, bh)
    ey = write_enterprise_yaml(answers, bh)
    if ey:
        written.append(ey)
    # prompt needs path - write map first stub then prompt
    map_stub = {"ts": _ts(), "path": str(bh / ".brain" / "state" / "day1_map.json")}
    prompt_path = write_codex_day1_prompt(answers, map_stub)
    written.append(prompt_path)
    doc = persist_map(answers, written, prompt_path)

    result = {
        "ok": True,
        "route": answers["route"],
        "program_id": answers["program_id"],
        "classification": answers["classification"],
        "day1_map": doc.get("path"),
        "codex_prompt": prompt_path,
        "ingest_url": answers.get("ingest_url") or None,
        "files": written[:12],
        "next_shell": {
            "mac": "source ./day1.env && ./SETUP.command && beastMode",
            "windows": ". .\\day1.env.ps1; .\\SETUP.ps1; beastMode",
        },
    }

    print()
    print("== Day-1 map complete - golden surface ready ===========")
    print(f" Route:     {answers['route']} ({answers['route_label']})")
    print(f" Program:   {answers['program_id']}")
    print(f" Class:     {answers['classification']}")
    print(f" CODEX_HOME={answers.get('codex_home')}")
    print(f" BRAIN_HOME={answers.get('private_brain_home')}")
    print(f" Sources:   gl={bool(answers.get('gitlab_url'))} jira={bool(answers.get('jira_url'))} conf={bool(answers.get('confluence_url'))}")
    print(f" AppGate:   connected={answers.get('appgate_connected')}")
    print(f" Map:       {doc.get('path')}")
    print(f" Codex:     {prompt_path}")
    print(f" Env:       day1.env / day1.env.ps1")
    if join_data:
        print(" Join:      co-worker kit applied - next: organism ingests YOUR sessions")
    print(" Next:      organism / beastMode (no heal/doctor parade)")
    print(f" Mermaid:   {bh}/docs/MERMAID.md")
    if answers.get("ingest_url"):
        print(f" Ingest:    {answers['ingest_url']} (after doctor)")
    print()
    print(" Technical steps (DAY1 wrapper / beastMode --day1 run these next):")
    if (probe.get("os") or {}).get("is_windows"):
        print("   . .\\day1.env.ps1")
        print("   SETUP -> beastMode --enterprise --heal -> --doctor")
        print("   optional: multi-agent crawl GitLab/Jira/Confluence")
    else:
        print("   source day1.env  (or $PRIVATE_BRAIN_HOME/day1.env)")
        print("   SETUP -> beastMode --enterprise --heal -> --doctor")
        print("   optional: multi-agent crawl GitLab/Jira/Confluence")
    print("==============================================")
    # export markers for DAY1 shell
    print(f"DAY1_CODEX_HOME={answers.get('codex_home')}")
    print(f"DAY1_BRAIN_HOME={answers.get('private_brain_home')}")
    if answers.get("gitlab_url"):
        print(f"DAY1_GITLAB={answers['gitlab_url']}")
    if answers.get("jira_url"):
        print(f"DAY1_JIRA={answers['jira_url']}")
    if answers.get("confluence_url"):
        print(f"DAY1_CONFLUENCE={answers['confluence_url']}")

    if args.json:
        print(json.dumps(result, indent=2))
    # machine-readable line for shell wrappers
    print(f"DAY1_ROUTE={answers['route']}")
    print(f"DAY1_PROGRAM={answers['program_id']}")
    if answers.get("ingest_url"):
        print(f"DAY1_INGEST_URL={answers['ingest_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
