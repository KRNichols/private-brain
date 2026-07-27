#!/usr/bin/env python3
"""
Unified URL ingestion entry for beastMode -ingestion.

Parses URL host and routes:
  GitLab      → gitlab_ingest.resolve_from_url + deep recursive crawl
  Jira        → crawl_public.crawl_jira  (issues.apache.org, *.atlassian.net)
  Confluence  → crawl_public.crawl_confluence (cwiki.apache.org, *atlassian.net/wiki)
  Unknown     → best-effort API detect, or clear error listing supported hosts

Defaults: deep + verbose; --max raises limits; polite --min-interval between calls.
After a successful ingest: distill_vault export_graph + sync (boss brain) if present.

Examples:
  python ingest_url.py --url https://gitlab.gnome.org/GNOME --deep -v
  python ingest_url.py --url https://issues.apache.org/jira --max
  python ingest_url.py --url https://cwiki.apache.org/confluence --resolve
  python ingest_url.py --list
  python ingest_url.py --preset gnome --max
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from brain_lib import build_snapshot, ensure_tree, resolve_brain_root

UA = "PrivateBrain-IngestURL/1.0 (+filesystem-rag-dag; research)"

SUPPORTED = {
    "gitlab": {
        "hosts": [
            "gitlab.com",
            "gitlab.gnome.org",
            "salsa.debian.org",
            "*.gitlab.* / self-hosted GitLab",
        ],
        "examples": [
            "https://gitlab.gnome.org/GNOME",
            "https://gitlab.com/gitlab-org",
            "https://salsa.debian.org/debian",
        ],
        "presets": ["gnome", "salsa", "gitlab", "freexian"],
    },
    "jira": {
        "hosts": [
            "issues.apache.org",
            "*.atlassian.net (Jira /jira path or cloud issues)",
        ],
        "examples": [
            "https://issues.apache.org/jira",
            "https://YOUR.atlassian.net/jira",
            "https://YOUR.atlassian.net/browse/PROJ",
        ],
    },
    "confluence": {
        "hosts": [
            "cwiki.apache.org",
            "*.atlassian.net/wiki",
        ],
        "examples": [
            "https://cwiki.apache.org/confluence",
            "https://YOUR.atlassian.net/wiki",
        ],
    },
}


def _normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("empty url")
    if "://" not in raw:
        raw = "https://" + raw
    return raw


def _http_probe(url: str, timeout: int = 12) -> tuple[int | None, str]:
    """Return (status_code or None, body_snippet). Soft-fail for detection."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:400]
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return e.code, body
    except Exception as e:
        return None, str(e)[:200]


