#!/bin/bash
# Mac double-click installer (sideload into Codex)
# End users never run Python. Only beastMode / SETUP / UNINSTALL.
cd "$(dirname "$0")"
echo "Private Brain — Codex sideload"
echo "You never run Python. Only beastMode / SETUP / UNINSTALL."
echo

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PRIVATE_BRAIN_HOME="${PRIVATE_BRAIN_HOME:-$CODEX_HOME/private-brain}"
PKG_DIR="$PWD/package"
if [[ ! -d "$PKG_DIR" && -f "$PWD/beast-mode.md" ]]; then
  PKG_DIR="$PWD"
fi

install_launchers() {
  mkdir -p "$HOME/bin"
  # Full arg-driven launcher from package (never a stub)
  if [[ -f "$PKG_DIR/scripts/beastMode" ]]; then
    cp -f "$PKG_DIR/scripts/beastMode" "$HOME/bin/beastMode"
    chmod +x "$HOME/bin/beastMode"
    # Also keep a copy under private-brain/scripts for recovery/sync
    mkdir -p "$PRIVATE_BRAIN_HOME/scripts"
    cp -f "$PKG_DIR/scripts/beastMode" "$PRIVATE_BRAIN_HOME/scripts/beastMode"
    chmod +x "$PRIVATE_BRAIN_HOME/scripts/beastMode"
  fi
  if [[ -f "$PKG_DIR/scripts/beastMode.cmd" ]]; then
    cp -f "$PKG_DIR/scripts/beastMode.cmd" "$HOME/bin/beastMode.cmd"
    cp -f "$PKG_DIR/scripts/beastMode.cmd" "$PRIVATE_BRAIN_HOME/scripts/beastMode.cmd" 2>/dev/null || true
  fi
  # Optional GodsEye convenience wrapper (same as beastMode -GodsEye)
  cat > "$HOME/bin/beastModeGodsEye" <<'SH'
#!/bin/bash
exec "$(dirname "$0")/beastMode" -GodsEye "$@"
SH
  chmod +x "$HOME/bin/beastModeGodsEye"

  # Ensure ~/bin on PATH for this shell and common profiles
  case ":$PATH:" in
    *":$HOME/bin:"*) ;;
    *) export PATH="$HOME/bin:$PATH" ;;
  esac
  for rc in "$HOME/.zprofile" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc"; do
    if [[ -f "$rc" ]] || [[ "$rc" == "$HOME/.zprofile" ]]; then
      if [[ -f "$rc" ]] && grep -q 'HOME/bin' "$rc" 2>/dev/null; then
        :
      else
        if [[ ! -f "$rc" ]]; then
          # only create .zprofile if missing (mac login shells)
          [[ "$rc" == "$HOME/.zprofile" ]] || continue
          touch "$rc"
        fi
        if ! grep -q 'HOME/bin' "$rc" 2>/dev/null; then
          echo '' >> "$rc"
          echo '# Private Brain launchers' >> "$rc"
          echo 'export PATH="$HOME/bin:$PATH"' >> "$rc"
        fi
      fi
    fi
  done
}

install_prompts() {
  mkdir -p "$HOME/.codex/prompts"
  cat > "$HOME/.codex/prompts/beastMode.md" <<'MD'
---
description: Private Brain beast mode (no GUI)
---
GodsEye OFF. Run Private Brain concert. Never ask permission. Cite node_ids.
MD
  cat > "$HOME/.codex/prompts/beastModeGodsEye.md" <<'MD'
---
description: Private Brain beast + GodsEye live GUI
---
GodsEye ON. Start live_gui via godseye.ensure_gui then concert. Never ask permission. Cite node_ids.
MD
}

if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -File ./SETUP.ps1
  EC=$?
  # Ensure Mac launcher is the full bash beastMode even after PS1 (which writes .cmd)
  install_launchers
  install_prompts
  if [[ $EC -ne 0 ]]; then
    echo "SETUP.ps1 exited $EC — launchers still installed if package present"
  fi
