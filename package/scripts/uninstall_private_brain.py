#!/usr/bin/env python3
"""
Private Brain uninstaller — reverse the Codex sideload.

Removes wiring from CODEX_HOME while leaving vanilla Codex intact.

What it removes:
  - ~/.codex/private-brain/          (engine; .brain data archived by default)
  - ~/.codex/hooks.json              (if Private Brain owned)
  - ~/.codex/beast*.config.toml
  - managed block in config.toml     (# >>> PRIVATE_BRAIN_BEAST_BEGIN ...)
    including orphaned BEGIN-without-END blocks from partial installs
  - AGENTS.md PRIVATE_BRAIN_SIDELOAD and PRIVATE_BRAIN_OVERLAY overlays
  - prompts/beastMode*.md, brainBootstrap.md
  - launchers: beastMode*, pb-codex, pb-boot, pb-status, pb-nuclear
  - known Private Brain agent prompts (.md) and codex-agents (.toml)
  - skills/private-brain (distilled skill)
  - PRIVATE_BRAIN_DISTILL markers in AGENTS.md
  - [projects.".../private-brain"] trust stanzas
  - live_gui / graph_gl processes

What it keeps (vanilla Codex):
  - auth.json, sessions, config.toml (after strip), other skills/plugins, sqlite, etc.

Flags:
  --keep-brain     archive .brain data under ~/.codex/private-brain-archive-* (default)
  --purge-brain    delete graph/audit data permanently
  --dry-run        print actions only
  --json           machine-readable report

CLI:
  python uninstall_private_brain.py
  python uninstall_private_brain.py --purge-brain
  python -m private_brain uninstall
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER_BEGIN = "# >>> PRIVATE_BRAIN_BEAST_BEGIN (managed)"
MARKER_END = "# <<< PRIVATE_BRAIN_BEAST_END"

# Both historical overlays (Install-PrivateBrain.ps1 vs python sideload)
AGENTS_MARKERS = [
    ("<!-- PRIVATE_BRAIN_SIDELOAD -->", "<!-- /PRIVATE_BRAIN_SIDELOAD -->"),
    ("<!-- PRIVATE_BRAIN_OVERLAY -->", "<!-- /PRIVATE_BRAIN_OVERLAY -->"),
]

LAUNCHER_NAMES = [
    "beastMode",
    "beastMode.cmd",
    "beastModeGodsEye",
    "beastModeGodsEye.cmd",
    "pb-codex",
    "pb-codex.cmd",
    "pb-boot",
    "pb-boot.cmd",
    "pb-status",
    "pb-status.cmd",
    "pb-nuclear",
    "pb-nuclear.cmd",
]

PROMPT_NAMES = [
    "beastMode.md",
    "beastModeGodsEye.md",
    "brainBootstrap.md",
]

BEAST_PROFILES = (
    "beast.config.toml",
    "beast-godseye.config.toml",
    "beast-nuclear.config.toml",
)

# Role agent prompts under CODEX_HOME/agents or private-brain/agents
PB_AGENT_MD = [
    "orchestrator.md",
    "watcher.md",
    "auditor.md",
    "visualizer.md",
    "retriever.md",
    "graph-writer.md",
    "gitlab-topo.md",
    "gitlab-deep.md",
    "jira-topo.md",
    "jira-deep.md",
    "confluence-topo.md",
    "confluence-deep.md",
    "_shared_preamble.md",
    "cost_manager.md",
    "db_manager.md",
    "optimizer.md",
    "rater.md",
    "security_auditor.md",
    "smart-discover.md",
    "synthesizer.md",
    "metrics-master.md",
]

# codex-agents installed into ~/.codex/agents/*.toml
PB_AGENT_TOML = [
    "orchestrator.toml",
    "watcher.toml",
    "auditor.toml",
    "retriever.toml",
    "graph-writer.toml",
    "gitlab-topo.toml",
    "gitlab-deep.toml",
    "jira-topo.toml",
    "jira-deep.toml",
    "confluence-topo.toml",
    "confluence-deep.toml",
    "metrics-master.toml",
]

PB_CONTENT_HINTS = (
    "Private Brain",
    "RAG-DAG",
    "beast mode",
    "spawn_agent",
    "PRIVATE_BRAIN",
    "private-brain",
    "godseye",
    "session_boot",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def codex_home() -> Path:
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]).expanduser().resolve()
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
    return (home / ".codex").resolve()


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


def bin_dirs() -> list[Path]:
    h = user_home()
    dirs: list[Path] = [h / "bin", h / ".local" / "bin"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "WindowsApps")
    return dirs


def _run_quiet(cmd: list[str] | str, *, shell: bool = False) -> None:
    try:
        subprocess.run(
            cmd,
            shell=shell,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
        )
    except Exception:
        pass


def kill_guis(brain: Path, dry: bool, actions: list[str]) -> None:
    scripts = brain / "scripts"
    if scripts.is_dir() and str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from godseye import terminate_existing_guis  # type: ignore

        if dry:
            actions.append("dry-run: would kill live_gui/graph_gl processes")
            return
        r = terminate_existing_guis(brain)
        actions.append(f"killed_guis found={r.get('found')} killed={r.get('killed')}")
        return
    except Exception as e:
        actions.append(f"godseye_kill_skip: {e}"[:120])

    if dry:
        actions.append("dry-run: would kill live_gui/graph_gl processes")
        return

    if sys.platform == "win32":
        for pat in ("live_gui.py", "graph_gl.py"):
            _run_quiet(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-CimInstance Win32_Process | "
                 f"Where-Object {{ $_.CommandLine -like '*{pat}*' }} | "
                 f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"]
            )
        actions.append("taskkill_fallback_attempted")
    else:
        _run_quiet("pkill -f 'private-brain/visualizer/live_gui.py' 2>/dev/null", shell=True)
        _run_quiet("pkill -f 'private-brain/visualizer/graph_gl.py' 2>/dev/null", shell=True)
        _run_quiet("pkill -f 'visualizer/live_gui.py' 2>/dev/null", shell=True)
        _run_quiet("pkill -f 'visualizer/graph_gl.py' 2>/dev/null", shell=True)
        actions.append("pkill_fallback_attempted")


def strip_managed_toml(text: str) -> tuple[str, bool]:
    """Remove managed Private Brain block. Handles missing END marker (orphaned BEGIN)."""
    changed = False
    if MARKER_BEGIN not in text and "PRIVATE_BRAIN_BEAST" not in text:
        return text, False

    if MARKER_BEGIN in text and MARKER_END in text:
        pattern = re.compile(
            re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END),
            re.DOTALL,
        )
        new = pattern.sub("", text)
        if new != text:
            text = new
            changed = True
    elif MARKER_BEGIN in text:
        # Orphaned BEGIN (no END) — strip from BEGIN through developer_instructions
        # closing triple-quote when present; otherwise through next top-level [table].
        start = text.find(MARKER_BEGIN)
        after = text[start:]
        end_rel: int | None = None
        m_dev = re.search(r'developer_instructions\s*=\s*"""', after)
        if m_dev:
            close = after.find('"""', m_dev.end())
            if close != -1:
                end_rel = close + 3
        if end_rel is None:
            m_tbl = re.search(r"\n\s*\[[^\]]+\]", after[len(MARKER_BEGIN) :])
            if m_tbl:
                end_rel = len(MARKER_BEGIN) + m_tbl.start()
            else:
                end_rel = len(after)
        text = text[:start] + after[end_rel:]
        changed = True

    # Drop [projects."…/private-brain"] trust stanzas (install side-effect)
    proj_pat = re.compile(
        r"\n?\[projects\.\"[^\"]*private-brain[^\"]*\"\]\s*\n"
        r"(?:[^\[]*\n)*?",
        re.IGNORECASE,
    )
    new = proj_pat.sub("\n", text)
    if new != text:
        text = new
        changed = True

    # Drop legacy top-level beast keys only if they still point at private-brain
    if "private-brain" in text and "model_instructions_file" in text:
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r'^model_instructions_file\s*=\s*".*private-brain', line):
                changed = True
                i += 1
                continue
            if re.match(r"^developer_instructions\s*=\s*\"\"\"", line) and i + 1 < len(lines):
                # Only strip if body mentions Private Brain and no managed marker context left
                block = [line]
                i += 1
                while i < len(lines):
                    block.append(lines[i])
                    if '"""' in lines[i] and not lines[i].strip().startswith('developer_instructions'):
                        # end of multiline — check if this line is only """
                        if lines[i].strip() == '"""' or lines[i].rstrip().endswith('"""'):
                            i += 1
                            break
                    i += 1
                body = "".join(block)
                if "Private Brain" in body or "PRIVATE_BRAIN" in body or "private-brain" in body:
                    # If markers already gone but orphan instructions remain at top-level
                    if MARKER_BEGIN not in body:
                        changed = True
                        continue
                out.extend(block)
                continue
            out.append(line)
            i += 1
        text = "".join(out)

    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text, changed


