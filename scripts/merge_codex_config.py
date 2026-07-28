#!/usr/bin/env python3
"""
Merge Private Brain beast mode into an existing Codex install.

Codex CLI 0.146+:
  Profiles are SEPARATE files:  ~/.codex/<name>.config.toml
  NOT [profiles.name] tables inside config.toml (legacy rejected).

This script:
  - Backs up config.toml
  - Injects managed top-level beast keys (approval never, danger-full-access, instructions)
  - Merges [features]/[agents] without duplicate tables
  - Writes beast.config.toml + beast-nuclear.config.toml profile files
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER_BEGIN = "# >>> PRIVATE_BRAIN_BEAST_BEGIN (managed)"
MARKER_END = "# <<< PRIVATE_BRAIN_BEAST_END"

TOP_KEYS = [
    "approval_policy",
    "sandbox_mode",
    "model_instructions_file",
    "developer_instructions",
    "model_reasoning_effort",
    "personality",
    "project_doc_max_bytes",
    "profile",  # strip legacy selector
    "model",
]

# Legacy inline profile tables — always strip
TABLES_REPLACE = {
    "profiles.beast",
    "profiles.beast-nuclear",
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def strip_managed_block(text: str) -> str:
    pattern = re.compile(
        re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    return pattern.sub("", text)


def escape_toml_multiline(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"""', '\\"""')


def strip_tables_and_top_keys(text: str) -> str:
    lines = text.splitlines()
    final: list[str] = []
    current_table: str | None = None
    dropping = False
    key_re = re.compile(
        r"^(" + "|".join(re.escape(k) for k in TOP_KEYS) + r")\s*="
    )

    for line in lines:
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if m:
            current_table = m.group(1).strip()
            dropping = current_table in TABLES_REPLACE or current_table.startswith(
                "profiles."
            )
            if dropping:
                continue
            final.append(line)
            continue
        if dropping:
            continue
        if current_table is None and key_re.match(line.strip()):
            continue
        final.append(line)

    out: list[str] = []
    blank = 0
    for line in final:
        if line.strip() == "":
            blank += 1
            if blank <= 2:
                out.append(line)
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def ensure_features_and_agents(text: str) -> str:
    need_feat = {
        "multi_agent": "true",
        "shell_tool": "true",
        "unified_exec": "true",
        "goals": "true",
    }
    need_agents = {"max_threads": "6"}

    def upsert_table(src: str, table: str, kv: dict[str, str]) -> str:
        lines = src.splitlines(keepends=True)
        out: list[str] = []
        i = 0
        found = False
        while i < len(lines):
            line = lines[i]
            m = re.match(rf"^\[{re.escape(table)}\]\s*$", line.rstrip("\n"))
            if not m:
                out.append(line)
                i += 1
                continue
            found = True
            out.append(line)
            i += 1
            body: list[str] = []
            while i < len(lines) and not re.match(
                r"^\[[^\]]+\]\s*$", lines[i].rstrip("\n")
            ):
                body.append(lines[i])
                i += 1
            new_body: list[str] = []
            seen: set[str] = set()
            for b in body:
                bm = re.match(r"^([A-Za-z0-9_]+)\s*=", b.strip())
                if bm and bm.group(1) in kv:
                    new_body.append(f"{bm.group(1)} = {kv[bm.group(1)]}\n")
                    seen.add(bm.group(1))
                else:
                    new_body.append(b)
            for k, v in kv.items():
                if k not in seen:
                    new_body.insert(0, f"{k} = {v}\n")
            out.extend(new_body)
        if not found:
            out.append(f"\n[{table}]\n")
            for k, v in kv.items():
                out.append(f"{k} = {v}\n")
        return "".join(out)

    text = upsert_table(text, "features", need_feat)
    text = upsert_table(text, "agents", need_agents)
    return text


def _prepend_managed_before_first_table(cleaned: str, block: str) -> str:
    """Insert managed top-level keys before the first [table] header.

    TOML assigns bare keys after a table header to that table. Managed globals
    (approval_policy, sandbox_mode, …) must never follow [features]/[agents]/…
    """
    block = block.strip() + "\n"
    lines = cleaned.splitlines(keepends=True)
    first_table = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*\[[^\]]+\]\s*$", line):
            first_table = i
            break
    if first_table is None:
        body = "".join(lines).rstrip()
        if body:
            return body + "\n\n" + block
        return block
    head = "".join(lines[:first_table]).rstrip()
    tail = "".join(lines[first_table:]).lstrip()
    if head:
        return head + "\n\n" + block + "\n" + tail
    return block + "\n" + tail


def managed_keys_before_first_table(text: str) -> bool:
    """Return True if managed marker/keys appear before any TOML table."""
    first_table = None
    managed_at = None
    for i, line in enumerate(text.splitlines()):
        if first_table is None and re.match(r"^\s*\[[^\]]+\]\s*$", line):
            first_table = i
        if managed_at is None and (
            MARKER_BEGIN in line or line.strip().startswith("approval_policy")
        ):
            managed_at = i
    if managed_at is None:
        return False
    if first_table is None:
        return True
    return managed_at < first_table


def build_managed_block(
    beast_md: Path,
    developer_text: str,
    model: str | None,
) -> str:
    dev = escape_toml_multiline(developer_text.strip())
    beast_path = str(beast_md.resolve()).replace("\\", "/")
    model_line = f'model = "{model}"\n' if model else ""

    return f"""
{MARKER_BEGIN}
# Re-run Install-PrivateBrain.ps1 to refresh this block.
# Profiles live in beast.config.toml / beast-nuclear.config.toml (Codex 0.146+).
approval_policy = "never"
sandbox_mode = "danger-full-access"
{model_line}model_reasoning_effort = "high"
personality = "pragmatic"
project_doc_max_bytes = 65536
model_instructions_file = "{beast_path}"
developer_instructions = \"\"\"
{dev}
\"\"\"
{MARKER_END}
"""


def write_profile_file(
    codex_home: Path,
    name: str,
    model: str,
    effort: str,
    beast_md: Path,
    developer_text: str,
) -> Path:
    dev = escape_toml_multiline(developer_text.strip())
    beast_path = str(beast_md.resolve()).replace("\\", "/")
    path = codex_home / f"{name}.config.toml"
    path.write_text(
        f"""# Private Brain profile — Codex 0.146+
