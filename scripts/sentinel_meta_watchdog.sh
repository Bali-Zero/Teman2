#!/usr/bin/env bash
# sentinel_meta_watchdog.sh — recursive watchdog for ~/scripts/nuzantara-sentinel.py.
#
# NB-A from zero-crash audit 2026-04-29 — "who watches the watcher?"
# The sentinel is the central monitor for ~58 jobs and Cell/Organism/NLM
# bridges. If sentinel crashes, hangs, or launchd silently fails to
# respawn it, no one notices. This script closes that gap.
#
# Failure modes detected:
#   1. Crash that launchd somehow didn't respawn (no PID for label)
#   2. Hang (process exists but status_json mtime stale > threshold)
#   3. Status file missing (sentinel never wrote one)
#
# Action: launchctl kickstart -k to force respawn, then alert via Telegram.
# Cooldown: 1h between restarts/alerts to avoid storm loops.
#
# Why this is NOT a new SPOF (recursion answer):
#   - This script is short-lived: stat → compare → maybe restart → exit.
#     It cannot hang. If it crashes mid-tick, the next StartInterval fires
#     a fresh process anyway.
#   - launchd is the ultimate scheduler. Its failure implies total OS
#     failure (Pro unresponsive — caught by Air-side checks and lack of
#     SSH).
#   - Mutual-watch: this watchdog's own status file (under
#     ~/.agent/decisions/state/) gets updated each tick; sentinel can be
#     extended (separate task) to alert if THAT goes stale.
#
# Run via launchd plist com.nuzantara.sentinel-meta-watchdog every 600s.
# Manual install:
#   cp launchagents/com.nuzantara.sentinel-meta-watchdog.plist \
#      ~/Library/LaunchAgents/
#   launchctl load -w ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
#
# Manual uninstall (fully reversible):
#   launchctl unload ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
#   rm ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist

set -uo pipefail

# --- Configuration ---------------------------------------------------------

SENTINEL_LABEL="com.nuzantara.sentinel"
SENTINEL_STATUS_FILE="$HOME/.agent/decisions/sentinel_status.json"
STALE_THRESHOLD_SEC=900      # 15 min = 3× sentinel cadence (5 min)
COOLDOWN_SEC=3600            # 1 h between alerts/restarts
LOG_FILE="$HOME/logs/sentinel-meta-watchdog.log"
WATCHDOG_STATE_FILE="$HOME/.agent/decisions/state/sentinel_meta_watchdog.json"
COOLDOWN_FILE="$HOME/.agent/decisions/state/sentinel_meta_watchdog.cooldown"

# Source secrets (TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_CHAT_ID).
# NEVER hardcode the bot token in the script or plist.
if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
TELEGRAM_CHAT_ID="${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-}}"

# --- Helpers ---------------------------------------------------------------

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$WATCHDOG_STATE_FILE")"

log() {
    echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*" >> "$LOG_FILE"
}

mtime_epoch() {
    # BSD stat: -f %m. Returns 0 if file missing.
    stat -f %m "$1" 2>/dev/null || echo 0
}

write_state() {
    local status="$1" age="$2" action="$3" detail="$4"
    cat > "$WATCHDOG_STATE_FILE" <<EOF
{
  "ts": $(date +%s),
  "generated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "status": "$status",
  "sentinel_status_age_s": $age,
  "stale_threshold_s": $STALE_THRESHOLD_SEC,
  "action": "$action",
  "detail": "$detail",
  "_writer": "sentinel_meta_watchdog"
}
EOF
}

cooldown_active() {
    [[ ! -f "$COOLDOWN_FILE" ]] && return 1
    local last now elapsed
    last=$(mtime_epoch "$COOLDOWN_FILE")
    now=$(date +%s)
    elapsed=$((now - last))
    (( elapsed < COOLDOWN_SEC ))
}

cooldown_set() {
    touch "$COOLDOWN_FILE"
}

tg_alert() {
    local text="$1"
    if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
        log "telegram: missing creds (token or chat_id), skipping alert"
        return 1
    fi
    curl -sS -m 10 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${text}" \
        -d "parse_mode=HTML" \
        -o /dev/null \
        || log "telegram: post failed"
}

restart_sentinel() {
    local uid
    uid=$(id -u)
    log "restart: kickstart gui/${uid}/${SENTINEL_LABEL}"
    /bin/launchctl kickstart -k "gui/${uid}/${SENTINEL_LABEL}" 2>>"$LOG_FILE" \
        || log "restart: launchctl kickstart failed (rc=$?)"
}

sentinel_pid() {
    # launchctl list <label> emits a plist-like dump including a line
    #   "PID" = 76801;
    # only when the process is currently running. Empty output → not running
    # (between ticks for an interval-based job, or crashed and not respawned).
    /bin/launchctl list "$SENTINEL_LABEL" 2>/dev/null \
        | awk -F'[="; \t]+' '/"PID"[[:space:]]*=/ {print $3; exit}' \
        || true
}

# --- Main ------------------------------------------------------------------

main() {
    local now mtime age pid
    now=$(date +%s)

    # Case A: status file missing entirely.
    if [[ ! -f "$SENTINEL_STATUS_FILE" ]]; then
        log "sentinel_status.json MISSING — sentinel never started or state wiped"
        write_state "missing" 0 "alert+restart" "sentinel_status.json absent"
        if cooldown_active; then
            log "cooldown active, not alerting/restarting"
            exit 0
        fi
        tg_alert "🚨 <b>Sentinel meta-watchdog</b> on Pro: <code>${SENTINEL_STATUS_FILE/$HOME/~}</code> MISSING. Restarting <code>${SENTINEL_LABEL}</code>. Cooldown 1h."
        restart_sentinel
        cooldown_set
        exit 0
    fi

    mtime=$(mtime_epoch "$SENTINEL_STATUS_FILE")
    age=$((now - mtime))

    # Case B: status file fresh — sentinel is alive, all good.
    if (( age <= STALE_THRESHOLD_SEC )); then
        log "OK age=${age}s threshold=${STALE_THRESHOLD_SEC}s"
        write_state "ok" "$age" "none" "fresh"
        exit 0
    fi

    # Case C: status file stale. Sentinel is hung OR launchd didn't respawn.
    log "STALE age=${age}s threshold=${STALE_THRESHOLD_SEC}s — sentinel hung or crashed"
    pid=$(sentinel_pid)
    log "sentinel pid per launchctl list: '${pid:-<none>}'"

    if cooldown_active; then
        log "cooldown active, not restarting (will retry next tick after cooldown)"
        write_state "stale" "$age" "cooldown_skip" "pid=${pid:-none}"
        exit 0
    fi

    write_state "stale" "$age" "alert+restart" "pid=${pid:-none}"
    tg_alert "🚨 <b>Sentinel meta-watchdog</b> on Pro: <code>${SENTINEL_STATUS_FILE/$HOME/~}</code> stale ${age}s (>${STALE_THRESHOLD_SEC}s). PID=${pid:-none}. Restarting <code>${SENTINEL_LABEL}</code>. Cooldown 1h."
    restart_sentinel
    cooldown_set
}

main "$@"