def strip_agents_overlay(text: str) -> tuple[str, bool]:
    changed = False
    for begin, end in AGENTS_MARKERS:
        if begin in text:
            pattern = re.compile(
                re.escape(begin) + r".*?" + re.escape(end),
                re.DOTALL,
            )
            new = pattern.sub("", text)
            if new != text:
                text = new
                changed = True
            elif begin in text and end not in text:
                # orphaned open marker — drop from begin to EOF or next HTML comment close-ish
                start = text.find(begin)
                text = text[:start].rstrip() + "\n"
                changed = True
    # Also strip bare legacy blocks that mention overlay without perfect markers
    if "PRIVATE_BRAIN_OVERLAY" in text or "PRIVATE_BRAIN_SIDELOAD" in text:
        text = re.sub(
            r"<!--\s*/?\s*PRIVATE_BRAIN_(?:OVERLAY|SIDELOAD)\s*-->",
            "",
            text,
        )
        changed = True
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if text:
        text += "\n"
    return text, changed


def looks_like_pb(content: str) -> bool:
    low = content[:4000]
    low_l = low.lower()
    for h in PB_CONTENT_HINTS:
        if h.lower() in low_l or h in low:
            return True
    return False


def rm_path(p: Path, dry: bool, actions: list[str], *, kind: str = "path") -> bool:
    if not p.exists() and not p.is_symlink():
        return False
    if dry:
        actions.append(f"dry-run: would remove {kind} {p}")
        return True
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        actions.append(f"removed {kind}: {p}")
        return True
    except Exception as e:
        actions.append(f"FAILED remove {p}: {e}"[:160])
        return False


