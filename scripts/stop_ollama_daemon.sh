#!/bin/bash
#
# Stop Ollama Daemon
#

PID_FILE="/tmp/ollama_daemon.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 Stopping Ollama daemon (PID: $PID)..."
        kill $PID
        rm "$PID_FILE"
        echo "✅ Ollama daemon stopped"
    else
        rm "$PID_FILE"
        echo "ℹ️  Ollama daemon was not running"
    fi
else
    echo "ℹ️  No Ollama daemon found"
fi
