#!/bin/bash
#
# Stop Ollama Test Instance
# Stops Ollama if it was started by ensure_ollama_ready.sh
#

if [ -f /tmp/ollama_test.pid ]; then
    PID=$(cat /tmp/ollama_test.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 Stopping Ollama test instance (PID: $PID)..."
        kill $PID
        rm /tmp/ollama_test.pid
        echo "✅ Ollama stopped"
    else
        rm /tmp/ollama_test.pid
        echo "ℹ️  Ollama test instance already stopped"
    fi
else
    echo "ℹ️  No Ollama test instance found (Ollama was already running)"
fi