def uninstall(
    *,
    keep_brain: bool = True,
    dry_run: bool = False,
    codex: Path | None = None,
) -> dict[str, Any]:
    ch = codex or codex_home()
    if codex is not None:
        ch = Path(codex).expanduser().resolve()
    brain = Path(os.environ.get("PRIVATE_BRAIN_HOME") or (ch / "private-brain")).expanduser().resolve()
    actions: list[str] = []
    report: dict[str, Any] = {
        "ok": True,
        "codex_home": str(ch),
        "brain_home": str(brain),
        "keep_brain": keep_brain,
        "dry_run": dry_run,
        "actions": actions,
        "archived_brain": None,
        "removed": {},
    }

    if not ch.is_dir():
        report["ok"] = False
        report["error"] = f"CODEX_HOME missing: {ch}"
        return report

    # 1) stop GUIs
    if brain.is_dir():
        kill_guis(brain, dry_run, actions)
    else:
        # Still try global pkill patterns (engine already gone)
        kill_guis(brain, dry_run, actions)

    # 2) archive or purge .brain
    brain_data = brain / ".brain"
    archive_path = None
    if brain_data.is_dir() and keep_brain:
        archive_path = ch / f"private-brain-archive-{utc_stamp()}"
        if dry_run:
            actions.append(f"dry-run: would archive {brain_data} → {archive_path}")
        else:
            try:
                shutil.move(str(brain_data), str(archive_path))
                actions.append(f"archived_brain: {archive_path}")
            except Exception as e:
                try:
                    shutil.copytree(brain_data, archive_path)
                    shutil.rmtree(brain_data)
                    actions.append(f"archived_brain_copy: {archive_path}")
                except Exception as e2:
                    actions.append(f"archive_failed: {e}; {e2}"[:200])
                    report["ok"] = False
        report["archived_brain"] = str(archive_path) if archive_path else None
    elif brain_data.is_dir() and not keep_brain:
        rm_path(brain_data, dry_run, actions, kind="brain_data")

    # 3) remove private-brain tree
    report["removed"]["private_brain_dir"] = rm_path(brain, dry_run, actions, kind="engine")

    # stash leftovers from sideload
    for p in ch.glob(".brain-stash-*"):
        rm_path(p, dry_run, actions, kind="stash")

    # 4) hooks.json — remove if PB-owned
    hooks = ch / "hooks.json"
    if hooks.exists():
        try:
            raw = hooks.read_text(encoding="utf-8")
            pb_owned = (
                "Private Brain" in raw
                or "private-brain" in raw
                or "session_start.py" in raw
                or "user_prompt_submit.py" in raw
                or "stop_validate.py" in raw
            )
            if pb_owned:
                if not dry_run:
                    bak = ch / f"hooks.json.bak.uninstall.{utc_stamp()}"
                    shutil.copy2(hooks, bak)
                    actions.append(f"backed_up_hooks: {bak}")
                rm_path(hooks, dry_run, actions, kind="hooks.json")
                report["removed"]["hooks_json"] = True
            else:
                actions.append("hooks.json left in place (not Private Brain owned)")
                report["removed"]["hooks_json"] = False
        except Exception as e:
            actions.append(f"hooks_json_error: {e}"[:160])
    else:
        report["removed"]["hooks_json"] = False
        actions.append("hooks.json already absent")

    hooks_dir = ch / "hooks"
    if hooks_dir.is_dir():
        try:
            if not any(hooks_dir.iterdir()):
                rm_path(hooks_dir, dry_run, actions, kind="hooks_dir")
        except Exception:
            pass

    # 5) beast profiles
    for name in BEAST_PROFILES:
        report["removed"][name] = rm_path(ch / name, dry_run, actions, kind="profile")

    # 6) strip config.toml managed block (incl. orphaned BEGIN)
    cfg = ch / "config.toml"
    if cfg.exists():
        try:
            text = cfg.read_text(encoding="utf-8")
            cleaned, changed = strip_managed_toml(text)
            if changed or MARKER_BEGIN in text or "PRIVATE_BRAIN_BEAST" in text:
                if not dry_run:
                    bak = ch / f"config.toml.bak.uninstall.{utc_stamp()}"
                    shutil.copy2(cfg, bak)
                    actions.append(f"backed_up_config: {bak}")
                    cfg.write_text(cleaned, encoding="utf-8")
                    actions.append("stripped PRIVATE_BRAIN managed block from config.toml")
                else:
                    actions.append("dry-run: would strip managed block from config.toml")
                    if MARKER_BEGIN in text and MARKER_END not in text:
                        actions.append("dry-run: note orphaned BEGIN without END (will heal)")
                report["removed"]["config_managed_block"] = True
            else:
                actions.append("config.toml has no Private Brain managed block")
                report["removed"]["config_managed_block"] = False
        except Exception as e:
            actions.append(f"config_strip_error: {e}"[:160])
            report["ok"] = False
    else:
        report["removed"]["config_managed_block"] = False

    # 7) AGENTS.md overlay (SIDELOAD + OVERLAY)
    agents = ch / "AGENTS.md"
    if agents.exists():
        try:
            text = agents.read_text(encoding="utf-8")
            needs = any(b in text for b, _ in AGENTS_MARKERS) or "PRIVATE_BRAIN_" in text
            if needs:
                cleaned, changed = strip_agents_overlay(text)
                if not dry_run:
                    bak = ch / f"AGENTS.md.bak.uninstall.{utc_stamp()}"
                    shutil.copy2(agents, bak)
                    actions.append(f"backed_up_agents: {bak}")
                    if cleaned.strip():
                        agents.write_text(cleaned, encoding="utf-8")
                        actions.append("stripped PRIVATE_BRAIN overlay(s) from AGENTS.md")
                    else:
                        agents.unlink()
                        actions.append("removed empty AGENTS.md")
                else:
                    actions.append("dry-run: would strip AGENTS.md overlay(s)")
                report["removed"]["agents_overlay"] = True
            else:
                actions.append("AGENTS.md has no Private Brain overlay")
                report["removed"]["agents_overlay"] = False
            # drop empty leftover AGENTS.md
            if agents.exists():
                try:
                    if not agents.read_text(encoding="utf-8", errors="ignore").strip():
                        rm_path(agents, dry_run, actions, kind="empty_agents")
                except Exception:
                    pass
        except Exception as e:
            actions.append(f"agents_strip_error: {e}"[:160])
    else:
        report["removed"]["agents_overlay"] = False

    # 8) prompts
    prompts = ch / "prompts"
    removed_prompts = []
    for name in PROMPT_NAMES:
        p = prompts / name
        if rm_path(p, dry_run, actions, kind="prompt"):
            removed_prompts.append(name)
    report["removed"]["prompts"] = removed_prompts

    # 9) launchers
    removed_bins = []
    for d in bin_dirs():
        if not d.is_dir():
            continue
        for name in LAUNCHER_NAMES:
            p = d / name
            if rm_path(p, dry_run, actions, kind="launcher"):
                removed_bins.append(str(p))
    report["removed"]["launchers"] = removed_bins

    # 10) agent prompts (.md) under CODEX_HOME/agents
    agents_dir = ch / "agents"
    removed_agents = []
    if agents_dir.is_dir():
        for name in PB_AGENT_MD:
            p = agents_dir / name
            if not p.exists():
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
                if looks_like_pb(t) or name.startswith("_shared"):
                    if rm_path(p, dry_run, actions, kind="agent"):
                        removed_agents.append(name)
            except Exception:
                pass
        # 11) codex-agents .toml (package copies into CODEX_HOME/agents)
        for name in PB_AGENT_TOML:
            p = agents_dir / name
            if not p.exists():
                continue
            # Known names from package/codex-agents — safe to remove
            if rm_path(p, dry_run, actions, kind="agent_toml"):
                removed_agents.append(name)

        # optional empty agents dir — leave if README or other files remain
    report["removed"]["agents"] = removed_agents

    # 11b) distilled skill (session memory surface)
    skill_dir = ch / "skills" / "private-brain"
    report["removed"]["skill"] = rm_path(skill_dir, dry_run, actions, kind="skill")

    # 12) clear user env PRIVATE_BRAIN_HOME on Windows (best-effort, non-fatal)
    if not dry_run and sys.platform == "win32":
        try:
            _run_quiet(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[Environment]::SetEnvironmentVariable('PRIVATE_BRAIN_HOME',$null,'User')",
                ]
            )
            actions.append("cleared user env PRIVATE_BRAIN_HOME (if set)")
        except Exception as e:
            actions.append(f"env_clear_skip: {e}"[:120])
    elif dry_run and sys.platform == "win32":
        actions.append("dry-run: would clear user env PRIVATE_BRAIN_HOME")

    report["ts"] = utc_stamp()
    report["actions"] = actions
    return report