def detect_kind(url: str) -> dict[str, Any]:
    """
    Classify URL → kind + base targets for crawlers.

    Returns dict with keys: kind, url, host, base, detail, extra
    kind ∈ gitlab | jira | confluence | unknown
    """
    raw = _normalize_url(url)
    u = urllib.parse.urlparse(raw)
    host = (u.netloc or "").lower()
    path = u.path or ""
    path_l = path.lower()
    scheme = u.scheme or "https"
    origin = f"{scheme}://{u.netloc}"

    # ── Explicit host / path rules ─────────────────────────────────
    # Confluence first (path /wiki beats generic atlassian)
    if host == "cwiki.apache.org" or path_l.startswith("/confluence") or "/wiki" in path_l.split("/")[0:3] or path_l.startswith("/wiki"):
        if host == "cwiki.apache.org":
            base = f"{origin}/confluence"
        elif path_l.startswith("/wiki"):
            base = f"{origin}/wiki"
        elif path_l.startswith("/confluence"):
            base = f"{origin}/confluence"
        else:
            base = origin
        # atlassian cloud wiki
        if host.endswith(".atlassian.net") and "/wiki" not in base:
            base = f"{origin}/wiki"
        return {
            "kind": "confluence",
            "url": raw,
            "host": host,
            "base": base.rstrip("/"),
            "detail": "host/path matched Confluence",
            "extra": {},
        }

    if host == "issues.apache.org" or path_l.startswith("/jira") or "/secure/" in path_l or "/browse/" in path_l:
        if host == "issues.apache.org" or path_l.startswith("/jira"):
            base = f"{origin}/jira"
        else:
            base = origin
        if host.endswith(".atlassian.net") and not path_l.startswith("/jira"):
            # cloud often serves REST at origin
            base = origin
        return {
            "kind": "jira",
            "url": raw,
            "host": host,
            "base": base.rstrip("/"),
            "detail": "host/path matched Jira",
            "extra": {},
        }

    # Known GitLab hosts / path looks like gitlab
    if (
        "gitlab" in host
        or host in ("salsa.debian.org",)
        or host.endswith(".gitlab.io")
    ):
        from gitlab_ingest import resolve_from_url

        try:
            resolved = resolve_from_url(raw)
        except ValueError as e:
            # instance root without group — still gitlab but needs group
            return {
                "kind": "gitlab",
                "url": raw,
                "host": host,
                "base": origin,
                "detail": f"GitLab host but path unresolved: {e}",
                "extra": {"instance": origin, "group": None, "error": str(e)},
            }
        return {
            "kind": "gitlab",
            "url": raw,
            "host": host,
            "base": resolved["instance"],
            "detail": f"GitLab → group={resolved['group']}",
            "extra": resolved,
        }

    # Atlassian cloud without wiki/jira path — prefer Jira for /browse, else ambiguous
    if host.endswith(".atlassian.net"):
        if "wiki" in path_l:
            return {
                "kind": "confluence",
                "url": raw,
                "host": host,
                "base": f"{origin}/wiki",
                "detail": "atlassian.net wiki path",
                "extra": {},
            }
        return {
            "kind": "jira",
            "url": raw,
            "host": host,
            "base": origin,
            "detail": "atlassian.net default → jira",
            "extra": {},
        }

    # ── Best-effort probes ─────────────────────────────────────────
    probes: list[tuple[str, str, str]] = [
        ("gitlab", f"{origin}/api/v4/version", "gitlab"),
        ("jira", f"{origin}/rest/api/2/serverInfo", "jira"),
        ("jira", f"{origin}/jira/rest/api/2/serverInfo", "jira"),
        ("confluence", f"{origin}/rest/api/space?limit=1", "confluence"),
        ("confluence", f"{origin}/confluence/rest/api/space?limit=1", "confluence"),
        ("confluence", f"{origin}/wiki/rest/api/space?limit=1", "confluence"),
    ]
    hits: list[dict[str, Any]] = []
    for kind, probe_url, _ in probes:
        code, body = _http_probe(probe_url)
        if code is None:
            continue
        if code == 200:
            if kind == "gitlab" and ("version" in body or "revision" in body or body.strip().startswith("{")):
                hits.append({"kind": kind, "probe": probe_url, "code": code})
            elif kind == "jira" and ("baseUrl" in body or "serverTitle" in body or "versionNumbers" in body or body.strip().startswith("{")) or kind == "confluence" and ("results" in body or "start" in body or body.strip().startswith("{")):
                hits.append({"kind": kind, "probe": probe_url, "code": code, "base_hint": probe_url.split("/rest/")[0]})
        elif code in (401, 403) and kind == "gitlab":
            # auth-walled GitLab still counts as GitLab
            hits.append({"kind": kind, "probe": probe_url, "code": code})

    if hits:
        # prefer first strong hit
        h = hits[0]
        kind = h["kind"]
        if kind == "gitlab":
            from gitlab_ingest import resolve_from_url

            try:
                resolved = resolve_from_url(raw)
                return {
                    "kind": "gitlab",
                    "url": raw,
                    "host": host,
                    "base": resolved["instance"],
                    "detail": f"probed GitLab API ({h.get('code')}) → group={resolved['group']}",
                    "extra": {**resolved, "probe": h.get("probe")},
                }
            except ValueError as e:
                return {
                    "kind": "gitlab",
                    "url": raw,
                    "host": host,
                    "base": origin,
                    "detail": f"probed GitLab but path unresolved: {e}",
                    "extra": {"instance": origin, "group": None, "error": str(e)},
                }
        base = h.get("base_hint") or origin
        return {
            "kind": kind,
            "url": raw,
            "host": host,
            "base": base.rstrip("/"),
            "detail": f"probed {kind} API ({h.get('code')})",
            "extra": {"probe": h.get("probe"), "all_hits": hits},
        }

    return {
        "kind": "unknown",
        "url": raw,
        "host": host,
        "base": origin,
        "detail": "no matching host rule and probes failed",
        "extra": {"probes_tried": [p[1] for p in probes]},
    }


