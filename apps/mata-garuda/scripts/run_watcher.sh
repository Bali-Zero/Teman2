#!/bin/zsh
# run_watcher.sh — Reference script for running Regulation Watcher
#
# NOTE: The actual LaunchAgent uses ~/scripts/mata-garuda-watcher.sh
# (TCC-safe bridge) — NOT this file. This is here for manual runs.
#
# Manual usage:
#   cd ~/Desktop/mata-garuda && source .venv/bin/activate
#   ./scripts/run_watcher.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/Users/nuzantara/logs/mata-garuda-watcher.log"
HEARTBEAT_LIB="${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh"
ORGANISM_HB_STATUS="starting"
ORGANISM_HB_NOTE="watcher started"

if [ -f "$HEARTBEAT_LIB" ]; then
    # shellcheck disable=SC1090
    source "$HEARTBEAT_LIB"
    organism_heartbeat "mata_garuda.watcher_daily.pro" "$ORGANISM_HB_STATUS" "$ORGANISM_HB_NOTE"
    _organism_hb_finalize() {
        local rc=$?
        if [ "$rc" -ne 0 ]; then
            ORGANISM_HB_STATUS="error"
            ORGANISM_HB_NOTE="rc=$rc"
        elif [ "$ORGANISM_HB_STATUS" = "starting" ]; then
            ORGANISM_HB_STATUS="ok"
            ORGANISM_HB_NOTE="watcher completed"
        fi
        organism_heartbeat "mata_garuda.watcher_daily.pro" "$ORGANISM_HB_STATUS" "$ORGANISM_HB_NOTE"
    }
    trap _organism_hb_finalize EXIT
fi

echo "" >> "$LOG"
echo "=== Regulation Watcher — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

cd "$REPO_DIR"
set +e
python -m mata_garuda.cli run "Regulation Watcher" \
    "check latest regulations" \
    --lamarckian \
    >> "$LOG" 2>&1

EXIT_CODE=$?
set -e
echo "[$(date '+%H:%M:%S')] Watcher exit=$EXIT_CODE" >> "$LOG"
if [ "$EXIT_CODE" -eq 0 ]; then
    ORGANISM_HB_STATUS="ok"
    ORGANISM_HB_NOTE="watcher completed"
else
    ORGANISM_HB_STATUS="error"
    ORGANISM_HB_NOTE="rc=$EXIT_CODE"
fi
exit $EXIT_CODE
