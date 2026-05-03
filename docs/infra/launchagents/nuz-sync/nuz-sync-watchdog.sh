#!/bin/bash
#
# nuz-sync-watchdog.sh — self-healing layer for the nuz-sync daemon
# Runs every 10 minutes via launchd.
#
# Checks 8 failure modes, attempts auto-fix, alerts Telegram on intervention.
# Safe by default: never destroys data, only removes orphan state or restarts services.
#
set -u

# ============================================================================
# Host detection
# ============================================================================
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"

case "$HOST" in
    Nuzantara|nuzantara)
        REPO="$HOME/Desktop/nuzantara"
        NODE_NAME="Pro"
        SECRETS_FILE="$HOME/.zshrc.secrets"
        ;;
    Nuzantara-9|nuzantara-9)
        REPO="$HOME/Projects/nuzantara"
        NODE_NAME="Air"
        SECRETS_FILE="$HOME/.nuzantara-secrets.env"
        ;;
    *)
        echo "FATAL: unknown host '$HOST'" >&2
        exit 1
        ;;
esac

LOG_DIR="$HOME/logs/nuz-sync"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"
SYNC_LOG="$LOG_DIR/sync.log"
HEARTBEAT_FILE="$LOG_DIR/last-run"
LOCK_FILE="$LOG_DIR/sync.lock"
SYNC_SCRIPT="$HOME/scripts/nuz-sync/nuz-sync.sh"
DAEMON_PLIST="$HOME/Library/LaunchAgents/com.nuzantara.nuz-sync.plist"
DAEMON_LABEL="com.nuzantara.nuz-sync"

HEARTBEAT_STALE=600   # 10 min
DISK_THRESHOLD_GB=2
MAX_LOG_SIZE=$((10*1024*1024))   # 10MB
INDEX_LOCK_STALE=300  # 5 min

mkdir -p "$LOG_DIR"

# ============================================================================
# Logging
# ============================================================================
wd_log() {
    local level="$1"; shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$NODE_NAME] [$level] $*" >> "$WATCHDOG_LOG"
}

# ============================================================================
# Alerts
# ============================================================================
# Track interventions in this run so we can send one consolidated message
INTERVENTIONS=()

record_intervention() {
    INTERVENTIONS+=("$1")
    wd_log ACTION "$1"
}

