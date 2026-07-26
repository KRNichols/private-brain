#!/usr/bin/env python3
"""Fail CI if residual customer-specific branding leaks into the public tree.

Banned stems (case-insensitive, word boundary):
  Boeing / BOEING / boeing
  SRES / sres
  BSF / bsf
  Artifactory / artifactory  (legacy package product name)

Allowed replacements (for humans, not enforced here):
  Corporate · Corporate Library · Protected Gateway · Corporate Package Index

Scanner self-exceptions:
  - this file only (by basename)
  - workflow/script lines that build needles via string concat
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Stems only — matched case-insensitively with \\b so mixed-case reintroductions fail.
# This file must name them to ban them; ALLOW_FILES excludes self.
BANNED_STEMS = (
    "boeing",
    "sres",
    "bsf",
    "artifactory",
)

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
# Only this scanner may mention banned stems (as the thing being banned).
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
            # Hard ban — no "do not use X" comments with residual tokens either.
            for stem in BANNED_STEMS:
                m = re.search(r"\b" + re.escape(stem) + r"\b", line, flags=re.IGNORECASE)
                if m:
                    hits.append(
                        f"{rel}:{i}: banned `{m.group(0)}` :: {line.strip()[:140]}"
                    )
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

    print(
        "SANITIZE LINT OK — no residual customer branding stems in public tree "
        "(Corporate / Corporate Library / Protected Gateway / Corporate Package Index only)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
