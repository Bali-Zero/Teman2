#!/bin/bash
# Install/reload the local LiveKit voice stack LaunchAgents on Pro/Mini.
set -euo pipefail

HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
case "$HOST" in
  Nuzantara|nuzantara|Nuzantara-2|nuzantara-2|Mini-Pro2|mini-pro2)
    HOME_DIR="/Users/nuzantara"
    ;;
  *)
    echo "FATAL: local LiveKit audio LaunchAgents are Pro/Mini only (host=$HOST)" >&2
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAUNCHAGENTS_DIR="$HOME_DIR/Library/LaunchAgents"
ENV_FILE="$HOME_DIR/.config/nuzantara/local-livekit.env"
RUNTIME_DIR="$HOME_DIR/Library/Application Support/Nuzantara/local-livekit"
RUNTIME_SCRIPTS_DIR="$RUNTIME_DIR/scripts"

SERVER_LABEL="com.nuzantara.local-livekit-server"
WORKER_LABEL="com.nuzantara.local-livekit-worker"

mkdir -p "$LAUNCHAGENTS_DIR" "$HOME_DIR/logs" "$HOME_DIR/.config/nuzantara" "$RUNTIME_SCRIPTS_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE.example" <<'EOF'
LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=replace-me-local-livekit-api-key
LIVEKIT_API_SECRET=replace-me-local-livekit-api-secret
VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL=http://127.0.0.1:7889/healthz
VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL=http://127.0.0.1:7888/
VOICE_CONCIERGE_LIVEKIT_AGENT_NAME=voice-concierge-local
VOICE_CONCIERGE_LIVEKIT_BIND=127.0.0.1
DO_NOT_TRACK=1
HF_DATASETS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
EOF
  echo "FATAL: create $ENV_FILE first; template written to $ENV_FILE.example" >&2
  exit 1
fi

install -m 755 "$SOURCE_APP_DIR/scripts/run_local_livekit_server.sh" "$RUNTIME_SCRIPTS_DIR/run_local_livekit_server.sh"
install -m 755 "$SOURCE_APP_DIR/scripts/run_local_livekit_worker.sh" "$RUNTIME_SCRIPTS_DIR/run_local_livekit_worker.sh"
install -m 755 "$SOURCE_APP_DIR/scripts/run_local_livekit_server.py" "$RUNTIME_SCRIPTS_DIR/run_local_livekit_server.py"
install -m 755 "$SOURCE_APP_DIR/scripts/local_livekit_voice_worker.py" "$RUNTIME_SCRIPTS_DIR/local_livekit_voice_worker.py"

PYTHON311="${VOICE_CONCIERGE_LIVEKIT_VENV_PYTHON:-}"
if [[ -z "$PYTHON311" ]]; then
  if [[ -x "$SOURCE_APP_DIR/.venv/bin/python" ]]; then
    PYTHON311="$SOURCE_APP_DIR/.venv/bin/python"
  else
    PYTHON311="$(command -v python3.11 || command -v python3)"
  fi
fi

if [[ -z "$PYTHON311" || ! -x "$PYTHON311" ]]; then
  echo "FATAL: Python 3 runtime not found for local LiveKit worker venv" >&2
  exit 1
fi

if [[ ! -x "$RUNTIME_DIR/.venv-livekit-worker/bin/python" ]]; then
  "$PYTHON311" -m venv "$RUNTIME_DIR/.venv-livekit-worker"
fi
"$RUNTIME_DIR/.venv-livekit-worker/bin/python" -m pip install --upgrade pip >/dev/null
"$RUNTIME_DIR/.venv-livekit-worker/bin/python" -m pip install -r "$SOURCE_APP_DIR/requirements-livekit-worker.txt" >/dev/null

install -m 644 "$SCRIPT_DIR/$SERVER_LABEL.plist" "$LAUNCHAGENTS_DIR/$SERVER_LABEL.plist"
install -m 644 "$SCRIPT_DIR/$WORKER_LABEL.plist" "$LAUNCHAGENTS_DIR/$WORKER_LABEL.plist"

launchctl bootout "gui/$(id -u)" "$LAUNCHAGENTS_DIR/$WORKER_LABEL.plist" 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$LAUNCHAGENTS_DIR/$SERVER_LABEL.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCHAGENTS_DIR/$SERVER_LABEL.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCHAGENTS_DIR/$WORKER_LABEL.plist"
launchctl kickstart -k "gui/$(id -u)/$SERVER_LABEL"
launchctl kickstart -k "gui/$(id -u)/$WORKER_LABEL"

echo "Installed $SERVER_LABEL and $WORKER_LABEL"
echo "Runtime: $RUNTIME_DIR"
echo "Health: curl -fsS http://127.0.0.1:7889/healthz"