send_consolidated_alert() {
    if (( ${#INTERVENTIONS[@]} == 0 )); then
        return 0
    fi

    # Load secrets
    if [[ -f "$SECRETS_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$SECRETS_FILE" 2>/dev/null || true
        set +a
    fi

    local token="${TELEGRAM_BOT_TOKEN:-}"
    local chat_id="${TELEGRAM_CHAT_ID:-8764530025}"

    if [[ -z "$token" ]]; then
        wd_log WARN "no telegram token, alerts suppressed"
        return 0
    fi

    local msg="[NUZ-SYNC WATCHDOG $NODE_NAME] interventions:"
    for i in "${INTERVENTIONS[@]}"; do
        msg+="$(printf '\n- %s' "$i")"
    done

    curl -sS -m 10 -o /dev/null \
        -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" \
        || wd_log WARN "telegram send failed"
}

# ============================================================================
# Check 1: daemon loaded in launchd
# ============================================================================
check_daemon_loaded() {
    if ! launchctl list "$DAEMON_LABEL" >/dev/null 2>&1; then
        wd_log WARN "daemon not loaded"
        if [[ -f "$DAEMON_PLIST" ]]; then
            if launchctl load "$DAEMON_PLIST" 2>/dev/null; then
                record_intervention "daemon was unloaded — reloaded from plist"
            else
                record_intervention "daemon FAILED to reload — manual intervention needed"
            fi
        else
            record_intervention "daemon plist MISSING at $DAEMON_PLIST"
        fi
        return 1
    fi
    return 0
}

# ============================================================================
# Check 2: daemon last exit status
# ============================================================================
check_daemon_exit_status() {
    local status
    status=$(launchctl list "$DAEMON_LABEL" 2>/dev/null | grep LastExitStatus | grep -oE '[0-9]+' | head -1)
    if [[ -n "$status" && "$status" != "0" ]]; then
        wd_log WARN "daemon last exit status: $status"
        # Kickstart to try again
        if launchctl kickstart -k "gui/$(id -u)/$DAEMON_LABEL" 2>/dev/null; then
            record_intervention "daemon had LastExitStatus=$status — kickstarted"
        fi
    fi
}

# ============================================================================
# Check 3: heartbeat freshness
# ============================================================================
check_heartbeat() {
    if [[ ! -f "$HEARTBEAT_FILE" ]]; then
        wd_log WARN "no heartbeat file"
        # Run daemon manually to bootstrap
        /bin/bash "$SYNC_SCRIPT" >/dev/null 2>&1 &
        record_intervention "no heartbeat — triggered manual run"
        return 1
    fi

    local last now age
    last=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    age=$((now - last))

    if (( age > HEARTBEAT_STALE )); then
        local mins=$((age / 60))
        wd_log WARN "heartbeat stale: ${mins}m"
        /bin/bash "$SYNC_SCRIPT" >/dev/null 2>&1 &
        record_intervention "heartbeat was stale (${mins}m) — triggered manual run"
        return 1
    fi
    return 0
}

# ============================================================================
# Check 4: orphan lock file
# ============================================================================
check_lock_file() {
    if [[ ! -f "$LOCK_FILE" ]]; then
        return 0
    fi

    local pid
    pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [[ -z "$pid" ]]; then
        rm -f "$LOCK_FILE"
        record_intervention "empty lock file removed"
        return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        # PID dead
        rm -f "$LOCK_FILE"
        record_intervention "orphan lock file removed (dead pid $pid)"
    fi
}

# ============================================================================
# Check 5: disk space
# ============================================================================
check_disk_space() {
    local free_bytes free_gb
    # Get free space in bytes
    free_bytes=$(df -k / | awk 'NR==2 {print $4 * 1024}')
    free_gb=$((free_bytes / 1024 / 1024 / 1024))

    if (( free_gb < DISK_THRESHOLD_GB )); then
        wd_log WARN "disk low: ${free_gb}GB free"

        local recovered_start="$free_gb"

        # Clean git temp packs (orphan files from failed gc)
        local tmp_packs
        tmp_packs=$(find "$REPO/.git/objects/pack" -name 'tmp_pack_*' 2>/dev/null)
        if [[ -n "$tmp_packs" ]]; then
            echo "$tmp_packs" | xargs rm -f 2>/dev/null || true
            record_intervention "removed orphan git tmp_pack files"
        fi

        # Brew cleanup (safe, reversible next install)
        if command -v brew >/dev/null 2>&1; then
            brew cleanup --prune=all >/dev/null 2>&1 || true
            record_intervention "ran brew cleanup"
        fi

        # Remove docker installer if present (2+ GB, never needed after install)
        if [[ -d "$HOME/Library/Application Support/com.docker.install" ]]; then
            rm -rf "$HOME/Library/Application Support/com.docker.install" 2>/dev/null || true
            record_intervention "removed stale docker installer"
        fi

        # Re-check
        free_bytes=$(df -k / | awk 'NR==2 {print $4 * 1024}')
        free_gb=$((free_bytes / 1024 / 1024 / 1024))

        if (( free_gb < DISK_THRESHOLD_GB )); then
            record_intervention "disk STILL low after cleanup: ${free_gb}GB free — MANUAL FIX NEEDED"
        else
            record_intervention "disk recovered: ${recovered_start}GB → ${free_gb}GB free"
        fi
    fi
}

# ============================================================================
# Check 6: Syncthing running
# ============================================================================
check_syncthing() {
    # Is it installed?
    if ! command -v syncthing >/dev/null 2>&1; then
        return 0  # not installed, skip silently
    fi

    # Is the brew service running?
    local status
    status=$(brew services list 2>/dev/null | awk '/^syncthing/ {print $2}')

    if [[ -z "$status" || "$status" == "none" || "$status" == "stopped" ]]; then
        wd_log WARN "syncthing not running (status=$status)"
        if brew services start syncthing >/dev/null 2>&1; then
            record_intervention "syncthing was stopped — started"
        else
            record_intervention "syncthing start FAILED"
        fi
    fi
}

# ============================================================================
# Check 7: log file too large (rotation stuck)
# ============================================================================
check_log_size() {
    if [[ ! -f "$SYNC_LOG" ]]; then
        return 0
    fi

    local size
    size=$(stat -f%z "$SYNC_LOG" 2>/dev/null || echo 0)

    if (( size > MAX_LOG_SIZE )); then
        mv "$SYNC_LOG" "$SYNC_LOG.1"
        : > "$SYNC_LOG"
        record_intervention "log rotated (was ${size} bytes)"
    fi
}

# ============================================================================
# Check 8: git index.lock orphan
# ============================================================================
check_git_index_lock() {
    local lock="$REPO/.git/index.lock"
    if [[ ! -f "$lock" ]]; then
        return 0
    fi

    local age
    age=$(( $(date +%s) - $(stat -f%m "$lock" 2>/dev/null || echo 0) ))

    if (( age > INDEX_LOCK_STALE )); then
        rm -f "$lock"
        record_intervention "removed stale .git/index.lock (${age}s old)"
    fi
}

# ============================================================================
# Main
# ============================================================================
main() {
    wd_log INFO "watchdog run start"

    check_daemon_loaded
    check_daemon_exit_status
    check_heartbeat
    check_lock_file
    check_disk_space
    check_syncthing
    check_log_size
    check_git_index_lock

    if (( ${#INTERVENTIONS[@]} > 0 )); then
        wd_log INFO "sending consolidated alert (${#INTERVENTIONS[@]} interventions)"
        send_consolidated_alert
    else
        wd_log INFO "all healthy"
    fi
}

main "$@"
