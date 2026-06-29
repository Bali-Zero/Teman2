#!/bin/bash
# LaunchAgent-safe wrapper for the local voice LiveKit worker.
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
export VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL="${VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL:-http://127.0.0.1:7889/healthz}"
export VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL="${VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL:-http://127.0.0.1:7888/}"
export VOICE_CONCIERGE_LIVEKIT_AGENT_NAME="${VOICE_CONCIERGE_LIVEKIT_AGENT_NAME:-voice-concierge-local}"
export DO_NOT_TRACK="${DO_NOT_TRACK:-1}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

if [[ -z "${LIVEKIT_API_KEY:-}" || -z "${LIVEKIT_API_SECRET:-}" ]]; then
  echo "FATAL: LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$HOME/logs"
cd "$APP_DIR"
PYTHON_BIN="${VOICE_CONCIERGE_LIVEKIT_WORKER_PYTHON:-$APP_DIR/.venv-livekit-worker/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "FATAL: worker Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" scripts/local_livekit_voice_worker.py start
