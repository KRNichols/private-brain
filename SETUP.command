#!/bin/bash
# Mac / Unix installer — sideload Private Brain into Codex
# End users never run Python. Only beastMode / SETUP / UNINSTALL.
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
echo "Private Brain — Codex sideload"
echo "You never run Python. Only beastMode / SETUP / UNINSTALL."
echo

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PRIVATE_BRAIN_HOME="${PRIVATE_BRAIN_HOME:-$CODEX_HOME/private-brain}"
export PB_ENTERPRISE="${PB_ENTERPRISE:-1}"

# Resolve package / engine root (kit layout: tools/engine OR package/ OR cwd)
PKG_DIR=""
for cand in \
  "${PB_ENGINE:-}" \
  "$HERE/package" \
  "$HERE/../engine" \
  "$HERE/tools/engine" \
  "$HERE"
do
  [[ -z "$cand" ]] && continue
  if [[ -d "$cand/scripts" && ( -f "$cand/scripts/organism.py" || -f "$cand/scripts/install_hooks.py" || -f "$cand/scripts/beastMode" ) ]]; then
    PKG_DIR="$(cd "$cand" && pwd)"
    break
  fi
done
if [[ -z "$PKG_DIR" ]]; then
  echo "ERROR: could not find engine/package (scripts/organism.py) near $HERE" >&2
  exit 2
fi
echo "  Package: $PKG_DIR"
echo "  Brain:   $PRIVATE_BRAIN_HOME"
echo "  Codex:   $CODEX_HOME"

install_launchers() {
  mkdir -p "$HOME/bin" "$PRIVATE_BRAIN_HOME/scripts"
  if [[ -f "$PKG_DIR/scripts/beastMode" ]]; then
    cp -f "$PKG_DIR/scripts/beastMode" "$HOME/bin/beastMode"
    cp -f "$PKG_DIR/scripts/beastMode" "$PRIVATE_BRAIN_HOME/scripts/beastMode"
    chmod +x "$HOME/bin/beastMode" "$PRIVATE_BRAIN_HOME/scripts/beastMode"
  fi
  cat > "$HOME/bin/beastModeGodsEye" <<'SH'
#!/bin/bash
exec "$(dirname "$0")/beastMode" -GodsEye "$@"
SH
  chmod +x "$HOME/bin/beastModeGodsEye"
  case ":$PATH:" in
    *":$HOME/bin:"*) ;;
    *) export PATH="$HOME/bin:$PATH" ;;
  esac
  for rc in "$HOME/.zprofile" "$HOME/.zshrc"; do
    if [[ -f "$rc" ]] || [[ "$rc" == "$HOME/.zprofile" ]]; then
      [[ -f "$rc" ]] || touch "$rc"
      if ! grep -q 'HOME/bin' "$rc" 2>/dev/null; then
        echo '' >> "$rc"
        echo '# Private Brain launchers' >> "$rc"
        echo 'export PATH="$HOME/bin:$PATH"' >> "$rc"
      fi
    fi
  done
}

install_prompts() {
  mkdir -p "$CODEX_HOME/prompts"
  cat > "$CODEX_HOME/prompts/beastMode.md" <<'MD'
---
description: Private Brain beast mode (no GUI)
---
GodsEye OFF. Run Private Brain concert. Never ask permission. Cite node_ids.
MD
  cat > "$CODEX_HOME/prompts/beastModeGodsEye.md" <<'MD'
---
description: Private Brain beast + GodsEye live GUI
---
GodsEye ON. Start live_gui via godseye.ensure_gui then concert. Never ask permission. Cite node_ids.
MD
}

install_profiles() {
  mkdir -p "$CODEX_HOME"
  if [[ ! -f "$CODEX_HOME/beast.config.toml" ]]; then
    cat > "$CODEX_HOME/beast.config.toml" <<'TOML'
model = "gpt-5.6-terra"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"
TOML
  fi
  if [[ ! -f "$CODEX_HOME/beast-enterprise.config.toml" ]]; then
    cat > "$CODEX_HOME/beast-enterprise.config.toml" <<'TOML'
model = "gpt-5.6-terra"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"
TOML
  fi
  if [[ ! -f "$CODEX_HOME/beast-godseye.config.toml" ]]; then
    cp "$CODEX_HOME/beast.config.toml" "$CODEX_HOME/beast-godseye.config.toml" 2>/dev/null || true
  fi
}

# Prefer native bash on Darwin / when Windows installer pieces are missing.
# (Mac runners often have pwsh but no SETUP.ps1 next to this script in the kit.)
USE_PS1=0
if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Darwin" ]] \
   && command -v pwsh >/dev/null 2>&1 \
   && [[ -f "$HERE/SETUP.ps1" ]] \
   && [[ -f "$HERE/Install-PrivateBrain.ps1" || -f "$PKG_DIR/../install/Install-PrivateBrain.ps1" ]]; then
  USE_PS1=1
fi

if [[ "$USE_PS1" == "1" ]]; then
  echo "==> SETUP.ps1 path"
  pwsh -NoProfile -File "$HERE/SETUP.ps1" || true
fi

echo "==> Copying engine → $PRIVATE_BRAIN_HOME"
mkdir -p "$PRIVATE_BRAIN_HOME"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude venv --exclude .brain --exclude '__pycache__' --exclude '*.pyc' \
    "$PKG_DIR/" "$PRIVATE_BRAIN_HOME/"
