#!/bin/bash
# Private Brain — macOS water-pipe (PARITY with windows START.ps1)
# Lives at: tools/install/START.command
# Kit root: README.md · DIAGRAM.md · tools/
set -euo pipefail
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS_DIR="$(cd "$INSTALL_DIR/.." && pwd)"
ROOT="$(cd "$TOOLS_DIR/.." && pwd)"
if [[ -d "$TOOLS_DIR/engine" ]]; then
  ENGINE="$TOOLS_DIR/engine"
elif [[ -d "$INSTALL_DIR/package" ]]; then
  ROOT="$INSTALL_DIR"
  TOOLS_DIR="$INSTALL_DIR"
  ENGINE="$INSTALL_DIR/package"
else
  ENGINE="$TOOLS_DIR/engine"
fi
export PB_KIT_ROOT="$ROOT"
export PB_ENGINE="$ENGINE"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PRIVATE_BRAIN_HOME="${PRIVATE_BRAIN_HOME:-$CODEX_HOME/private-brain}"
export PATH="$HOME/bin:/Applications/ChatGPT.app/Contents/Resources:${PATH:-}"
export PB_ENTERPRISE=1
export PB_GODSEYE="${PB_GODSEYE:-1}"
export PB_AWS_REGION="${PB_AWS_REGION:-gov-region-1}"
export PB_SWARM_AGENTS="${PB_SWARM_AGENTS:-auto}"
export PB_MAX_AGENTS="${PB_MAX_AGENTS:-auto}"
export PB_ORGANISM_INTERVIEW="${PB_ORGANISM_INTERVIEW:-1}"
export PYGAME_HIDE_SUPPORT_PROMPT=1

chmod +x "$INSTALL_DIR/SETUP.command" "$INSTALL_DIR/UNINSTALL.command" \
  "$ENGINE/scripts/beastMode" "$ENGINE/scripts/day1_first_start.py" "$ENGINE/scripts/organism.py" 2>/dev/null || true

echo "=============================================="
echo " Private Brain — WATER PIPE (macOS)"
echo " Same product as Windows. Open Codex after this."
echo " Golden: tools/install/golden_join.json when Corporate provides it"
echo "=============================================="
echo " Kit:    $ROOT"
echo " Engine: $ENGINE"
echo " Codex:  $CODEX_HOME"
echo ""

PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then
  echo "ERROR: python3 not found (need 3.10+)" >&2
  exit 1
fi
if [[ -x "$PRIVATE_BRAIN_HOME/venv/bin/python3" ]]; then
  PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
fi

need_setup=0
[[ -f "$PRIVATE_BRAIN_HOME/scripts/organism.py" || -f "$PRIVATE_BRAIN_HOME/scripts/orchestrate.py" ]] || need_setup=1
[[ -f "$CODEX_HOME/hooks.json" ]] || need_setup=1
if [[ "$need_setup" == "1" ]]; then
  echo "==> Installing sideload (SETUP)"
  if [[ -f "$INSTALL_DIR/SETUP.command" ]]; then
    # SETUP expects package next to it or PB paths — use engine as package root
    ( cd "$ENGINE" && bash "$INSTALL_DIR/SETUP.command" ) || bash "$INSTALL_DIR/SETUP.command" || true
  fi
  if [[ -x "$PRIVATE_BRAIN_HOME/venv/bin/python3" ]]; then
    PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
  fi
fi

export PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts:$PRIVATE_BRAIN_HOME:$ENGINE/scripts:${PYTHONPATH:-}"

ORG="$PRIVATE_BRAIN_HOME/scripts/organism.py"
[[ -f "$ORG" ]] || ORG="$ENGINE/scripts/organism.py"
DAY1="$PRIVATE_BRAIN_HOME/scripts/day1_first_start.py"
[[ -f "$DAY1" ]] || DAY1="$ENGINE/scripts/day1_first_start.py"

for envf in "$PRIVATE_BRAIN_HOME/day1.env" "$INSTALL_DIR/day1.env" "$INSTALL_DIR/corporate-package-index.env"; do
  if [[ -f "$envf" ]]; then
    echo "==> Loading $envf"
    set +u
    # shellcheck disable=SC1090
    source "$envf"
    set -u
    break
  fi
done
export PB_ENTERPRISE=1

JOIN=""
if [[ -f "$INSTALL_DIR/golden_join.json" ]]; then
  JOIN="$INSTALL_DIR/golden_join.json"
elif [[ -f "$ROOT/golden_join.json" ]]; then
  JOIN="$ROOT/golden_join.json"
elif [[ -f "$PRIVATE_BRAIN_HOME/.brain/state/golden_join.json" ]]; then
  JOIN="$PRIVATE_BRAIN_HOME/.brain/state/golden_join.json"
fi
if [[ -n "$JOIN" ]]; then
  echo "==> Join kit found: $JOIN"
  export PB_NONINTERACTIVE=1
  if [[ -f "$DAY1" ]]; then
    "$PY" "$DAY1" --yes --join "$JOIN" || true
  fi
fi

echo "==> ORGANISM water-pipe (sessions · golden · GodsEye · swarm · AWS)"
if [[ ! -f "$ORG" ]]; then
  echo "ERROR: organism.py missing — SETUP incomplete" >&2
  exit 1
fi
OARGS=()
if [[ -z "$JOIN" && "${1:-}" == "--yes" ]]; then
  export PB_NONINTERACTIVE=1
  if [[ -f "$DAY1" ]]; then
    "$PY" "$DAY1" "$@" || true
  fi
fi
if [[ "${PB_GODSEYE:-1}" == "0" ]]; then
  OARGS+=(--no-godseye)
fi
set +e
"$PY" "$ORG" "${OARGS[@]+"${OARGS[@]}"}"
ORG_RC=$?
set -e
if [[ "${ORG_RC}" -ne 0 ]]; then
  echo "NOTE: organism exit ${ORG_RC} (not fully ALIVE yet is OK on Day-1 — hooks/sideload still READY)"
fi

BM="$HOME/bin/beastMode"
if [[ ! -x "$BM" ]]; then
  mkdir -p "$HOME/bin" "$PRIVATE_BRAIN_HOME/scripts"
  if [[ -f "$ENGINE/scripts/beastMode" ]]; then
    cp -f "$ENGINE/scripts/beastMode" "$HOME/bin/beastMode"
    cp -f "$ENGINE/scripts/beastMode" "$PRIVATE_BRAIN_HOME/scripts/beastMode"
  fi
  chmod +x "$HOME/bin/beastMode" "$PRIVATE_BRAIN_HOME/scripts/beastMode" 2>/dev/null || true
fi
export PATH="$HOME/bin:$PATH"

echo ""
echo "=============================================="
echo " READY — open Codex and talk"
echo " Pause:  say 'stop beast mode' in chat"
echo " Reopen: beast on automatically"
echo " HUD:    say 'show GodsEye'"
echo "=============================================="

export PB_ORGANISM_LIGHT=1
if [[ "${PB_NO_OPEN_CODEX:-0}" == "1" ]]; then
  exit 0
fi
if [[ -x "$HOME/bin/beastMode" ]]; then
  exec "$HOME/bin/beastMode" --enterprise
else
  echo "Open Codex Desktop now — hooks are wired."
fi
