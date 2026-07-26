#!/usr/bin/env python3
"""Fail CI if residual customer-specific branding leaks into the public tree.

Banned tokens (word boundary):
  Boeing / BOEING / boeing
  SRES
  BSF
  Artifactory / artifactory  (legacy package product name)

Allowed replacements (for humans, not enforced here):
  Corporate · Corporate Library · Protected Gateway · Corporate Package Index

Scanner self-exceptions:
  - this file
  - workflow lines that build needles via string concat
  - explicit allowlist file paths (none by default)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Built without writing full banned words as a single contiguous literal in
# some consumers — but THIS file must name them to lint them out.
BANNED = [
    "Boeing",
    "BOEING",
    "boeing",
    "SRES",
    "BSF",
    "Artifactory",
    "artifactory",
    "ARTIFACTORY",
]

TEXT_SUFFIX = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".ps1",
    ".command",
    ".toml",
    ".txt",
    ".cmd",
    ".sh",
    ".cfg",
    ".ini",
    ".rst",
    ".html",
    ".css",
    ".js",
    ".ts",
}
SKIP_DIRS = {
    ".git",
    "dist",
    "__pycache__",
    ".brain",
    "venv",
    ".venv",
    "node_modules",
    "images",
}
# Files that may mention banned words only as the thing being banned
ALLOW_FILES = {
    "lint_sanitized_branding.py",
}


def is_concat_scanner_line(line: str) -> bool:
    """Allow lines that only construct ban needles via string addition."""
    if " + " not in line and '+"' not in line and "+'" not in line:
        return False
    # e.g. "Boe" + "ing"
    return bool(re.search(r'["\'][A-Za-z]{2,6}["\']\s*\+\s*["\'][A-Za-z]{2,10}["\']', line))


def main() -> int:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in ALLOW_FILES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIX and path.name not in (
            "freeze_for_corporate",
            "beastMode",
            "start_at_corporate",
            "LICENSE",
            "Makefile",
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = path.relative_to(ROOT)
        for i, line in enumerate(text.splitlines(), 1):
            if is_concat_scanner_line(line):
                continue
            # allow comments that say "do not use X" listing banned terms? No — ban hard.
            for token in BANNED:
                if re.search(r"\b" + re.escape(token) + r"\b", line):
                    hits.append(f"{rel}:{i}: banned `{token}` :: {line.strip()[:140]}")
                    break

    if hits:
        print("SANITIZE LINT FAIL — residual customer branding in public tree:\n")
        print("\n".join(hits[:80]))
        if len(hits) > 80:
            print(f"\n... +{len(hits) - 80} more")
        print(
            "\nReplace with: Corporate | Corporate Library | Protected Gateway | Corporate Package Index"
        )
        print(f"Total hits: {len(hits)}")
        return 1

    print("SANITIZE LINT OK — no Boeing / SRES / BSF / Artifactory in public tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