else
  # portable copy
  (
    cd "$PKG_DIR"
    tar cf - \
      --exclude=venv --exclude=.brain --exclude='__pycache__' --exclude='*.pyc' \
      . 2>/dev/null || find . -type f ! -path './venv/*' ! -path './.brain/*' ! -name '*.pyc' -print0 | tar cf - --null -T -
  ) | ( cd "$PRIVATE_BRAIN_HOME" && tar xf - ) 2>/dev/null || {
    cp -R "$PKG_DIR"/* "$PRIVATE_BRAIN_HOME/" 2>/dev/null || true
  }
fi

echo "==> Python venv (internal — you never type python)"
if command -v python3 >/dev/null 2>&1; then
  python3 -m venv "$PRIVATE_BRAIN_HOME/venv" 2>/dev/null || true
  VENV_PIP="$PRIVATE_BRAIN_HOME/venv/bin/pip"
  VENV_PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
  REQ="$PKG_DIR/visualizer/requirements.txt"
  [[ -f "$REQ" ]] || REQ="$PRIVATE_BRAIN_HOME/visualizer/requirements.txt"

  INDEX_URL="${PB_PIP_INDEX_URL:-${PIP_INDEX_URL:-}}"
  TRUSTED="${PB_PIP_TRUSTED_HOST:-${PIP_TRUSTED_HOST:-}}"
  REQUIRE_ART="${PB_PIP_REQUIRE_CORPORATE_INDEX:-0}"
  if [[ "${PB_ENTERPRISE:-0}" == "1" ]]; then
    REQUIRE_ART="${PB_PIP_REQUIRE_CORPORATE_INDEX:-1}"
  fi

  if [[ -x "$VENV_PIP" && -f "$REQ" ]]; then
    if ! "$VENV_PY" -c "import pygame" 2>/dev/null; then
      if [[ -n "$INDEX_URL" ]]; then
        args=(--index-url "$INDEX_URL" --disable-pip-version-check)
        [[ -n "$TRUSTED" ]] && args+=(--trusted-host "$TRUSTED")
        "$VENV_PIP" install "${args[@]}" -r "$REQ" -q 2>/dev/null \
          || "$VENV_PIP" install "${args[@]}" pygame -q 2>/dev/null \
          || true
      elif [[ "$REQUIRE_ART" == "1" || "$REQUIRE_ART" == "true" ]]; then
        echo "    enterprise: no PIP_INDEX_URL — headless OK (Corporate Library / Protected Gateway optional)"
      else
        "$VENV_PIP" install pygame -q 2>/dev/null || true
      fi
    fi
  fi
  if [[ -x "$VENV_PY" ]] && "$VENV_PY" -c "import pygame" 2>/dev/null; then
    echo "    pygame: OK (GodsEye available)"
  else
    echo "    pygame: missing — headless enterprise still works (skip -GodsEye)"
  fi
fi

PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
[[ -x "$PY" ]] || PY="$(command -v python3 || true)"
export PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts:$PRIVATE_BRAIN_HOME:${PYTHONPATH:-}"

echo "==> Install hooks + profiles"
if [[ -n "$PY" && -f "$PRIVATE_BRAIN_HOME/scripts/install_hooks.py" ]]; then
  PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts:$PRIVATE_BRAIN_HOME" \
    "$PY" "$PRIVATE_BRAIN_HOME/scripts/install_hooks.py" || true
fi
if [[ -n "$PY" && -f "$PRIVATE_BRAIN_HOME/scripts/brain_init.py" ]]; then
  PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts:$PRIVATE_BRAIN_HOME" \
    "$PY" "$PRIVATE_BRAIN_HOME/scripts/brain_init.py" 2>/dev/null || true
fi
# Module path sideload (optional)
if [[ -n "$PY" && -d "$PRIVATE_BRAIN_HOME/private_brain" ]]; then
  (cd "$PRIVATE_BRAIN_HOME" && "$PY" -m private_brain sideload gpt-5.6-terra) 2>/dev/null || true
fi

install_prompts
install_launchers
install_profiles

# Fail closed: hooks + brain scripts must exist after SETUP
if [[ ! -f "$CODEX_HOME/hooks.json" ]]; then
  # last-chance minimal hooks write if install_hooks failed
  if [[ -n "$PY" && -f "$PRIVATE_BRAIN_HOME/scripts/install_hooks.py" ]]; then
    PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts" "$PY" "$PRIVATE_BRAIN_HOME/scripts/install_hooks.py" || true
  fi
fi
if [[ ! -f "$CODEX_HOME/hooks.json" ]]; then
  echo "ERROR: hooks.json missing after SETUP — fail closed" >&2
  exit 3
fi
if [[ ! -f "$PRIVATE_BRAIN_HOME/scripts/organism.py" && ! -f "$PRIVATE_BRAIN_HOME/scripts/orchestrate.py" ]]; then
  echo "ERROR: brain scripts missing after SETUP — fail closed" >&2
  exit 3
fi

echo
echo "READY — sideloaded into Codex"
echo "  You never run Python. Only beastMode / SETUP / UNINSTALL."
echo
echo "  Corporate pilot:"
echo "    ./START_AT_CORPORATE.command   # or tools/install/START.command"
echo "    beastMode --enterprise --doctor"
echo "    beastMode --enterprise"
echo
echo "  Daily: open Codex and talk (hooks already on)."
echo "  Launcher: $HOME/bin/beastMode"
echo "  Brain:    $PRIVATE_BRAIN_HOME"
echo "  Hooks:    $CODEX_HOME/hooks.json"
echo

# No interactive pause in CI / noninteractive / pipes
if [[ "${PB_CI:-0}" == "1" || "${PB_NONINTERACTIVE:-0}" == "1" || ! -t 0 ]]; then
  exit 0
fi
if [[ -t 0 ]]; then
  read -n 1 -s -r -p "Press any key to close..." || true
  echo
fi
exit 0
