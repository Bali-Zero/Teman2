#!/usr/bin/env bash
# Pin the designated warm Ollama model after Ollama starts.
set -euo pipefail

ORGAN_ID="pro.ollama_warm_pin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/lib/heartbeat.sh" ]; then
  # shellcheck source=scripts/lib/heartbeat.sh
  source "${SCRIPT_DIR}/lib/heartbeat.sh"
elif [ -f "${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh" ]; then
  # shellcheck source=scripts/lib/heartbeat.sh
  source "${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh"
elif [ -f "${HOME}/Desktop/nuzantara-deploy/scripts/lib/heartbeat.sh" ]; then
  # shellcheck source=scripts/lib/heartbeat.sh
  source "${HOME}/Desktop/nuzantara-deploy/scripts/lib/heartbeat.sh"
else
  organism_heartbeat() { :; }
fi

_heartbeat_on_exit() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    organism_heartbeat "$ORGAN_ID" "error" "rc=$rc"
  fi
}
trap _heartbeat_on_exit EXIT

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
TOPOLOGY="${MODEL_TOPOLOGY_PATH:-/Users/nuzantara/Desktop/nuzantara/MODEL_TOPOLOGY.json}"
LOG="${OLLAMA_WARM_PIN_LOG:-${HOME}/logs/ollama-warm-pin.log}"
PYTHON_BIN="${PYTHON_BIN:-/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3}"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="/opt/homebrew/bin/python3.11"
fi

mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" >> "$LOG"; }

organism_heartbeat "$ORGAN_ID" "starting" "warm pin starting"

for _ in $(seq 1 60); do
  curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && break
  sleep 1
done

if ! curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  log "ERROR: Ollama not responding after 60s"
  organism_heartbeat "$ORGAN_ID" "error" "ollama not responding"
  exit 1
fi

MODEL=$("$PYTHON_BIN" -c "
import json, socket
t = json.load(open('$TOPOLOGY'))
h = socket.gethostname()
for v in t['nodes'].values():
    if v['hostname'] == h:
        print(v['warm_model'])
        break
")

CTX=$("$PYTHON_BIN" -c "
import json, socket
t = json.load(open('$TOPOLOGY'))
h = socket.gethostname()
for v in t['nodes'].values():
    if v['hostname'] == h:
        print(v.get('warm_ctx', 4096))
        break
")

if [ -z "$MODEL" ]; then
  log "ERROR: No warm model found for hostname $(hostname)"
  organism_heartbeat "$ORGAN_ID" "error" "warm model not found"
  exit 1
fi

EXTRA_MODELS=$("$PYTHON_BIN" -c "
import json, socket
t = json.load(open('$TOPOLOGY'))
h = socket.gethostname()
for v in t['nodes'].values():
    if v['hostname'] == h:
        for m in v.get('warm_models_extra', []) or []:
            print(m)
        break
")

_pin_model() {
  local model="$1"
  local ctx="$2"
  curl -s "$OLLAMA_URL/api/chat" \
    -d "{\"model\": \"$model\", \"keep_alive\": -1, \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}], \"stream\": false, \"think\": false, \"options\": {\"num_ctx\": $ctx, \"num_predict\": 1}}" \
    >/dev/null 2>&1
  log "Pinned $model warm (ctx=$ctx, keep_alive=-1)"
}

_pin_model "$MODEL" "$CTX"

if [ -n "$EXTRA_MODELS" ]; then
  while IFS= read -r extra; do
    [ -z "$extra" ] && continue
    _pin_model "$extra" "8192"
  done <<< "$EXTRA_MODELS"
fi

log "Warm-pin complete on $(hostname)"
organism_heartbeat "$ORGAN_ID" "ok" "model=$MODEL"
