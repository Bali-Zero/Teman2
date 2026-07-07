#!/bin/bash
# LaunchAgent-safe wrapper for the local LiveKit server.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${VOICE_CONCIERGE_BACKEND_DIR:-$DEFAULT_APP_DIR}"
ENV_FILE="${VOICE_CONCIERGE_LIVEKIT_ENV_FILE:-/Users/nuzantara/.config/nuzantara/local-livekit.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export HOME="${HOME:-/Users/nuzantara}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export LIVEKIT_URL="${LIVEKIT_URL:-ws://127.0.0.1:7880}"
export VOICE_CONCIERGE_LIVEKIT_BIND="${VOICE_CONCIERGE_LIVEKIT_BIND:-127.0.0.1}"

mkdir -p "$HOME/logs"
cd "$APP_DIR"
PYTHON_BIN="${VOICE_CONCIERGE_LIVEKIT_SERVER_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$APP_DIR/.venv/bin/python"
  else
    PYTHON_BIN="$(command -v python3.11 || command -v python3)"
  fi
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "FATAL: Python runtime not found for local LiveKit server" >&2
  exit 1
fi

exec "$PYTHON_BIN" scripts/run_local_livekit_server.py