def verification_checklist(ch: Path) -> dict[str, Any]:
    """Post-uninstall: what should be gone vs kept."""
    brain = ch / "private-brain"
    cfg_text = ""
    if (ch / "config.toml").exists():
        cfg_text = (ch / "config.toml").read_text(encoding="utf-8", errors="ignore")
    agents_text = ""
    if (ch / "AGENTS.md").exists():
        agents_text = (ch / "AGENTS.md").read_text(encoding="utf-8", errors="ignore")
    hooks_ok = True
    if (ch / "hooks.json").exists():
        h = (ch / "hooks.json").read_text(encoding="utf-8", errors="ignore")
        hooks_ok = "private-brain" not in h and "Private Brain" not in h
    return {
        "private_brain_gone": not brain.exists(),
        "hooks_json_gone_or_non_pb": hooks_ok,
        "beast_profiles_gone": not (ch / "beast.config.toml").exists(),
        "config_exists": (ch / "config.toml").exists(),
        "auth_intact": (ch / "auth.json").exists(),
        "no_managed_marker": MARKER_BEGIN not in cfg_text and MARKER_END not in cfg_text,
        "no_agents_overlay": (
            "PRIVATE_BRAIN_SIDELOAD" not in agents_text
            and "PRIVATE_BRAIN_OVERLAY" not in agents_text
        ),
        "no_pb_agent_toml": not (ch / "agents" / "orchestrator.toml").exists(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Uninstall Private Brain sideload from Codex")
    ap.add_argument("--purge-brain", action="store_true", help="Delete .brain graph data (default: archive)")
    ap.add_argument("--keep-brain", action="store_true", default=True, help="Archive .brain (default)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--codex-home", default="")
    args = ap.parse_args(argv)

    keep = not args.purge_brain
    ch = Path(args.codex_home).expanduser().resolve() if args.codex_home else None
    report = uninstall(keep_brain=keep, dry_run=args.dry_run, codex=ch)
    ch_path = Path(report["codex_home"])
    if not args.dry_run:
        report["verify"] = verification_checklist(ch_path)
    else:
        # dry-run: report what verify *would* look like after a real run is N/A;
        # still snapshot current state for operators
        report["verify"] = verification_checklist(ch_path)
        report["verify_note"] = "verify reflects current disk state (dry-run did not mutate)"

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("Private Brain uninstall")
        print(f"  CODEX_HOME : {report['codex_home']}")
        print(f"  keep_brain : {report['keep_brain']}  dry_run={report['dry_run']}")
        for a in report["actions"]:
            print(f"  · {a}")
        if report.get("archived_brain"):
            print(f"  archived   : {report['archived_brain']}")
        print("  verify:")
        for k, v in report["verify"].items():
            print(f"    {k}: {v}")
        print("  DONE" if report["ok"] else "  DONE WITH ERRORS")
        print("  Codex itself was not removed. Run: codex")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
