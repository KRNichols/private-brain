#!/usr/bin/env python3
"""
Never-forgets second mind — plain-text vault you own forever.

Persistent identity for Private Brain (Codex sideload). No third-party product names.

  Vault                 →  private-brain/vault/   (plain markdown on disk)
  IDENTITY.md           →  vault/IDENTITY.md      (synced every session)
  Project folders       →  vault/projects/<name>/{Inputs,Process,Outputs,Feedback}
  Project brief         →  vault/projects/<name>/PROJECT.md
  Skills                →  vault/projects/<name>/skills/  + vault/skills/
  Autopilot             →  second_mind.py organize

End users never type Python:
  beastMode --never-forget-init
  beastMode --project youtube-channel
  beastMode --organize
  beastMode --sync-memory
  beastMode --interview
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from brain_lib import (
    STATE_DIR,
    ensure_tree,
    read_json,
    resolve_brain_root,
    utc_now,
    write_json,
)

try:
    from distill_vault import init_vault, sync_to_codex, vault_root
except Exception:  # pragma: no cover
    init_vault = None  # type: ignore
    vault_root = None  # type: ignore
    sync_to_codex = None  # type: ignore


ACTIVE_PROJECT_FILE = "active_project.json"
IDENTITY_NAME = "IDENTITY.md"
PROJECT_MD_NAME = "PROJECT.md"
# Legacy filenames — migrated automatically; never used as product branding
_LEGACY_IDENTITY = "CLAUDE.md"

INTERVIEW_PROMPT = """You are setting up my second brain (Private Brain vault).

Interview me ONE question at a time. Wait for each answer before the next.

