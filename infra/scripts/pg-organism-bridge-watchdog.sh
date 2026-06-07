#!/bin/bash
# pg-organism-bridge-watchdog.sh — verifica che il bridge sia vivo + Redis stream attivo
# Pattern secrets: source ~/.nuzantara-secrets.env (NON launchctl setenv)
# Symbiosis L3 grandfathering: polling 5min (heartbeat-based = follow-up PR)
# Test: apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py

set -uo pipefail  # NO -e: pgrep no-match exits 1
LOG=~/logs/pg-organism-bridge-watchdog.log
STATE=~/.agent/decisions/state/pg_organism_bridge_watchdog.state
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"

set -a
[ -f "$HOME/.nuzantara-secrets.env" ] && source "$HOME/.nuzantara-secrets.env"
set +a

HEARTBEAT_LIB="${ORGANISM_HEARTBEAT_LIB:-${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh}"
if [ -f "$HEARTBEAT_LIB" ]; then
  # shellcheck disable=SC1090
  source "$HEARTBEAT_LIB"
fi

ORGAN_ID="infra.pg_organism_bridge_watchdog"

record_state() {
  local status="$1"
  local note="${2:-}"
  printf 'updated_at=%s\nstatus=%s\nnote=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "$note" > "$STATE" 2>/dev/null || true
  if declare -F organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat "$ORGAN_ID" "$status" "$note"
  fi
}

send_telegram() {
  local text="$1"
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "$(date) WARN: Telegram skipped, TELEGRAM_BOT_TOKEN unset" >> "$LOG"
    return 0
  fi
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
    --data-urlencode "text=${text}" >> "$LOG" 2>&1 || true
}

record_state "starting" "pg organism bridge watchdog start"

# Step A: bridge process alive
PID=$(pgrep -f "pg-to-organism-bridge.py" | head -1 || true)
if [ -z "$PID" ]; then
  echo "$(date) ALERT: pg-organism-bridge NOT RUNNING — Symbiosis SPOF" >> "$LOG"
  record_state "error" "pg-organism-bridge not running"
  send_telegram "⚠️ pg-organism-bridge DOWN ($(date +%H:%M)) — Symbiosis SPOF"
  exit 0
fi

# Step B: Redis stream lag check (last event in 30min)
REDIS_HOST="${GARUDA_REDIS_HOST:-127.0.0.1}"
LAST_ID=$(redis-cli -h "$REDIS_HOST" XREVRANGE organism:events + - COUNT 1 2>/dev/null | head -1 || echo "")

if [ -z "$LAST_ID" ]; then
  echo "$(date) WARN: no events in organism:events stream (PID=$PID alive, stream empty)" >> "$LOG"
  record_state "warning" "pid=$PID stream empty"
  exit 0
fi

STREAM_MS=${LAST_ID%%-*}
NOW_MS=$(( $(date +%s) * 1000 ))
LAG_MS=$(( NOW_MS - STREAM_MS ))
LAG_MIN=$(( LAG_MS / 60000 ))

if [ "$LAG_MIN" -gt 30 ]; then
  echo "$(date) ALERT: bridge alive (PID=$PID) but stream lag ${LAG_MIN}min > 30min threshold" >> "$LOG"
  record_state "error" "pid=$PID stream lag ${LAG_MIN}min"
  send_telegram "⚠️ pg-organism-bridge alive but stream STALE (${LAG_MIN}min, threshold 30min)"
else
  echo "$(date) OK: PID=$PID last_event_lag=${LAG_MIN}min" >> "$LOG"
  record_state "ok" "pid=$PID lag=${LAG_MIN}min"
fi

exit 0
