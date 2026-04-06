#!/bin/bash
#
# Ollama Cron Window Manager
# Manages model loading during test window (1am-6am).
# Ollama serve runs via homebrew.mxcl.ollama LaunchAgent (KeepAlive=true).
# This script only verifies the API is up and pre-loads/unloads test models.
#

set -e

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
TEST_MODEL="${OLLAMA_MODEL:-qwen3.5:9b}"  # Model used by auto_test.sh
DATE=$(date "+%Y-%m-%d %H:%M:%S")

ACTION="${1:-start}"

case "$ACTION" in
    start)
        echo "[$DATE] Opening test window — checking Ollama serve..."

        # Verify LaunchAgent Ollama is responding
        for i in {1..15}; do
            if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
                echo "[$DATE] Ollama API is up"

                # Check if test model is available
                if curl -s "${OLLAMA_URL}/api/tags" | grep -q "qwen"; then
                    echo "[$DATE] Qwen model available"
                else
                    echo "[$DATE] Pulling $TEST_MODEL..."
                    ollama pull "$TEST_MODEL" || echo "[$DATE] WARN: model pull failed"
                fi

                exit 0
            fi
            sleep 2
        done

        echo "[$DATE] ERROR: Ollama API not responding after 30s"
        echo "[$DATE] Trying to restart LaunchAgent..."
        launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ollama" 2>/dev/null || true
        sleep 5

        if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
            echo "[$DATE] Ollama recovered after kickstart"
            exit 0
        fi

        echo "[$DATE] FATAL: Ollama still not responding"
        exit 1
        ;;

    stop)
        echo "[$DATE] Closing test window — unloading models to free RAM..."

        # Unload all loaded models (frees GPU/RAM but keeps serve running)
        LOADED=$(curl -s "${OLLAMA_URL}/api/ps" 2>/dev/null | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    for m in data.get('models',[]):
        print(m['name'])
except: pass
" 2>/dev/null)

        if [ -n "$LOADED" ]; then
            while IFS= read -r model; do
                echo "[$DATE] Unloading $model..."
                curl -s -X POST "${OLLAMA_URL}/api/generate" \
                    -d "{\"model\":\"$model\",\"keep_alive\":0}" > /dev/null 2>&1 || true
            done <<< "$LOADED"
            echo "[$DATE] All models unloaded — Ollama serve stays running (LaunchAgent)"
        else
            echo "[$DATE] No models loaded — nothing to unload"
        fi
        ;;

    status)
        if curl -s --max-time 2 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
            echo "[$DATE] Ollama API is responding"
            LOADED=$(curl -s "${OLLAMA_URL}/api/ps" 2>/dev/null | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    models=data.get('models',[])
    if models:
        for m in models:
            size_gb=m.get('size',0)/1e9
            print(f'  {m[\"name\"]}: {size_gb:.1f}GB')
    else:
        print('  No models loaded')
except: print('  Cannot parse /api/ps')
" 2>/dev/null)
            echo "[$DATE] Loaded models:"
            echo "$LOADED"
        else
            echo "[$DATE] Ollama API not responding"
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