Cover, in order:
1. Who I am and what I do
2. Goals this year (max 3)
3. How I want you to communicate with me (tone, length, do/don't)
4. Strengths and weaknesses
5. Current projects and their single goals
6. Tools I use daily (Codex, editors, terminals, etc.)
7. Anything I never want you to re-ask

When finished, write everything into:
  vault/IDENTITY.md
organized with clear headers (Who I Am, Goals, Communication, Strengths, Weaknesses,
Projects, Tools, Never Re-Ask). That file is permanent session context — I never
explain myself from zero again.

Also call (or ask me to run): beastMode --sync-memory
so Codex AGENTS.md + skills/private-brain pick it up automatically.
"""


def _vault() -> Path:
    if vault_root is not None:
        return vault_root()
    return resolve_brain_root() / "vault"


def projects_dir() -> Path:
    return _vault() / "projects"


def global_skills_dir() -> Path:
    return _vault() / "skills"


def identity_path() -> Path:
    """Canonical permanent identity file (vault/IDENTITY.md). Migrates legacy names."""
    v = _vault()
    modern = v / IDENTITY_NAME
    legacy = v / _LEGACY_IDENTITY
    if legacy.exists() and not modern.exists():
        try:
            legacy.rename(modern)
        except OSError:
            try:
                modern.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                legacy.unlink(missing_ok=True)  # type: ignore[arg-type]
            except OSError:
                pass
    return modern


def project_md_path(project_root: Path) -> Path:
    """Project brief: PROJECT.md (migrates legacy CLAUDE.md if present)."""
    modern = project_root / PROJECT_MD_NAME
    legacy = project_root / _LEGACY_IDENTITY
    if legacy.exists() and not modern.exists():
        try:
            legacy.rename(modern)
        except OSError:
            try:
                modern.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                legacy.unlink(missing_ok=True)  # type: ignore[arg-type]
            except OSError:
                pass
    return modern


def ensure_second_mind() -> dict[str, Any]:
    """Create vault + identity skeleton + folders (idempotent)."""
    ensure_tree()
    if init_vault is not None:
        init_vault()
    v = _vault()
    for d in (
        projects_dir(),
        global_skills_dir(),
        v / "distill",
        v / "conventions",
        v / "graph",
        v / "tools",
        v / "Inbox",
    ):
        d.mkdir(parents=True, exist_ok=True)

    idp = identity_path()
    if not idp.exists():
        idp.write_text(
            f"""# IDENTITY.md — permanent identity (never start from zero)

> Owned plain text under `{v}`. Synced into Codex skills + AGENTS.md
> via `beastMode --sync-memory`. Edit freely — this is the second mind.

Generated skeleton: {utc_now()}

## Who I Am

_TODO: run `beastMode --interview` and answer one question at a time, or paste your brief here._

## Goals This Year

1. …
2. …
3. …

## How To Communicate With Me

- Tone:
- Length:
- Always:
- Never:

## Strengths

-

## Weaknesses

-

## Current Projects

| Project | Single goal | Role for the agent |
|---------|-------------|--------------------|
| | | |

## Tools I Use

- Codex / beastMode (Private Brain sideload)
- …

## Never Re-Ask

- Stack and conventions live in `vault/conventions/`
- Graph evidence arrives via concert hooks — cite `node_id` (T#)
- Entry is `beastMode` / SETUP / UNINSTALL only — never ask me to run Python

## Links

- Active project pointer: `.brain/state/active_project.json`
- Distill notes: `vault/distill/`
- Graph export: `vault/graph/`
""",
            encoding="utf-8",
        )

    interview = v / "INTERVIEW.md"
    if not interview.exists() or "CLAUDE.md" in interview.read_text(encoding="utf-8", errors="ignore"):
        interview.write_text(
            "# Second-mind interview\n\n"
            "Paste the following into Codex and answer one question at a time.\n\n"
            "---\n\n"
            + INTERVIEW_PROMPT
            + "\n",
            encoding="utf-8",
        )

    readme = v / "NEVER_FORGET.md"
    body = """# Never forgets — how this maps

| Concept | Private Brain |
|---|---|
| Second brain vault | `vault/` plain markdown on disk |
| Permanent identity | `vault/IDENTITY.md` → synced into skills / AGENTS.md |
| Project workspace | `vault/projects/<name>/` |
| Project brief | `vault/projects/<name>/PROJECT.md` |
| Inputs / Process / Outputs / Feedback | same four folders under each project |
| Skills | `vault/skills/` + per-project `skills/` |
| Daily organize | `beastMode --organize` (cron/launchd optional) |

## Commands (no Python)

```text
beastMode --never-forget-init
beastMode --interview
beastMode --project my-thing
beastMode --skill "name" --skill-body "steps..."
beastMode --organize
beastMode --sync-memory
```

You own the brain. The model is replaceable. Codex is the product CLI; Private Brain is the sideload.
"""
    if not readme.exists() or "CLAUDE" in readme.read_text(encoding="utf-8", errors="ignore"):
        readme.write_text(body, encoding="utf-8")

    # Neutral tool slice (replace any legacy third-party-named files)
    tools = v / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    other = tools / "other-agents.md"
    if not other.exists() or "Claude" in other.read_text(encoding="utf-8", errors="ignore"):
        other.write_text(
            """# Other agent tools

Conventions in this vault are the source of truth.
When sharing context with other coding agents, point them at `vault/IDENTITY.md`
and `beastMode --sync-memory` outputs under Codex skills — not a third-party brand name.
""",
            encoding="utf-8",
        )
    legacy_tool = tools / "claude.md"
    if legacy_tool.exists():
        try:
            legacy_tool.unlink()
        except OSError:
            pass

    return {
        "ok": True,
        "vault": str(v),
        "identity": str(idp),
        "projects": str(projects_dir()),
        "skills": str(global_skills_dir()),
    }


def create_project(
    name: str,
    *,
    goal: str = "",
    role: str = "",
    activate: bool = True,
) -> dict[str, Any]:
    """Create project with Inputs/Process/Outputs/Feedback + PROJECT.md."""
    ensure_second_mind()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-_.") or "project"
    root = projects_dir() / safe
    for sub in ("Inputs", "Process", "Outputs", "Feedback", "skills"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    seeds = {
        "Inputs/README.md": (
            f"# Inputs — {safe}\n\nDrop raw ideas, links, dumps here. "
            f"`beastMode --organize` files them into Process.\n"
        ),
        "Process/README.md": f"# Process — {safe}\n\nWork-in-progress. Agent drafts live here.\n",
        "Outputs/README.md": f"# Outputs — {safe}\n\nFinished artifacts that shipped.\n",
        "Feedback/README.md": f"# Feedback — {safe}\n\nResults, metrics, postmortems.\n",
    }
    for rel, body in seeds.items():
        p = root / rel
        if not p.exists():
            p.write_text(body, encoding="utf-8")

    proj_md = project_md_path(root)
    if not proj_md.exists():
        goal_s = goal.strip() or f"Advance {safe} with clear, shippable outputs."
        role_s = role.strip() or (
            "Stay inside this project folder. Prefer Inputs → Process → Outputs. "
            "Record outcomes in Feedback. Do not re-ask global identity (see vault/IDENTITY.md)."
        )
        proj_md.write_text(
            f"""# Project: {safe}

## Single goal

{goal_s}

## Agent role

{role_s}

## Folders

| Folder | Purpose |
|--------|---------|
| Inputs | Raw ideas and material |
| Process | Active work |
| Outputs | Finished work |
| Feedback | Results and learnings |
| skills/ | Reusable workflows for this project |

## Rules

- Work one project at a time when this is active.
- Cite Private Brain graph nodes when relevant.
- After meaningful work: append Feedback + `beastMode --note "..."`.
""",
            encoding="utf-8",
        )

    out: dict[str, Any] = {
        "ok": True,
        "project": safe,
        "path": str(root),
        "created": True,
    }
    if activate:
        out["active"] = set_active_project(safe)
    return out


def set_active_project(name: str) -> dict[str, Any]:
    ensure_second_mind()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-_.")
    root = projects_dir() / safe
    if not root.exists():
        return {"ok": False, "error": f"project not found: {safe}"}
    rec = {
        "name": safe,
        "path": str(root),
        "activated_at": utc_now(),
    }
    write_json(STATE_DIR / ACTIVE_PROJECT_FILE, rec)
    os.environ["PRIVATE_BRAIN_PROJECT"] = str(root)
    os.environ["PRIVATE_BRAIN_ACTIVE_PROJECT"] = safe
    return {"ok": True, **rec}


def get_active_project() -> dict[str, Any] | None:
    p = STATE_DIR / ACTIVE_PROJECT_FILE
    if not p.exists():
        return None
    try:
        return read_json(p)
    except Exception:
        return None


def list_projects() -> list[dict[str, Any]]:
    ensure_second_mind()
    active = (get_active_project() or {}).get("name")
    out = []
    for d in sorted(projects_dir().iterdir()) if projects_dir().exists() else []:
        if not d.is_dir():
            continue
        out.append(
            {
                "name": d.name,
                "path": str(d),
                "active": d.name == active,
                "has_project_md": project_md_path(d).exists(),
            }
        )
    return out


def save_skill(
    name: str,
    body: str,
    *,
    project: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    ensure_second_mind()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-_.") or "skill"
    if project:
        root = projects_dir() / re.sub(r"[^A-Za-z0-9._-]+", "-", project.strip())
        root.mkdir(parents=True, exist_ok=True)
        dest_dir = root / "skills"
    else:
        dest_dir = global_skills_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{safe}.md"
    desc = description.strip() or f"Reusable skill: {safe}"
    if not body.strip().startswith("#"):
        content = f"# Skill: {safe}\n\n> {desc}\n\n## When to use\n\n{desc}\n\n## Steps\n\n{body.strip()}\n"
    else:
        content = body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path), "name": safe, "project": project}


def _read_cap(path: Path, n: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:n]
    except OSError:
        return ""


def identity_brief(max_chars: int = 3500) -> str:
    ensure_second_mind()
    parts: list[str] = []
    idp = identity_path()
    if idp.exists():
        parts.append("### Permanent identity (vault/IDENTITY.md)\n\n" + _read_cap(idp, max_chars // 2))
    ap = get_active_project()
    if ap and ap.get("path"):
        pc = project_md_path(Path(ap["path"]))
        if pc.exists():
            parts.append(
                f"### Active project: {ap.get('name')}\n\n" + _read_cap(pc, max_chars // 3)
            )
        parts.append(f"Project path: `{ap.get('path')}` — work here (Inputs→Process→Outputs).")
    distill = _vault() / "distill"
    days = sorted(distill.glob("*.md"), reverse=True)[:1] if distill.exists() else []
    for d in days:
        parts.append(f"### Latest distill ({d.name})\n\n" + _read_cap(d, 800))
    blob = "\n\n".join(parts).strip()
    if len(blob) > max_chars:
        blob = blob[: max_chars - 20] + "\n…(truncated)"
    return blob or "_Second mind empty — run beastMode --never-forget-init + --interview._"


def organize(*, stale_days: int = 14) -> dict[str, Any]:
    ensure_second_mind()
    moved: list[str] = []
    flagged: list[str] = []
    now = datetime.now(timezone.utc)
    stale_cut = now - timedelta(days=stale_days)

    def _file_inputs(inputs: Path, process: Path, label: str) -> None:
        if not inputs.exists():
            return
        process.mkdir(parents=True, exist_ok=True)
        for p in sorted(inputs.iterdir()):
            if p.name.startswith(".") or p.name == "README.md":
                continue
            if p.is_file():
                dest = process / p.name
                if dest.exists():
                    dest = process / f"{p.stem}-{now.strftime('%H%M%S')}{p.suffix}"
                try:
                    shutil.move(str(p), str(dest))
                    moved.append(f"{label}: {p.name} → Process/")
                except OSError as e:
                    flagged.append(f"move-fail {p}: {e}")

    _file_inputs(_vault() / "Inbox", _vault() / "Inbox" / "_processed", "vault")
    vault_process = _vault() / "Process"
    if (_vault() / "Inbox").exists():
        for p in list((_vault() / "Inbox").iterdir()):
            if p.is_file() and p.name != "README.md":
                vault_process.mkdir(parents=True, exist_ok=True)
                dest = vault_process / p.name
                try:
                    shutil.move(str(p), str(dest))
                    moved.append(f"vault-inbox: {p.name}")
                except OSError:
                    pass

    for proj in list_projects():
        root = Path(proj["path"])
        _file_inputs(root / "Inputs", root / "Process", proj["name"])
        proc = root / "Process"
        if proc.exists():
            for p in proc.rglob("*"):
                if not p.is_file() or p.name == "README.md":
                    continue
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
                if mtime < stale_cut:
                    flagged.append(
                        f"stale {proj['name']}/Process/{p.relative_to(proc)} "
                        f"({(now - mtime).days}d)"
                    )

    summary_lines = [
        f"organize @ {utc_now()}",
        f"moved={len(moved)} stale_flags={len(flagged)} projects={len(list_projects())}",
    ]
    if moved:
        summary_lines.append("moved: " + "; ".join(moved[:5]))
    if flagged:
        summary_lines.append("stale: " + "; ".join(flagged[:5]))
    summary = "\n".join(summary_lines)

    ap = get_active_project()
    if ap and ap.get("path"):
        fb = Path(ap["path"]) / "Feedback"
        fb.mkdir(parents=True, exist_ok=True)
        log_path = fb / f"organize-{now.strftime('%Y%m%d')}.md"
    else:
        log_path = _vault() / "distill" / f"{now.strftime('%Y-%m-%d')}.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## organize {now.strftime('%H:%M:%SZ')}\n\n{summary}\n")

    report = {
        "ok": True,
        "moved": moved,
        "stale": flagged,
        "summary": summary,
        "log": str(log_path),
        "three_line": "\n".join(summary_lines[:3]),
    }
    write_json(STATE_DIR / "last_organize.json", report)
    return report


def write_identity_from_text(text: str) -> dict[str, Any]:
    """Replace or write vault/IDENTITY.md from interview result."""
    ensure_second_mind()
    path = identity_path()
    body = text.strip()
    if not body.startswith("#"):
        body = "# IDENTITY.md — permanent identity\n\n" + body
    # strip accidental third-party brand titles if pasted from old templates
    body = re.sub(r"(?im)^#\s*CLAUDE\.md\b", "# IDENTITY.md", body)
    if "Generated" not in body[:200] and "Updated" not in body[-80:]:
        body = body.rstrip() + f"\n\n_Updated {utc_now()}_\n"
    path.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": path.stat().st_size}


def boot_context(max_chars: int = 4000) -> str:
    try:
        ensure_second_mind()
    except Exception:
        pass
    brief = identity_brief(max_chars=max_chars)
    return (
        "NEVER-FORGET SECOND MIND (plain-text vault — you already know the user):\n"
        f"{brief}\n"
        "Rules: do not re-interview for facts already in vault/IDENTITY.md. "
        "If active project is set, prefer that folder. "
        "After session learnings: suggest beastMode --note + --sync-memory."
    )


def status() -> dict[str, Any]:
    ensure_second_mind()
    ap = get_active_project()
    idp = identity_path()
    id_bytes = idp.stat().st_size if idp.exists() else 0
    todo = "TODO" in _read_cap(idp, 500) if idp.exists() else True
    return {
        "ok": True,
        "vault": str(_vault()),
        "identity": str(idp),
        "identity_bytes": id_bytes,
        "identity_needs_interview": todo,
        "projects": list_projects(),
        "active_project": ap,
        "global_skills": [p.name for p in global_skills_dir().glob("*.md")],
        "interview_prompt_path": str(_vault() / "INTERVIEW.md"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Never-forgets second mind (Private Brain)")
    ap.add_argument(
        "cmd",
        choices=[
            "init",
            "status",
            "interview",
            "project",
            "activate",
            "list-projects",
            "skill",
            "organize",
            "identity",
            "brief",
            "sync",
        ],
    )
    ap.add_argument("--name", default="")
    ap.add_argument("--goal", default="")
    ap.add_argument("--role", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--body", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--project", default="")
    ap.add_argument("--stale-days", type=int, default=14)
    ap.add_argument("--json", action="store_true", default=True)
    ap.add_argument("--no-activate", action="store_true")
    args = ap.parse_args()

    out: dict[str, Any]
    if args.cmd == "init":
        out = ensure_second_mind()
    elif args.cmd == "status":
        out = status()
    elif args.cmd == "interview":
        out = {
            "ok": True,
            "prompt": INTERVIEW_PROMPT,
            "path": str(_vault() / "INTERVIEW.md"),
            "hint": "Paste prompt into Codex; when done save to vault/IDENTITY.md then --sync-memory",
        }
        ensure_second_mind()
    elif args.cmd == "project":
        if not args.name.strip():
            print(json.dumps({"ok": False, "error": "--name required"}))
            return 2
        out = create_project(
            args.name,
            goal=args.goal,
            role=args.role,
            activate=not args.no_activate,
        )
    elif args.cmd == "activate":
        if not args.name.strip():
            print(json.dumps({"ok": False, "error": "--name required"}))
            return 2
        out = set_active_project(args.name)
    elif args.cmd == "list-projects":
        out = {"ok": True, "projects": list_projects()}
    elif args.cmd == "skill":
        if not args.name.strip() or not (args.body or args.text).strip():
            print(json.dumps({"ok": False, "error": "--name and --body/--text required"}))
            return 2
        out = save_skill(
            args.name,
            args.body or args.text,
            project=args.project or None,
            description=args.description,
        )
    elif args.cmd == "organize":
        out = organize(stale_days=args.stale_days)
    elif args.cmd == "identity":
        if not args.text.strip():
            print(json.dumps({"ok": False, "error": "--text required (full IDENTITY.md body)"}))
            return 2
        out = write_identity_from_text(args.text)
    elif args.cmd == "brief":
        out = {"ok": True, "brief": identity_brief()}
    elif args.cmd == "sync":
        ensure_second_mind()
        if sync_to_codex is not None:
            out = sync_to_codex()
        else:
            out = {"ok": False, "error": "distill_vault unavailable"}
    else:
        out = {"ok": False, "error": "unknown"}

    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
