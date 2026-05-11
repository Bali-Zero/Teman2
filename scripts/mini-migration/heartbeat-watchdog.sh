#!/bin/bash
# scripts/mini-migration/heartbeat-watchdog.sh
#
# Daily watchdog: checks that every job in config/job-ownership.yaml with
# owner=mini has emitted a heartbeat file in ~/heartbeat/<label>.ts within
# the expected window. Telegram alert for missing heartbeats.
#
# Heartbeat protocol: each migrated cron job, at the END of its run,
# touches ~/heartbeat/<label>.ts and writes "exit_code:<n>\nfinished_at:<iso>".
# (The idempotent-runner.sh wrapper does this automatically when it wraps
# a job; standalone scripts must implement it themselves.)
#
# Cron: Mini, daily 09:00 WITA via com.nuzantara.heartbeat-watchdog.daily.plist
#
# Expected windows (max age before alert):
# - hourly  => 90 minutes
# - daily   => 26 hours
# - weekly  => 8 days
# - monthly => 33 days

set -u

REPO="${REPO:-/Users/nuzantara/Desktop/nuzantara}"
YAML="${YAML:-$HOME/agent-config/job-ownership.yaml}"
HB_DIR="$HOME/heartbeat"
LOG_FILE="$HOME/logs/heartbeat-watchdog.log"
STATE_DIR="$HOME/.agent/decisions/state"
ALERT_COOLDOWN=21600  # 6h

mkdir -p "$(dirname "$LOG_FILE")" "$HB_DIR" "$STATE_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

telegram_alert() {
  local key="$1"
  local message="$2"
  local state_file="$STATE_DIR/heartbeat-${key}.ts"
  local now last_ts
  now=$(date +%s)
  if [ -f "$state_file" ]; then
    last_ts=$(cat "$state_file" 2>/dev/null || echo "0")
    if [ $((now - last_ts)) -lt "$ALERT_COOLDOWN" ]; then
      return 0
    fi
  fi
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a; source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true; set +a
  fi
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    log "  (telegram skipped — TELEGRAM_BOT_TOKEN not in env)"
    return 0
  fi
  curl -s --max-time 8 \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
    -d "text=[heartbeat-watchdog] ${message}" >/dev/null 2>&1 || true
  echo "$now" > "$state_file"
}

log "=== heartbeat-watchdog run ==="

if [ ! -f "$YAML" ]; then
  log "WARN: $YAML missing, skip"
  exit 0
fi

# Parse YAML cheaply: find blocks where owner: mini
MINI_LABELS=$(awk '
  /^  [a-zA-Z]/ { label = $1; sub(/:$/, "", label); next }
  /^    owner: mini$/ { print label }
' "$YAML")

if [ -z "$MINI_LABELS" ]; then
  log "no jobs with owner=mini yet (Fase 0 — expected)"
  exit 0
fi

NOW=$(date +%s)
MISSING=()

while IFS= read -r label; do
  [ -z "$label" ] && continue

  hb_file="$HB_DIR/${label}.ts"
  if [ ! -f "$hb_file" ]; then
    log "MISSING heartbeat for $label (file does not exist)"
    MISSING+=("$label (no file)")
    continue
  fi

  # mtime of heartbeat file
  hb_mtime=$(stat -f %m "$hb_file" 2>/dev/null || echo 0)
  age=$((NOW - hb_mtime))

  # Expected window from label suffix
  case "$label" in
    *.hourly|*.30min|*.10min|*.5min) max_age=5400 ;;   # 90 min
    *.weekly)                         max_age=691200 ;; # 8 days
    *.monthly|*.28d-check)            max_age=2851200 ;; # 33 days
    *.daily|*.nightly|*)              max_age=93600 ;;  # 26 h
  esac

  if [ "$age" -gt "$max_age" ]; then
    age_h=$((age / 3600))
    log "STALE heartbeat for $label (age=${age_h}h, max=$((max_age / 3600))h)"
    MISSING+=("$label (${age_h}h old)")
  fi
done <<< "$MINI_LABELS"

if [ "${#MISSING[@]}" -gt 0 ]; then
  msg=$(printf "%s, " "${MISSING[@]}" | sed 's/, $//')
  telegram_alert "missing-$(date +%Y-%m-%d)" \
    "${#MISSING[@]} job heartbeat missing/stale: ${msg:0:200}"
  exit 1
fi

log "OK all $(echo "$MINI_LABELS" | wc -l | tr -d ' ') Mini-owned jobs heartbeated within window"
exit 0
