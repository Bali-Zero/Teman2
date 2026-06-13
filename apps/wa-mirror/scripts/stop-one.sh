#!/usr/bin/env bash
# stop-one.sh — stop ONE wa-mirror process for ONE employee.

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

NAME="${1:-}"
if [ -z "$NAME" ]; then
    echo "Usage: bash stop-one.sh <name>"
    list_accounts | awk '{print "  - " $1}'
    exit 1
fi

validate_name "$NAME" > /dev/null || exit 1

PIDFILE="$(pid_file "$NAME")"

if [ ! -f "$PIDFILE" ]; then
    echo "✋ No PID file for $NAME — already stopped"
    exit 0
fi

PID=$(cat "$PIDFILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "▸ Killing $NAME PID $PID..."
    kill -TERM "$PID" 2>/dev/null || true
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi
    echo "✅ $NAME stopped"
else
    echo "✋ $NAME process already dead (PID $PID not running)"
fi

rm -f "$PIDFILE"
