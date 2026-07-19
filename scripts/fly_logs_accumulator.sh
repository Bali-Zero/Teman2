#!/bin/bash
# fly_logs_accumulator.sh — follow Fly.io app logs into daily rotated local files.
#
# Runs on Pro (Nuzantara) as LaunchAgent com.nuzantara.fly-logs-accumulator
# (O0-P1, approved by Zero 2026-07-19). Fly's own log retention is tiny, so
# post-hoc forensics on cron failures (see the KG staging promotion scar,
# 2026-07-19) was impossible — this follower keeps a local trail.
#
# - Daily rotation: the follower is restarted when the date rolls over.
# - Retention: files older than 14 days are pruned (at start and each loop).
# - PII boundary (Law 2): logs never leave the Pro's local disk.
set -u

APP="${FLY_LOGS_APP:-nuzantara-rag}"
FLY_BIN="${FLY_BIN:-/opt/homebrew/bin/fly}"
LOG_DIR="${FLY_LOGS_DIR:-$HOME/logs/fly/$APP}"

mkdir -p "$LOG_DIR"

prune() {
  find "$LOG_DIR" -name '*.log' -mtime +14 -delete 2>/dev/null || true
}

prune
while true; do
  today=$(date +%F)
  "$FLY_BIN" logs --app "$APP" >> "$LOG_DIR/$today.log" 2>&1 &
  fly_pid=$!
  # Wait until the follower dies (reconnect) or the day rolls over (rotate).
  while kill -0 "$fly_pid" 2>/dev/null; do
    if [ "$(date +%F)" != "$today" ]; then
      kill "$fly_pid" 2>/dev/null
      break
    fi
    sleep 30
  done
  wait "$fly_pid" 2>/dev/null
  prune
  sleep 5
done
