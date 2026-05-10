#!/bin/bash
# scripts/mini-migration/overlap-detector.sh
#
# Daily health-check: compares launchctl-active labels on Pro vs Mini.
# Alerts via Telegram if any label is active on BOTH machines (potential
# duplicate fire).
#
# Read-only. Safe to run anytime.
# Cron: Mini, daily 09:00 WITA via com.nuzantara.overlap-detector.daily.plist
# Log:  ~/logs/overlap-detector.log

set -u

LOG_FILE="$HOME/logs/overlap-detector.log"
STATE_DIR="$HOME/.agent/decisions/state"
ALERT_KEY="overlap-detector"
ALERT_COOLDOWN=43200  # 12 hours between identical alerts

mkdir -p "$(dirname "$LOG_FILE")" "$STATE_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

telegram_alert() {
  local message="$1"
  local state_file="$STATE_DIR/${ALERT_KEY}.ts"
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
  local token="${TELEGRAM_BOT_TOKEN:-}"
  local chat="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  if [ -z "$token" ]; then
    log "  (telegram skipped — TELEGRAM_BOT_TOKEN not in env)"
    return 0
  fi
  curl -s --max-time 8 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" \
    -d "text=[overlap-detector] ${message}" >/dev/null 2>&1 || true
  echo "$now" > "$state_file"
}

log "=== overlap-detector run ==="

# Pull active labels (with PID, not the dash-prefixed inactive ones)
# from both machines. We exclude "system" prefixes (com.apple, com.google,
# homebrew.mxcl) — they're allowed to coexist.
SYSTEM_FILTER='com\.apple|com\.google|homebrew\.mxcl'

PRO_TMP=$(mktemp -t overlap-pro.XXXX)
MINI_TMP=$(mktemp -t overlap-mini.XXXX)
trap 'rm -f "$PRO_TMP" "$MINI_TMP"' EXIT

if ! ssh -o ConnectTimeout=5 -o BatchMode=yes pro \
     'launchctl list | awk "\$1 ~ /^[0-9]+\$/ {print \$3}"' \
     | grep -vE "$SYSTEM_FILTER" \
     | sort -u > "$PRO_TMP" 2>/dev/null; then
  log "WARN: cannot reach Pro via SSH, skip"
  exit 0  # not an error — Pro might be off
fi

launchctl list | awk '$1 ~ /^[0-9]+$/ {print $3}' \
  | grep -vE "$SYSTEM_FILTER" \
  | sort -u > "$MINI_TMP"

PRO_COUNT=$(wc -l < "$PRO_TMP" | tr -d ' ')
MINI_COUNT=$(wc -l < "$MINI_TMP" | tr -d ' ')
OVERLAP=$(comm -12 "$PRO_TMP" "$MINI_TMP")
OVERLAP_COUNT=$(echo "$OVERLAP" | grep -cv '^$' || echo 0)

log "Pro active: $PRO_COUNT, Mini active: $MINI_COUNT, Overlap: $OVERLAP_COUNT"

if [ "$OVERLAP_COUNT" -gt 0 ]; then
  log "OVERLAP DETECTED:"
  while IFS= read -r label; do
    [ -z "$label" ] && continue
    log "  - $label"
  done <<< "$OVERLAP"

  # Build alert message (truncated)
  ALERT_MSG=$(echo "$OVERLAP" | head -5 | tr '\n' ',' | sed 's/,$//')
  EXTRA=""
  if [ "$OVERLAP_COUNT" -gt 5 ]; then
    EXTRA=" (+$((OVERLAP_COUNT - 5)) more)"
  fi
  telegram_alert "${OVERLAP_COUNT} label active on Pro AND Mini: ${ALERT_MSG}${EXTRA}. Check job-ownership.yaml + launchctl bootout one side."
  exit 1
fi

log "OK no overlap"
exit 0