def supported_message() -> str:
    lines = [
        "Supported ingestion targets:",
        "",
        "  GitLab:",
        "    hosts: gitlab.com, gitlab.gnome.org, salsa.debian.org, self-hosted GitLab",
        "    examples: https://gitlab.gnome.org/GNOME",
        "    presets: gnome | salsa | gitlab | freexian",
        "",
        "  Jira:",
        "    hosts: issues.apache.org, *.atlassian.net",
        "    examples: https://issues.apache.org/jira",
        "",
        "  Confluence:",
        "    hosts: cwiki.apache.org, *.atlassian.net/wiki",
        "    examples: https://cwiki.apache.org/confluence",
        "",
        "Usage:",
        "  ingest_url.py --url <URL> [--deep] [--max] [-v] [--min-interval 0.12]",
        "  ingest_url.py --preset gnome --max",
        "  ingest_url.py --list",
        "  ingest_url.py --url <URL> --resolve",
    ]
    return "\n".join(lines)


def _apply_max_limits(args: argparse.Namespace) -> None:
    if not args.max:
        return
    args.max_projects = max(args.max_projects, 80)
    args.max_issues = max(args.max_issues, 40)
    args.max_mrs = max(args.max_mrs, 25)
    args.max_notes = max(args.max_notes, 15)
    args.max_wiki = max(args.max_wiki, 40)
    args.max_tree = max(args.max_tree, 100)
    args.max_files = max(args.max_files, 12)
    args.max_subgroups = max(args.max_subgroups, 200)
    args.max_spaces = max(args.max_spaces, 20)
    args.max_pages = max(args.max_pages, 80)
    args.workers = max(args.workers, 2)
    # still polite
    args.min_interval = max(0.08, min(args.min_interval, 0.1))


