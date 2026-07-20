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
#
# Organ genes (infra/organ-conformance):
# - G2 heartbeat: organism_heartbeat every poll cycle, on start, on follower exit.
# - G5 kill switch: FLY_LOGS_ACCUMULATOR_ENABLED=false → final heartbeat
#   (note=disabled) + clean exit 0; the plist's KeepAlive.SuccessfulExit=false
#   means launchd does NOT relaunch after this intentional stop.
set -u

APP="${FLY_LOGS_APP:-nuzantara-rag}"
FLY_BIN="${FLY_BIN:-/opt/homebrew/bin/fly}"
LOG_DIR="${FLY_LOGS_DIR:-$HOME/logs/fly/$APP}"
ORGAN_ID="pro.fly_logs_accumulator"
HB="${HEARTBEAT_BIN:-$HOME/nuzantara/scripts/lib/heartbeat.sh}"

hb() {
  [ -x "$HB" ] && "$HB" "$ORGAN_ID" "$1" "${2:-}" || true
}

kill_switch_engaged() {
  [ "${FLY_LOGS_ACCUMULATOR_ENABLED:-true}" = "false" ]
}

# G5 kill switch — checked at (re)start and every loop iteration.
if kill_switch_engaged; then
  hb ok "disabled via FLY_LOGS_ACCUMULATOR_ENABLED=false — intentional stop"
  exit 0
fi

mkdir -p "$LOG_DIR"

prune() {
  find "$LOG_DIR" -name '*.log' -mtime +14 -delete 2>/dev/null || true
}

hb starting "accumulator starting (app=$APP dir=$LOG_DIR)"
prune
while true; do
  if kill_switch_engaged; then
    hb ok "disabled via FLY_LOGS_ACCUMULATOR_ENABLED=false — intentional stop"
    exit 0
  fi
  today=$(date +%F)
  "$FLY_BIN" logs --app "$APP" >> "$LOG_DIR/$today.log" 2>&1 &
  fly_pid=$!
  # Wait until the follower dies (reconnect) or the day rolls over (rotate).
  while kill -0 "$fly_pid" 2>/dev/null; do
    if [ "$(date +%F)" != "$today" ]; then
      kill "$fly_pid" 2>/dev/null
      break
    fi
    hb ok "following (pid=$fly_pid file=$today.log)"
    sleep 30
  done
  wait "$fly_pid" 2>/dev/null
  hb error "fly logs exited (day rollover or drop) — reconnecting"
  prune
  sleep 5
done
