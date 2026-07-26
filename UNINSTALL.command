#!/bin/bash
# Mac one-click uninstaller — double-click in Finder
set -e
cd "$(dirname "$0")"
echo "════════════════════════════════════════════"
echo "  Private Brain — UNINSTALL from Codex"
echo "════════════════════════════════════════════"
echo "  Codex CLI stays. Sideload wiring is removed."
echo "  Knowledge graph (.brain) is ARCHIVED by default."
echo ""

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PKG="$PWD/package"
SCRIPTS=""
if [[ -f "$PKG/scripts/uninstall_private_brain.py" ]]; then
  SCRIPTS="$PKG/scripts"
elif [[ -f "$CODEX_HOME/private-brain/scripts/uninstall_private_brain.py" ]]; then
  SCRIPTS="$CODEX_HOME/private-brain/scripts"
elif [[ -f "$PWD/package/scripts/uninstall_private_brain.py" ]]; then
  SCRIPTS="$PWD/package/scripts"
fi

if [[ -z "$SCRIPTS" ]]; then
  echo "ERROR: uninstall_private_brain.py not found" >&2
  read -r -p "Press Enter to close..."
  exit 1
fi

PY=""
if [[ -x "$CODEX_HOME/private-brain/venv/bin/python3" ]]; then
  PY="$CODEX_HOME/private-brain/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  echo "ERROR: python3 required" >&2
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Using: $PY"
echo "Script: $SCRIPTS/uninstall_private_brain.py"
echo ""
"$PY" "$SCRIPTS/uninstall_private_brain.py" "$@"
EC=$?
echo ""
if [[ $EC -eq 0 ]]; then
  echo "Uninstall complete. Test vanilla Codex:"
  echo "  codex"
  echo "  /Applications/ChatGPT.app/Contents/Resources/codex exec --skip-git-repo-check 'say hi'"
else
  echo "Uninstall finished with errors (exit $EC)"
fi
echo ""
read -r -p "Press Enter to close..."
exit $EC
