#!/usr/bin/env bash
# One command. No install, no API key, no network (demo mode).
#   ./run.sh              → offline duration demo
#   ./run.sh brain        → live Private Brain RAG fan-out
#   ./run.sh test         → unittest suite
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PRIVATE_BRAIN_HOME="${PRIVATE_BRAIN_HOME:-$ROOT}"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PYTHONPATH="${ROOT}/scripts:${ROOT}:${PYTHONPATH:-}"
PY="${PRIVATE_BRAIN_HOME}/venv/bin/python3"
if [[ ! -x "$PY" ]]; then PY=python3; fi
exec "$PY" -m loop_graph_harness.pipeline "$@"