def run_gitlab(resolved: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    from gitlab_ingest import GitLabClient, GitLabIngestor

    instance = resolved.get("instance") or resolved.get("base")
    group = resolved.get("group")
    if not instance or not group:
        return {
            "ok": False,
            "kind": "gitlab",
            "error": "GitLab URL needs a group/project path (e.g. https://gitlab.gnome.org/GNOME)",
            "resolved": resolved,
        }
    client = GitLabClient(instance, token=args.token, min_interval=args.min_interval)
    eng = GitLabIngestor(
        client,
        agent_id="ingest-url-gitlab",
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
    if args.verbose:
        print(
            f"gitlab deep={not args.shallow} instance={instance} group={group} "
            f"min_interval={args.min_interval}",
            file=sys.stderr,
        )
    result = eng.crawl_group_tree(group)
    result.setdefault("kind", "gitlab")
    result.setdefault("instance", instance)
    result.setdefault("group", group)
    return result


def run_jira(base: str, args: argparse.Namespace) -> dict[str, Any]:
    import crawl_public as cp

    # polite pacing for shared http_get
    orig_get = cp.http_get
    last = {"t": 0.0}

    def polite_get(url: str, headers: dict[str, str] | None = None, timeout: int = 45) -> Any:
        now = time.time()
        wait = args.min_interval - (now - last["t"])
        if wait > 0:
            time.sleep(wait)
        last["t"] = time.time()
        return orig_get(url, headers=headers, timeout=timeout)

    cp.http_get = polite_get  # type: ignore[assignment]
    try:
        if args.verbose:
            print(
                f"jira base={base} max_projects={args.max_projects} "
                f"max_issues={args.max_issues} min_interval={args.min_interval}",
                file=sys.stderr,
            )
        counts = cp.crawl_jira(
            base,
            args.max_projects,
            args.max_issues,
            None,
            "ingest-url-jira",
            args.run_id,
        )
        return {"ok": True, "kind": "jira", "base": base, "counts": counts}
    except Exception as e:
        return {"ok": False, "kind": "jira", "base": base, "error": str(e)}
    finally:
        cp.http_get = orig_get  # type: ignore[assignment]


def run_confluence(base: str, args: argparse.Namespace) -> dict[str, Any]:
    import crawl_public as cp

    orig_get = cp.http_get
    last = {"t": 0.0}

    def polite_get(url: str, headers: dict[str, str] | None = None, timeout: int = 45) -> Any:
        now = time.time()
        wait = args.min_interval - (now - last["t"])
        if wait > 0:
            time.sleep(wait)
        last["t"] = time.time()
        return orig_get(url, headers=headers, timeout=timeout)

    cp.http_get = polite_get  # type: ignore[assignment]
    try:
        if args.verbose:
            print(
                f"confluence base={base} max_spaces={args.max_spaces} "
                f"max_pages={args.max_pages} min_interval={args.min_interval}",
                file=sys.stderr,
            )
        counts = cp.crawl_confluence(
            base,
            args.max_spaces,
            args.max_pages,
            None,
            "ingest-url-confluence",
            args.run_id,
        )
        return {"ok": True, "kind": "confluence", "base": base, "counts": counts}
    except Exception as e:
        return {"ok": False, "kind": "confluence", "base": base, "error": str(e)}
    finally:
        cp.http_get = orig_get  # type: ignore[assignment]


def auto_boss_brain(verbose: bool = True) -> dict[str, Any] | None:
    """After successful ingest: export_graph + sync if distill_vault present."""
    try:
        import distill_vault as dv
    except Exception as e:
        if verbose:
            print(f"distill_vault not available (skip boss brain): {e}", file=sys.stderr)
        return None
    out: dict[str, Any] = {}
    try:
        out["export_graph"] = dv.export_graph()
        if verbose:
            print(
                f"boss brain: export_graph → {out['export_graph'].get('exported')} notes",
                file=sys.stderr,
            )
    except Exception as e:
        out["export_graph"] = {"ok": False, "error": str(e)}
        if verbose:
            print(f"boss brain: export_graph failed: {e}", file=sys.stderr)
    try:
        out["sync"] = dv.sync_to_codex()
        if verbose:
            print(f"boss brain: sync → {out['sync'].get('skill')}", file=sys.stderr)
    except Exception as e:
        out["sync"] = {"ok": False, "error": str(e)}
        if verbose:
            print(f"boss brain: sync failed: {e}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Unified URL ingest (GitLab / Jira / Confluence) → Private Brain"
    )
    ap.add_argument("--url", default=os.environ.get("PB_INGEST_URL"), help="Any supported URL")
    ap.add_argument(
        "--preset",
        choices=["gnome", "salsa", "gitlab", "freexian"],
        help="GitLab preset shortcut",
    )
    ap.add_argument("--token", default=None, help="GitLab PRIVATE-TOKEN (or GITLAB_TOKEN env)")
    ap.add_argument("--deep", action="store_true", default=True, help="Deep harvest (default on)")
    ap.add_argument("--shallow", action="store_true", help="Light harvest where applicable")
    ap.add_argument("--max", action="store_true", help="Raise capture limits (still polite)")
    ap.add_argument("--max-projects", type=int, default=20)
    ap.add_argument("--max-issues", type=int, default=20)
    ap.add_argument("--max-mrs", type=int, default=12)
    ap.add_argument("--max-notes", type=int, default=10)
    ap.add_argument("--max-wiki", type=int, default=15)
    ap.add_argument("--max-tree", type=int, default=40)
    ap.add_argument("--max-files", type=int, default=6)
    ap.add_argument("--max-subgroups", type=int, default=60)
    ap.add_argument("--max-spaces", type=int, default=8)
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument(
        "--min-interval",
        type=float,
        default=0.12,
        help="Seconds between API calls (polite default 0.12)",
    )
    ap.add_argument(
        "--run-id",
        default=os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"ingest-url-{int(time.time())}",
    )
    ap.add_argument("--json", action="store_true", help="Print result JSON (always prints JSON)")
    ap.add_argument("-v", "--verbose", action="store_true", default=True)
    ap.add_argument("--quiet", action="store_true", help="Less stderr")
    ap.add_argument("--list", action="store_true", help="List supported hosts / examples")
    ap.add_argument(
        "--resolve",
        action="store_true",
        help="Dry-run: detect kind + resolve targets, no crawl",
    )
    ap.add_argument(
        "--no-distill",
        action="store_true",
        help="Skip auto export_graph + sync after success",
    )
    args = ap.parse_args()

    if args.quiet:
        args.verbose = False
    # Machine-readable modes must not emit human chatter on either stream
    # (callers often use `cmd --json 2>&1 | jq` / json.load on the redirect).
    if args.json or args.resolve:
        args.verbose = False

    if args.list:
        print(json.dumps(SUPPORTED, indent=2))
        print(supported_message(), file=sys.stderr)
        return 0

    _apply_max_limits(args)

    # Preset → synthetic GitLab URL / resolved target
    detected: dict[str, Any] | None = None
    if args.preset:
        from gitlab_ingest import PRESETS

        p = PRESETS[args.preset]
        detected = {
            "kind": "gitlab",
            "url": f"{p['instance']}/{p['group']}",
            "host": urllib.parse.urlparse(p["instance"]).netloc,
            "base": p["instance"],
            "detail": f"preset={args.preset}: {p['note']}",
            "extra": {"instance": p["instance"], "group": p["group"], "preset": args.preset},
        }
        if args.verbose:
            print(f"preset={args.preset}: {p['note']}", file=sys.stderr)
    elif args.url:
        try:
            detected = detect_kind(args.url)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print(supported_message(), file=sys.stderr)
            return 2
    else:
        print(
            "Need --url <URL> or --preset gnome|salsa|gitlab|freexian (or --list)",
            file=sys.stderr,
        )
        print(supported_message(), file=sys.stderr)
        return 2

    assert detected is not None

    # Enterprise policy: public presets / public hosts blocked (same as beastMode).
    # Fail closed under PB_ENTERPRISE — never swallow policy errors.
    try:
        from enterprise import assert_ingest_allowed
    except Exception as e:
        if (os.environ.get("PB_ENTERPRISE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enterprise",
        }:
            print(
                f"ERROR: enterprise policy required under PB_ENTERPRISE but unavailable: {e}",
                file=sys.stderr,
            )
            return 2
    else:
        try:
            preset = (detected.get("extra") or {}).get("preset") or args.preset
            assert_ingest_allowed(
                url=detected.get("url") or detected.get("base"),
                preset=preset,
            )
        except PermissionError as e:
            try:
                from ingest_scenario import handle_blocked_ingest

                sc = handle_blocked_ingest(
                    blocked_url=str(detected.get("url") or detected.get("base") or ""),
                    reason=str(e),
                )
                print(f"ERROR: enterprise policy blocked ingest: {e}", file=sys.stderr)
                if sc.get("suggested_gitlab"):
                    print(
                        f"SELF-HEAL: use internal GitLab {sc['suggested_gitlab']} "
                        f"(beastMode -ingestion {sc['suggested_gitlab']})",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "SCENARIO: ask human for internal GitLab/Jira/Confluence URLs — synthesizer pending.",
                        file=sys.stderr,
                    )
                print(sc.get("inject") or "", file=sys.stderr)
                return int(sc.get("exit_code") or 2)
            except Exception as se:
                print(f"ERROR: enterprise policy blocked ingest: {e}", file=sys.stderr)
                print(f"ingest_scenario soft-fail: {se}", file=sys.stderr)
                return 2

    if args.verbose:
        print(
            f"detect: kind={detected['kind']} host={detected.get('host')} "
            f"base={detected.get('base')} — {detected.get('detail')}",
            file=sys.stderr,
        )

    if detected["kind"] == "unknown":
        print(
            f"ERROR: unsupported or undetectable host '{detected.get('host')}'",
            file=sys.stderr,
        )
        print(supported_message(), file=sys.stderr)
        print(json.dumps({"ok": False, "error": "unknown_host", "detected": detected}, indent=2))
        return 2

    if args.resolve:
        out = {"ok": True, "mode": "resolve", "detected": detected}
        print(json.dumps(out, indent=2, default=str))
        return 0

    ensure_tree()
    os.environ["PRIVATE_BRAIN_RUN_ID"] = args.run_id
    os.environ.setdefault("PRIVATE_BRAIN_AGENT_ID", "ingest-url")
    os.environ.setdefault("PRIVATE_BRAIN_ROLE", "ingest-url")
    if args.verbose:
        print(f"brain: {resolve_brain_root()}", file=sys.stderr)
        if args.max:
            print("MAX capture limits armed (still rate-limited/polite)", file=sys.stderr)

    kind = detected["kind"]
    if kind == "gitlab":
        extra = detected.get("extra") or {}
        # merge base/instance
        if "instance" not in extra:
            extra["instance"] = detected.get("base")
        result = run_gitlab(extra, args)
    elif kind == "jira":
        result = run_jira(detected["base"], args)
    elif kind == "confluence":
        result = run_confluence(detected["base"], args)
    else:
        result = {"ok": False, "error": f"unhandled kind {kind}"}

    ok = bool(result.get("ok", False))
    # some gitlab results use ok key; crawl counts without ok still success if no error
    if "error" not in result and kind in ("jira", "confluence") and "counts" in result:
        ok = True
        result["ok"] = True
    if kind == "gitlab" and result.get("ok") is None and "error" not in result:
        # crawl_group_tree always sets ok
        ok = bool(result.get("ok", True))

    if ok and not args.no_distill:
        result["boss_brain"] = auto_boss_brain(verbose=args.verbose)

    try:
        result["snapshot"] = build_snapshot().get("stats")
    except Exception:
        pass

    result["detected"] = {
        "kind": detected["kind"],
        "host": detected.get("host"),
        "base": detected.get("base"),
        "detail": detected.get("detail"),
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        raise