# Launch: codex -p {name}
# Nuclear: codex --dangerously-bypass-approvals-and-sandbox -p {name}

model = "{model}"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "{effort}"
personality = "pragmatic"
project_doc_max_bytes = 65536
model_instructions_file = "{beast_path}"
developer_instructions = \"\"\"
{dev}
\"\"\"
""",
        encoding="utf-8",
    )
    print(f"wrote profile: {path}")
    return path


def merge(
    config_path: Path,
    beast_md: Path,
    developer_file: Path,
    model: str | None,
    set_default_profile: bool,
) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    codex_home = config_path.parent
    existing = ""
    if config_path.exists():
        existing = config_path.read_text(encoding="utf-8")
        backup = config_path.with_suffix(config_path.suffix + f".bak.{utc_stamp()}")
        shutil.copy2(config_path, backup)
        print(f"backup: {backup}")

    cleaned = strip_managed_block(existing)
    cleaned = strip_tables_and_top_keys(cleaned)
    cleaned = ensure_features_and_agents(cleaned)
    developer_text = developer_file.read_text(encoding="utf-8")
    model = model or "gpt-5.6-terra"
    block = build_managed_block(beast_md, developer_text, model)
    # LAW: all managed Private Brain GLOBAL settings must appear BEFORE the first
    # TOML table. Keys after [agents]/[features]/etc. become table fields and
    # break Codex parse (e.g. approval_policy string inside [features]).
    merged = _prepend_managed_before_first_table(cleaned, block)
    config_path.write_text(merged, encoding="utf-8")
    print(f"wrote: {config_path}")

    write_profile_file(
        codex_home, "beast", model, "high", beast_md, developer_text
    )
    write_profile_file(
        codex_home, "beast-nuclear", model, "xhigh", beast_md, developer_text
    )
    # set_default_profile: top-level already has beast keys — no legacy profile=
    if set_default_profile:
        print("default session uses top-level beast keys (no legacy profile= key)")
    return config_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--beast-md", required=True)
    ap.add_argument("--developer-file", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--set-default-profile", action="store_true")
    args = ap.parse_args()
    merge(
        Path(args.config),
        Path(args.beast_md),
        Path(args.developer_file),
        args.model,
        args.set_default_profile,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