else
  # fallback: pure bash sideload (no user-facing python)
  echo "==> Copying package → $PRIVATE_BRAIN_HOME"
  mkdir -p "$PRIVATE_BRAIN_HOME"
  if [[ -d "$PKG_DIR" ]]; then
    rsync -a --exclude venv --exclude .brain --exclude __pycache__ "$PKG_DIR/" "$PRIVATE_BRAIN_HOME/" 2>/dev/null || \
      cp -R "$PKG_DIR"/* "$PRIVATE_BRAIN_HOME/" 2>/dev/null || true
  fi

  echo "==> Python venv (internal — you never type python)"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$PRIVATE_BRAIN_HOME/venv" 2>/dev/null || true
    VENV_PIP="$PRIVATE_BRAIN_HOME/venv/bin/pip"
    VENV_PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
    REQ="$PKG_DIR/visualizer/requirements.txt"
    [[ -f "$REQ" ]] || REQ="$PRIVATE_BRAIN_HOME/visualizer/requirements.txt"

    # Corporate Package Index / approved index (Corporate Library) — never default to public PyPI in enterprise
    INDEX_URL="${PB_PIP_INDEX_URL:-${PIP_INDEX_URL:-}}"
    TRUSTED="${PB_PIP_TRUSTED_HOST:-${PIP_TRUSTED_HOST:-}}"
    REQUIRE_ART="${PB_PIP_REQUIRE_CORPORATE_INDEX:-0}"
    if [[ "${PB_ENTERPRISE:-0}" == "1" ]]; then
      REQUIRE_ART="${PB_PIP_REQUIRE_CORPORATE_INDEX:-1}"
    fi

    pip_install_req() {
      # usage: pip_install_req  — installs visualizer requirements via policy
      local args=()
      if [[ -n "$INDEX_URL" ]]; then
        echo "    pip index: $INDEX_URL"
        args+=(--index-url "$INDEX_URL")
        [[ -n "$TRUSTED" ]] && args+=(--trusted-host "$TRUSTED")
        # do not also search public PyPI
        args+=(--disable-pip-version-check)
        "$VENV_PIP" install "${args[@]}" -r "$REQ" -q 2>/dev/null \
          || "$VENV_PIP" install "${args[@]}" pygame -q 2>/dev/null \
          || return 1
        return 0
      fi
      # Preferred enterprise model: PIP_INDEX_URL → Corporate Library/Protected Gateway only (above).
      # Missing package → request Corporate Library/Protected Gateway onboard; headless core is valid.
      # vendor/wheels is NOT the primary Corporate model (legacy emergency only if present).
      if [[ "$REQUIRE_ART" == "1" || "$REQUIRE_ART" == "true" ]]; then
        echo "    enterprise: no PIP_INDEX_URL — skipping optional pygame (headless OK)"
        echo "    set corporate-package-index.env (Corporate Library/Protected Gateway) or request package onboard — see CORPORATE_PACKAGE_INDEX.md"
        echo "    policy: config/judge_corporate_library_policy.json (not offline wheel kit)"
        return 1
      fi
      # Dev laptop only: public PyPI
      echo "    pip install pygame from default index (dev only — not for Corporate enterprise)"
      "$VENV_PIP" install pygame -q 2>/dev/null || return 1
      return 0
    }

    if [[ -x "$VENV_PIP" && -f "$REQ" ]]; then
      if ! "$VENV_PY" -c "import pygame" 2>/dev/null; then
        pip_install_req || true
      fi
    fi
    if "$VENV_PY" -c "import pygame" 2>/dev/null; then
      echo "    pygame: OK (GodsEye available)"
    else
      echo "    pygame: missing — headless enterprise still works (skip -GodsEye)"
    fi
  fi

  PY="$PRIVATE_BRAIN_HOME/venv/bin/python3"
  [[ -x "$PY" ]] || PY="$(command -v python3 || true)"
  export PYTHONPATH="$PRIVATE_BRAIN_HOME"
  if [[ -n "$PY" ]]; then
    (cd "$PRIVATE_BRAIN_HOME" && "$PY" -m private_brain sideload gpt-5.6-terra) 2>/dev/null || \
      PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts" "$PY" "$PRIVATE_BRAIN_HOME/scripts/install_hooks.py" 2>/dev/null || true
    if [[ -f "$PRIVATE_BRAIN_HOME/scripts/brain_init.py" ]]; then
      PYTHONPATH="$PRIVATE_BRAIN_HOME/scripts" "$PY" "$PRIVATE_BRAIN_HOME/scripts/brain_init.py" 2>/dev/null || true
    fi
  fi

  # Default beast profiles if sideload did not write them
  if [[ ! -f "$CODEX_HOME/beast.config.toml" ]]; then
    cat > "$CODEX_HOME/beast.config.toml" <<'TOML'
model = "gpt-5.6-terra"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_reasoning_effort = "high"
TOML
  fi
  if [[ ! -f "$CODEX_HOME/beast-godseye.config.toml" ]]; then
    cp "$CODEX_HOME/beast.config.toml" "$CODEX_HOME/beast-godseye.config.toml" 2>/dev/null || true
  fi

  install_prompts
  install_launchers
fi

echo
echo "READY — sideloaded into Codex"
echo "  You never run Python. Only beastMode / SETUP / UNINSTALL."
echo
echo "  Corporate pilot:"
echo "    ./START_AT_CORPORATE.command"
echo "    beastMode --enterprise --doctor"
echo "    beastMode --enterprise"
echo
echo "  Daily:"
echo "  beastMode                         # headless"
echo "  beastMode -GodsEye                # live GUI (needs pygame)"
echo "  beastMode --swarm 32"
echo "  beastMode -ingestion URL --max"
echo "  beastMode --enterprise -ingestion https://INTERNAL/group --ingest-only"
echo "  beastMode --preset salsa --max"
echo "  beastMode --sync-memory"
echo "  beastMode --doctor                # READY / FAIL"
echo "  beastMode --nuclear"
echo
echo "  codex -p beast"
echo "  Inside Codex: /prompts:beastMode  /prompts:beastModeGodsEye"
echo
echo "  Launcher: $HOME/bin/beastMode"
echo "  Brain:    $PRIVATE_BRAIN_HOME"
echo
read -n 1 -s -r -p "Press any key to close..."
echo
