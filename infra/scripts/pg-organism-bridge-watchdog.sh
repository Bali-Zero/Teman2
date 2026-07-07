#!/bin/bash
# pg-organism-bridge-watchdog.sh — verifica che il bridge sia vivo + Redis stream attivo
# Pattern secrets: source ~/.nuzantara-secrets.env (NON launchctl setenv)
# Symbiosis L3 grandfathering: polling 5min (heartbeat-based = follow-up PR)
# Test: apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py
#
# 2026-06-28: this watchdog was NOT LOADED for ~21 days (launchd never re-bootstrapped
# after a Pro reboot) — the guardian-of-the-guardian was dead, which is WHY the bridge
# could stop refreshing core organs for 28 days unseen. Two cures applied:
#   1. emit its OWN heartbeat every tick (so it can never go stale-invisible again —
#      the organism_stale_detector now covers it).
#   2. route alerts to the ORGANISM channel (~/.organism/alerts/) FIRST, not only to
#      the operator's Telegram. The alert must reach the organism (the brain-session
#      via the SessionStart receptor), not a human who won't look. Telegram kept as
#      a best-effort backup, not the primary path.

set -uo pipefail  # NO -e: pgrep no-match exits 1
LOG=~/logs/pg-organism-bridge-watchdog.log
STATE=~/.agent/decisions/state/pg_organism_bridge_watchdog.state
ORGANISM_DIR=~/.organism
ALERTS_DIR="$ORGANISM_DIR/alerts"
LAST_SEEN_DIR="$ORGANISM_DIR/last_seen"
SELF_ORGAN="infra.pg_organism_bridge_watchdog"
mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")" "$ALERTS_DIR" "$LAST_SEEN_DIR"

set -a
[ -f "$HOME/.nuzantara-secrets.env" ] && source "$HOME/.nuzantara-secrets.env"
set +a

# emit_self_heartbeat <status> <note> — atomic, never breaks the run.
emit_self_heartbeat() {
  local _status="${1:-ok}" _note="${2:-}"
  local _path="$LAST_SEEN_DIR/$SELF_ORGAN.json"
  local _tmp="$_path.tmp.$$"
  local _ts; _ts="$(date +%s)"
  printf '{"ts":%s,"status":"%s","organ_id":"%s","metadata":{"note":"%s"}}\n' \
    "$_ts" "$_status" "$SELF_ORGAN" "$_note" > "$_tmp" 2>/dev/null \
    && mv "$_tmp" "$_path" 2>/dev/null
  return 0
}

# organism_alert <severity> <organ> <message> — write to the organism alert channel
# the SessionStart receptor reads. Append-as-event; the detector snapshot dedups.
organism_alert() {
  local _sev="$1" _organ="$2" _msg="$3"
  local _ts; _ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local _esc="${_msg//\"/\\\"}"
  printf '{"detected_at":"%s","severity":"%s","organ_id":"%s","source":"%s","message":"%s"}\n' \
    "$_ts" "$_sev" "$_organ" "$SELF_ORGAN" "$_esc" >> "$ALERTS_DIR/bridge-watchdog.jsonl" 2>/dev/null
  return 0
}

# telegram_backup <text> — best-effort operator backup, never the primary channel.
telegram_backup() {
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || return 0
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
    -d "text=$1" >> "$LOG" 2>&1 || true
}

# Step A: bridge process alive
PID=$(pgrep -f "pg-to-organism-bridge.py" | head -1 || true)
if [ -z "$PID" ]; then
  echo "$(date) ALERT: pg-organism-bridge NOT RUNNING — Symbiosis SPOF" >> "$LOG"
  organism_alert "critical" "pro.pg_organism_bridge" "bridge process NOT RUNNING — Symbiosis SPOF (the heartbeat writer for core organs is down)"
  telegram_backup "⚠️ pg-organism-bridge DOWN ($(date +%H:%M)) — Symbiosis SPOF"
  emit_self_heartbeat "degraded" "bridge down"
  exit 0
fi

# Step B: Redis stream lag check (last event in 30min)
REDIS_HOST="${GARUDA_REDIS_HOST:-127.0.0.1}"
# requirepass live since 2026-06-29 — redis-cli reads REDISCLI_AUTH, not REDIS_PASSWORD
LAST_ID=$(REDISCLI_AUTH="${REDIS_PASSWORD:-}" redis-cli -h "$REDIS_HOST" XREVRANGE organism:events + - COUNT 1 2>/dev/null | head -1 || echo "")

if [ -z "$LAST_ID" ]; then
  echo "$(date) WARN: no events in organism:events stream (PID=$PID alive, stream empty)" >> "$LOG"
  emit_self_heartbeat "ok" "PID=$PID stream empty"
  exit 0
fi

STREAM_MS=${LAST_ID%%-*}
# NOAUTH/error text lands on stdout and would poison the arithmetic below
# (set -u killed the run exactly this way on 2026-07-03) — non-numeric = read error
case "$STREAM_MS" in
  ''|*[!0-9]*)
    echo "$(date) WARN: unreadable stream reply '$LAST_ID' (redis auth/error?)" >> "$LOG"
    emit_self_heartbeat "degraded" "stream reply unreadable: ${LAST_ID:0:40}"
    exit 0
    ;;
esac
NOW_MS=$(( $(date +%s) * 1000 ))
LAG_MS=$(( NOW_MS - STREAM_MS ))
LAG_MIN=$(( LAG_MS / 60000 ))

if [ "$LAG_MIN" -gt 30 ]; then
  echo "$(date) ALERT: bridge alive (PID=$PID) but stream lag ${LAG_MIN}min > 30min threshold" >> "$LOG"
  organism_alert "warning" "pro.pg_organism_bridge" "bridge alive (PID=$PID) but organism:events stream STALE ${LAG_MIN}min > 30min threshold"
  telegram_backup "⚠️ pg-organism-bridge alive but stream STALE (${LAG_MIN}min, threshold 30min)"
  emit_self_heartbeat "degraded" "stream lag ${LAG_MIN}min"
else
  echo "$(date) OK: PID=$PID last_event_lag=${LAG_MIN}min" >> "$LOG"
  emit_self_heartbeat "ok" "PID=$PID lag=${LAG_MIN}min"
fi

exit 0
