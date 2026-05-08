#!/usr/bin/env bash
# supervisor_liveness_watchdog.sh — detects "live but logically dead" Supervisor.
#
# P1 incident 2026-05-08 04:00 → 08:24 (4h 24min) showed that
# `KeepAlive=true` on com.nuzantara.organism.supervisor is INSUFFICIENT:
# the daemon stayed `state=running, runs=1, last exit code=(never exited)`
# while looping on FileNotFoundError every 5s for 4h 24min, because the
# inner `try/except` in daemon.py:run_once swallowed the error.
#
# Process alive ≠ supervisor functioning. The truth is in the data flow:
# decisions.jsonl growing means events are being processed; gap means dead.
#
# This watchdog runs every 600s via launchd:
#   1. Read tail of ~/logs/organism/decisions.jsonl
#   2. Compute gap between newest event ts and now
#   3. If gap > LIVENESS_THRESHOLD_S: launchctl kickstart -k Supervisor + Telegram alert
#   4. Cooldown 30min between actions to avoid storm loops
#
# Why this is not a new SPOF (recursion answer, same as sentinel_meta_watchdog.sh):
#   - Short-lived script, exits in <2s. Cannot hang.
#   - If it crashes mid-tick, next StartInterval fires a fresh process.
#   - launchd is the ultimate scheduler.
#   - Sentinel itself can extend coverage to alert if THIS watchdog's state
#     file goes stale (mutual-watch). Tracked in issue #541.
#
# Reference:
#   - cicatrix `STRUCTURAL Recurrence Pattern P0-3` (2026-05-08 P1)
#   - lesson `lessons_plist_worktree_path_trap.md`
#   - sentinel_meta_watchdog.sh (sibling pattern for sentinel.py)
#
# Manual test:
#   bash ~/scripts/supervisor_liveness_watchdog.sh
#   # Expected: SUCCESS with last event ts + gap_seconds.
#
# Forced trigger test (alert only, no respawn): set FORCE_ALERT=1.

set -u -o pipefail

# --- Config (env-overridable) ---
DECISIONS_LOG="${DECISIONS_LOG:-$HOME/logs/organism/decisions.jsonl}"
STATE_FILE="${STATE_FILE:-$HOME/.agent/decisions/state/supervisor_liveness_watchdog.json}"
LOG_FILE="${LOG_FILE:-$HOME/logs/supervisor-liveness-watchdog.log}"
LIVENESS_THRESHOLD_S="${LIVENESS_THRESHOLD_S:-7200}"  # 2h — covers the every-hour scheduled-tick + safety margin
COOLDOWN_S="${COOLDOWN_S:-1800}"                       # 30min between alerts
SUPERVISOR_LABEL="${SUPERVISOR_LABEL:-com.nuzantara.organism.supervisor}"
FORCE_ALERT="${FORCE_ALERT:-0}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

now_ts() { date +%s; }
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >>"$LOG_FILE"; }

# --- Telegram helper ---
send_telegram() {
  local msg="$1"
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local TOKEN="${TELEGRAM_BOT_TOKEN:-${CELL_TELEGRAM_BOT_TOKEN:-}}"
  local CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-1125336968}}"
  if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    log "telegram: skipped (no token/chat_id available)"
    return 0
  fi
  curl -fsS --max-time 5 -X POST \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    --data-urlencode "parse_mode=Markdown" \
    >/dev/null 2>&1 || log "telegram: send failed"
}

# --- Read state ---
read_last_action_ts() {
  if [ -f "$STATE_FILE" ]; then
    /usr/bin/jq -r '.last_action_ts // 0' "$STATE_FILE" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

write_state() {
  local action="$1"
  local gap="$2"
  cat >"$STATE_FILE" <<EOF
{
  "last_action_ts": $(now_ts),
  "last_action": "$action",
  "last_gap_seconds": $gap,
  "supervisor_label": "$SUPERVISOR_LABEL"
}
EOF
}

# --- Main check ---
NOW=$(now_ts)

if [ ! -f "$DECISIONS_LOG" ]; then
  log "ERROR: $DECISIONS_LOG missing"
  send_telegram "🚨 Supervisor watchdog: decisions.jsonl missing at \`$DECISIONS_LOG\`. Daemon never wrote anything. Investigate."
  exit 1
fi

# Get newest event timestamp
LAST_TS=$(/usr/bin/tail -n 1 "$DECISIONS_LOG" 2>/dev/null | /usr/bin/jq -r '.ts // empty' 2>/dev/null)
if [ -z "$LAST_TS" ] || [ "$LAST_TS" = "null" ]; then
  log "ERROR: cannot parse last ts from $DECISIONS_LOG"
  exit 1
fi

# bash arithmetic on float-ish ts: convert to int seconds
LAST_TS_INT=${LAST_TS%.*}
GAP=$((NOW - LAST_TS_INT))

log "check: last_event_ts=$LAST_TS_INT now=$NOW gap=${GAP}s threshold=${LIVENESS_THRESHOLD_S}s"

# Forced alert (test mode)
if [ "$FORCE_ALERT" = "1" ]; then
  log "FORCE_ALERT=1 → sending test alert"
  send_telegram "🧪 Supervisor watchdog test alert (FORCE_ALERT=1). last_gap=${GAP}s."
  write_state "test_alert" "$GAP"
  exit 0
fi

# Liveness gate
if [ "$GAP" -le "$LIVENESS_THRESHOLD_S" ]; then
  log "OK: supervisor processing events (gap ${GAP}s < ${LIVENESS_THRESHOLD_S}s)"
  write_state "ok" "$GAP"
  exit 0
fi

# Gap exceeded — check cooldown
LAST_ACTION_TS=$(read_last_action_ts)
SINCE_LAST_ACTION=$((NOW - LAST_ACTION_TS))
if [ "$SINCE_LAST_ACTION" -lt "$COOLDOWN_S" ]; then
  log "WARN: gap=${GAP}s exceeded but cooldown active (${SINCE_LAST_ACTION}s < ${COOLDOWN_S}s) — skipping action"
  exit 0
fi

# Action: kickstart supervisor + alert
log "ACTION: gap=${GAP}s > threshold ${LIVENESS_THRESHOLD_S}s — kickstart $SUPERVISOR_LABEL"

if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN=1 → would launchctl kickstart -k gui/$(id -u)/$SUPERVISOR_LABEL"
else
  launchctl kickstart -k "gui/$(id -u)/$SUPERVISOR_LABEL" 2>>"$LOG_FILE" || log "kickstart failed"
fi

GAP_HOURS=$((GAP / 3600))
GAP_MINS=$(((GAP % 3600) / 60))
send_telegram "🚨 Supervisor liveness ALERT
Label: \`$SUPERVISOR_LABEL\`
Last decision: ${GAP_HOURS}h ${GAP_MINS}min ago
Threshold: 2h
Action: \`launchctl kickstart -k\` issued
Cooldown: 30min
Investigate: \`tail ~/logs/organism/supervisor.err\`"

write_state "kickstart" "$GAP"
log "ACTION done"
