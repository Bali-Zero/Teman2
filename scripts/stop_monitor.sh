#!/bin/bash

# Stop Memory Monitor

if [ -f /tmp/memory_monitor.pid ]; then
    PID=$(cat /tmp/memory_monitor.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f /tmp/memory_monitor.pid
        echo "✅ Memory monitor stopped (PID: $PID)"
    else
        echo "⚠️  Monitor not running"
        rm -f /tmp/memory_monitor.pid
    fi
else
    echo "⚠️  PID file not found"
fi
