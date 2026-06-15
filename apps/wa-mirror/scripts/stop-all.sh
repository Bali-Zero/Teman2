#!/usr/bin/env bash
# stop-all.sh — stop all wa-mirror processes.

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

echo "━━━ wa-mirror — STOP ALL ━━━"
echo ""

ALL_NAMES=$(list_accounts | awk '{print $1}' | tr '[:upper:]' '[:lower:]')

for NAME in $ALL_NAMES; do
    PIDFILE="$(pid_file "$NAME")"
    if [ -f "$PIDFILE" ]; then
        bash "$SCRIPT_DIR/stop-one.sh" "$NAME"
    fi
done

# Belt-and-suspenders: kill any leftover wa-mirror node processes
pkill -9 -f "dist/bridge/index.js" 2>/dev/null || true

echo ""
echo "✅ All wa-mirror processes stopped."
