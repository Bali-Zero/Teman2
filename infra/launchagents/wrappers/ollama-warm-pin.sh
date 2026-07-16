#!/usr/bin/env bash
# Pin the designated warm model after Ollama starts.
# Reads MODEL_TOPOLOGY.json for the correct model per hostname.
# Called by LaunchAgent com.nuzantara.ollama-warm-pin at boot.
set -euo pipefail

OLLAMA_URL="http://127.0.0.1:11434"
TOPOLOGY="/Users/nuzantara/nuzantara/MODEL_TOPOLOGY.json"
LOG="$HOME/logs/ollama-warm-pin.log"
PYTHON_BIN="${PYTHON_BIN:-/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3}"

if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3.11"
fi

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" >> "$LOG"; }

# Wait for Ollama ready (max 60s)
for i in $(seq 1 60); do
    curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1 && break
    sleep 1
done

if ! curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    log "ERROR: Ollama not responding after 60s"
    exit 1
fi

# Read warm model from topology
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
    exit 1
fi

# Read additional warm models (optional — empty if not configured)
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

# Pin a single model with keep_alive=-1 and think:false
_pin_model() {
    local model="$1"
    local ctx="$2"
    curl -s "$OLLAMA_URL/api/chat" \
        -d "{\"model\": \"$model\", \"keep_alive\": -1, \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}], \"stream\": false, \"think\": false, \"options\": {\"num_ctx\": $ctx, \"num_predict\": 1}}" \
        > /dev/null 2>&1
    log "Pinned $model warm (ctx=$ctx, keep_alive=-1)"
}

# Pin primary
_pin_model "$MODEL" "$CTX"

# Pin extras (use smaller ctx to keep memory footprint reasonable)
if [ -n "$EXTRA_MODELS" ]; then
    while IFS= read -r extra; do
        [ -z "$extra" ] && continue
        _pin_model "$extra" "8192"
    done <<< "$EXTRA_MODELS"
fi

log "Warm-pin complete on $(hostname)"
