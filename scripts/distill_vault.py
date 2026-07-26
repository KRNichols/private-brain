#!/usr/bin/env python3
"""
Distill vault — plain markdown "boss brain" that tools read.

Pattern (Obsidian-style multi-tool memory):
  One folder of dated distill notes + conventions.
  Sync into Codex AGENTS.md + skills/ so every session already knows you.
  Optional: export high-worth graph nodes into markdown (graph → notes).

End users: beastMode --sync-memory  (never type python)

CLI (maintainer / beastMode internal):
  python distill_vault.py init
  python distill_vault.py note "what I learned today"
  python distill_vault.py export-graph
  python distill_vault.py sync
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain_lib import (
    STATE_DIR,
    ensure_tree,
    load_all_nodes,
    resolve_brain_root,
    utc_now,
    write_json,
)

MARKER_BEGIN = "<!-- PRIVATE_BRAIN_DISTILL_BEGIN -->"
MARKER_END = "<!-- PRIVATE_BRAIN_DISTILL_END -->"


def vault_root() -> Path:
    return resolve_brain_root() / "vault"


def distill_dir() -> Path:
    return vault_root() / "distill"


def conventions_dir() -> Path:
    return vault_root() / "conventions"


def graph_export_dir() -> Path:
    return vault_root() / "graph"


def tools_dir() -> Path:
    return vault_root() / "tools"


def init_vault() -> dict[str, Any]:
    ensure_tree()
    for d in (distill_dir(), conventions_dir(), graph_export_dir(), tools_dir()):
        d.mkdir(parents=True, exist_ok=True)

    readme = vault_root() / "README.md"
    if not readme.exists():
        readme.write_text(
            """# Distill vault — your boss in markdown

Plain files. No SaaS. One source of truth.

## Folders

| Path | Purpose |
|------|---------|
| `distill/YYYY-MM-DD.md` | Daily: what you tried, what worked, what you'd tell past-you |
| `conventions/` | Stack, coding style, always-true rules |
| `graph/` | Auto-export of high-worth RAG-DAG nodes (read-only generated) |
| `tools/` | Per-tool slices (codex.md, other-agents.md, …) |

## Daily ritual

```text
beastMode --note "Tried X. Worked because Y. Tell past-me: Z"
beastMode --sync-memory
```

Or just write markdown under `distill/` then `beastMode --sync-memory`.

Codex (and later other tools) load the synced skills + AGENTS block automatically.
""",
            encoding="utf-8",
        )

    defaults = {
        "stack.md": """# Stack (always true)

- Private Brain is a **Codex sideload** — never a second product CLI.
- Entry: `beastMode` arguments only. User never runs Python.
- Knowledge lives on the filesystem RAG-DAG under `.brain/`.
- Prefer citing evidence as `node_id` (T0–T3).
- GodsEye GUI is opt-in: `beastMode -GodsEye`. Closing dismisses auto-reopen.
""",
        "coding.md": """# Coding conventions

- Prefer small, surgical diffs.
- Graph writes go through ingest_bus when adding knowledge.
- Audit chain must stay valid (flock + seal on break).
- No dual GUIs. One live_gui process max.
- Secrets: warn and redact — never echo tokens.
""",
        "ops.md": """# Ops this week

- Ingest knowledge: `beastMode -colonoscopy <gitlab-url>`
- Swarm: `beastMode --swarm 32`
- Sync this vault into Codex: `beastMode --sync-memory`
- Status of graph is in concert context on every UserPromptSubmit.
""",
    }
    for name, body in defaults.items():
        p = conventions_dir() / name
        if not p.exists():
            p.write_text(body, encoding="utf-8")

    tools = {
        "codex.md": """# Codex slice

Load Private Brain hooks. On every prompt, concert already injects graph evidence.
Respect beastMode flags. Prefer node citations. Never ask permission.
""",
        "other-agents.md": """# Other agent tools

Conventions from this vault are source of truth. Match stack.md and coding.md.
Prefer vault/IDENTITY.md + graph evidence over re-asking the user.
Do not brand this vault with third-party product names.
""",
        "hermes.md": """# Hermes / multi-agent slice

