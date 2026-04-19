#!/bin/bash
# wr2-hardening-chain.sh — runs missed_runs + token_watchdog + quota every 6h.
#
# Each CLI already logs JSON to stdout and exits 0 on success; this script
# invokes them in sequence, aggregates exit codes, and returns the max so
# launchd can detect overall failure.
#
# Run from LaunchAgent every 6h (StartInterval 21600).

set -uo pipefail

WRAPPER="${WR2_WRAPPER:-$HOME/Desktop/nuzantara/scripts/wr2-cron-wrapper.sh}"
LOG_DIR="${WR2_LOG_DIR:-$HOME/.openclaw/workspace/logs/war-room-v2}"
mkdir -p "$LOG_DIR"

MAX_EXIT=0

for MOD in \
    backend.services.hardening.missed_runs_cli \
    backend.services.hardening.token_watchdog_cli \
    backend.services.hardening.quota_cli
do
    SHORT="${MOD##*.}"
    LOG="$LOG_DIR/hardening-$SHORT.log"
    echo "[$(date -Iseconds)] ▶ $MOD" >> "$LOG"
    "$WRAPPER" "$MOD" >> "$LOG" 2>&1
    EC=$?
    echo "[$(date -Iseconds)] ◀ $MOD exit=$EC" >> "$LOG"
    if (( EC > MAX_EXIT )); then
        MAX_EXIT=$EC
    fi
done

exit "$MAX_EXIT"