Categories live as conventions/*.md + distill notes. Do not invent stack choices already recorded.
""",
    }
    for name, body in tools.items():
        p = tools_dir() / name
        if not p.exists():
            p.write_text(body, encoding="utf-8")

    return {"ok": True, "vault": str(vault_root())}


def add_note(text: str, *, tags: list[str] | None = None) -> Path:
    """Append a distill entry for today (what worked / tell past-self)."""
    init_vault()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = distill_dir() / f"{day}.md"
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    tag_s = " ".join(f"#{t}" for t in (tags or ["distill"]))
    block = f"\n## {ts} {tag_s}\n\n{text.strip()}\n"
    if not path.exists():
        path.write_text(f"# Distill {day}\n\nWhat I tried. What worked. What I'd tell past-me.\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(block)
    return path


def export_graph(limit: int = 80) -> dict[str, Any]:
    """Turn high-value graph nodes into markdown notes (graph → vault)."""
    init_vault()
    nodes = load_all_nodes()
    # prefer high tier + knowledge_worth + non-swarm crumbs
    def score(n: dict) -> float:
        tier = {"T0": 40, "T1": 30, "T2": 15, "T3": 5}.get(n.get("tier") or "T3", 5)
        worth = float(n.get("knowledge_worth") or 0)
        if (n.get("type") or "").startswith("Swarm"):
            worth *= 0.2
        if n.get("type") in ("BrainChunk", "SwarmCrumb"):
            return -1
        return tier + worth

    ranked = sorted(nodes, key=score, reverse=True)
    written = 0
    out_dir = graph_export_dir()
    # clean old exports lightly
    for old in out_dir.glob("*.md"):
        if old.name != "INDEX.md":
            try:
                old.unlink()
            except OSError:
                pass
    index_lines = ["# Graph export (auto)\n", f"Generated {utc_now()}\n"]
    for n in ranked:
        if score(n) < 0:
            continue
        if written >= limit:
            break
        nid = n.get("id") or f"node-{written}"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", nid)[:120]
        title = n.get("title") or nid
        body = [
            f"# {title}",
            "",
            f"- id: `{nid}`",
            f"- type: {n.get('type')}",
            f"- source: {n.get('source')}",
            f"- tier: {n.get('tier')}",
            f"- worth: {n.get('knowledge_worth')}",
            f"- tags: {', '.join(n.get('tags') or [])}",
            "",
            "## Why it matters",
            "",
            f"Exported from Private Brain RAG-DAG for multi-tool memory. Cite as `{nid}` ({n.get('tier')}).",
            "",
        ]
        # attach content snippet if present
        cpath = n.get("content_path")
        if cpath:
            fp = resolve_brain_root() / ".brain" / cpath
            if fp.exists():
                try:
                    snippet = fp.read_text(encoding="utf-8", errors="ignore")[:3000]
                    body += ["## Content", "", snippet, ""]
                except OSError:
                    pass
        (out_dir / f"{safe}.md").write_text("\n".join(body), encoding="utf-8")
        index_lines.append(f"- [{title}]({safe}.md) · `{nid}` · {n.get('tier')}")
        written += 1
    (out_dir / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return {"ok": True, "exported": written, "path": str(out_dir)}


def _read_md_tree(root: Path, limit_files: int = 40, max_chars: int = 12000) -> str:
    parts: list[str] = []
    n = 0
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("."):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = p.relative_to(root)
        parts.append(f"### {rel}\n\n{text.strip()}\n")
        n += 1
        if n >= limit_files:
            break
    blob = "\n".join(parts)
    return blob[:max_chars]


def build_skill_md() -> str:
    """Single SKILL.md for Codex skills/private-brain/"""
    init_vault()
    conv = _read_md_tree(conventions_dir(), limit_files=20, max_chars=8000)
    # last 7 distill days
    days = sorted(distill_dir().glob("*.md"), reverse=True)[:7]
    distill_bits = []
    for p in days:
        try:
            distill_bits.append(p.read_text(encoding="utf-8", errors="ignore")[:2000])
        except OSError:
            pass
    tools = _read_md_tree(tools_dir(), limit_files=10, max_chars=4000)
    graph_idx = graph_export_dir() / "INDEX.md"
    graph_head = ""
    if graph_idx.exists():
        graph_head = graph_idx.read_text(encoding="utf-8", errors="ignore")[:3000]
    nl = "\n"
    distill_block = nl.join(distill_bits) if distill_bits else (
        "_No distill notes yet. User can beastMode --note \"...\"._"
    )
    graph_block = graph_head or "_Run export-graph via --sync-memory._"

    # Never-forget identity + active project (compact)
    identity_block = ""
    try:
        from second_mind import (
            get_active_project,
            global_skills_dir,
            identity_path,
            project_md_path,
            projects_dir,
        )

        idp = identity_path()
        if idp.exists():
            identity_block = idp.read_text(encoding="utf-8", errors="ignore")[:4500]
        project_block = ""
        ap = get_active_project()
        if ap and ap.get("path"):
            pc = project_md_path(Path(ap["path"]))
            if pc.exists():
                project_block = (
                    f"**Active project: {ap.get('name')}** (`{ap.get('path')}`)\n\n"
                    + pc.read_text(encoding="utf-8", errors="ignore")[:2500]
                )
        skills_bits = []
        for sk in list(global_skills_dir().glob("*.md"))[:8]:
            skills_bits.append(f"- `{sk.name}`")
        if projects_dir().exists():
            for pd in sorted(projects_dir().iterdir())[:12]:
                if pd.is_dir():
                    skills_bits.append(f"- project `{pd.name}/`")
        skills_index = nl.join(skills_bits) if skills_bits else "_No skills yet._"
    except Exception:
        idp = vault_root() / "IDENTITY.md"
        if idp.exists():
            try:
                identity_block = idp.read_text(encoding="utf-8", errors="ignore")[:4500]
            except OSError:
                pass
        project_block = ""
        skills_index = "_second_mind not loaded_"

    identity_section = identity_block or (
        "_No vault/IDENTITY.md yet. Run `beastMode --never-forget-init` then `--interview`._"
    )
    project_section = project_block or "_No active project. `beastMode --project <name>`._"

    # Codex skills require YAML frontmatter delimited by ---
    return f"""---
name: private-brain
description: Persistent boss-brain memory (vault + RAG-DAG). Identity, projects, distill, graph.
---

# Private Brain · Distilled memory (never start from zero)

You are operating with a **persistent second mind** (plain markdown vault + RAG-DAG).
Do not re-ask for identity, stack, or conventions already listed here.
Cite graph nodes as `node_id` (T#). Prefer the active project folder when set.

## How the user runs you

- Sideload only: `beastMode` arguments — never require the user to run Python.
- Never-forget: `beastMode --never-forget-init` · `--interview` · `--project NAME` · `--organize`
- Ingest: `beastMode -colonoscopy <gitlab-url>` or `-ingestion <url>`.
- Pipeline: `beastMode --pipeline` (LOOP→GRAPH→HARNESS offline demo) · `--pipeline brain`
- GUI: `beastMode -GodsEye` (optional).
- Swarm: `beastMode --swarm 32`.
- Refresh this skill: `beastMode --sync-memory`.

## Permanent identity (vault/IDENTITY.md)

{identity_section}

## Active project

{project_section}

## Skills index

{skills_index}

## Conventions

{conv}

## Recent distill (what worked / tell past-self)

{distill_block}

## Tool slices

{tools}

## Graph export index (high-worth knowledge)

{graph_block}
"""


def _upsert_marker_block(path: Path, block: str) -> None:
    """Insert or replace MARKER_BEGIN…MARKER_END in a markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = block if block.endswith("\n") else block + "\n"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if MARKER_BEGIN in text:
            text = re.sub(
                re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END),
                body.strip(),
                text,
                flags=re.DOTALL,
            )
        else:
            text = text.rstrip() + "\n" + body
        path.write_text(text, encoding="utf-8")
    else:
        path.write_text(body.lstrip(), encoding="utf-8")


def _distill_pointer_block() -> str:
    """Short pointer for Codex AGENTS.md (and optional project IDENTITY overlays)."""
    active = ""
    try:
        from second_mind import get_active_project, identity_path

        ap = get_active_project()
        if ap and ap.get("name"):
            active = (
                f"Active project: **{ap.get('name')}** at `{ap.get('path')}` "
                f"(Inputs→Process→Outputs). Work there when relevant.\n"
            )
        idp = identity_path()
    except Exception:
        idp = vault_root() / "IDENTITY.md"
    id_hint = ""
    if idp.exists():
        id_hint = f"Permanent identity: `{idp}` — never re-interview from zero.\n"
    return (
        f"\n{MARKER_BEGIN}\n"
        f"# Private Brain distill (auto-synced {utc_now()})\n\n"
        f"Read skill: `skills/private-brain/SKILL.md` and vault at "
        f"`{vault_root()}`.\n"
        f"{id_hint}"
        f"{active}"
        f"Do not re-prompt the user for conventions or identity already in that skill.\n"
        f"On knowledge questions, trust concert hooks + distilled vault.\n"
        f"Entry for humans: `beastMode` / `SETUP` / `UNINSTALL` only — never run Python.\n"
        f"{MARKER_END}\n"
    )


def sync_to_codex() -> dict[str, Any]:
    """Push vault into Codex skills + AGENTS.md (sideload memory only — no third-party branding)."""
    init_vault()
    export_graph()
    skill_body = build_skill_md()
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser()
    skills = codex / "skills" / "private-brain"
    skills.mkdir(parents=True, exist_ok=True)
    skill_path = skills / "SKILL.md"
    skill_path.write_text(skill_body, encoding="utf-8")

    block = _distill_pointer_block()

    # Codex AGENTS overlay
    agents = codex / "AGENTS.md"
    _upsert_marker_block(agents, block)

    # Optional: project-local IDENTITY.md when PRIVATE_BRAIN_PROJECT is set
    extra_paths: list[str] = []
    proj_env = os.environ.get("PRIVATE_BRAIN_PROJECT")
    if proj_env:
        for name in ("IDENTITY.md", "PROJECT.md"):
            p = Path(proj_env).expanduser() / name
            try:
                if p.parent.exists():
                    _upsert_marker_block(p, block)
                    extra_paths.append(str(p))
            except OSError:
                pass

    # copy conventions into skills for tools that read folders
    conv_dst = skills / "conventions"
    if conv_dst.exists():
        shutil.rmtree(conv_dst)
    shutil.copytree(conventions_dir(), conv_dst)

    report = {
        "ok": True,
        "skill": str(skill_path),
        "agents": str(agents),
        "identity": str(vault_root() / "IDENTITY.md"),
        "extra_overlays": extra_paths,
        "vault": str(vault_root()),
        "synced_at": utc_now(),
        "bytes": skill_path.stat().st_size,
    }
    write_json(STATE_DIR / "last_distill_sync.json", report)
    return report


def status() -> dict[str, Any]:
    init_vault()
    return {
        "vault": str(vault_root()),
        "distill_days": len(list(distill_dir().glob("*.md"))),
        "conventions": [p.name for p in conventions_dir().glob("*.md")],
        "graph_exports": len(list(graph_export_dir().glob("*.md"))),
        "last_sync": str(STATE_DIR / "last_distill_sync.json"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Distill vault — multi-tool memory")
    ap.add_argument("cmd", choices=["init", "note", "export-graph", "sync", "status"])
    ap.add_argument("--text", default="")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "init":
        out = init_vault()
    elif args.cmd == "note":
        if not args.text.strip():
            print("note requires --text", flush=True)
            return 2
        p = add_note(args.text)
        out = {"ok": True, "path": str(p)}
    elif args.cmd == "export-graph":
        out = export_graph(limit=args.limit)
    elif args.cmd == "sync":
        out = sync_to_codex()
    else:
        out = status()

    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
