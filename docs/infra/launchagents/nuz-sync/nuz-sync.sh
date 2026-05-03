#!/bin/bash
#
# nuz-sync.sh — bidirectional git sync daemon for nuzantara repo
# Runs every 2 minutes via launchd on both Pro and Air.
#
# Design:
# - Fetch from origin + peer node (air from pro, pro from air)
# - Fast-forward main only if clean FF possible
# - Auto-stash noise files (state JSONs) before pull
# - Alert Telegram on divergence, push failure, stale state
# - Kill switch: touch .git/sync-pause to disable
# - Lock file prevents concurrent runs
#
# Logs: ~/logs/nuz-sync/sync.log (rotated at 1MB)
#

set -u

# ============================================================================
# Host detection and config
# ============================================================================
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"

case "$HOST" in
    Nuzantara|nuzantara)
        REPO="$HOME/Desktop/nuzantara"
        PEER_REMOTE="air"
        NODE_NAME="Pro"
        SECRETS_FILE="$HOME/.zshrc.secrets"
        ;;
    Nuzantara-9|nuzantara-9)
        REPO="$HOME/Projects/nuzantara"
        PEER_REMOTE="pro"
        NODE_NAME="Air"
        SECRETS_FILE="$HOME/.nuzantara-secrets.env"
        ;;
    *)
        echo "FATAL: unknown host '$HOST'" >&2
        exit 1
        ;;
esac

LOG_DIR="$HOME/logs/nuz-sync"
LOG_FILE="$LOG_DIR/sync.log"
LOCK_FILE="$LOG_DIR/sync.lock"
HEARTBEAT_FILE="$LOG_DIR/last-run"
MAX_LOG_SIZE=1048576  # 1MB

MANAGED_BRANCHES="main"

# Noise file patterns — auto-stashed before pull, never alerted.
# These are auto-generated state files that pollute the working tree.
NOISE_PATTERNS=(
    "apps/evaluator/nlm_deep_research/"
    "apps/evaluator/nlm_nb"
    "apps/evaluator/nlm_deep_research/t4_state.json"
    "apps/evaluator/nlm_deep_research/yt_state.json"
    "apps/evaluator/nlm_deep_research/freshness_monitor_state.json"
    "apps/evaluator/nlm_deep_research/gap_scanner_state.json"
    "shared/escalations_pro.jsonl"
    "apps/bali-intel-scraper/data/published_articles.json"
    "data/analysis/SEO_ACTION_PLAN_REAL_DATA.json"
    "apps/backend-rag/backend/app/routers/admin_team_activity.py"
)

# ============================================================================
# Logging
# ============================================================================
mkdir -p "$LOG_DIR"

log() {
    local level="$1"; shift
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$ts] [$NODE_NAME] [$level] $*" >> "$LOG_FILE"
}

rotate_log() {
    if [[ -f "$LOG_FILE" ]]; then
        local size
        size=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
        if (( size > MAX_LOG_SIZE )); then
            mv "$LOG_FILE" "$LOG_FILE.1"
            : > "$LOG_FILE"
            log INFO "log rotated (previous: $size bytes)"
        fi
    fi
}

# ============================================================================
# Telegram alerts
# ============================================================================
send_alert() {
    local msg="$1"
    local chat_id="${TELEGRAM_CHAT_ID:-8764530025}"
    local token="${TELEGRAM_BOT_TOKEN:-}"

    if [[ -z "$token" ]]; then
        log WARN "TELEGRAM_BOT_TOKEN not set, alert suppressed: $msg"
        return 0
    fi

    local full_msg="[NUZ-SYNC $NODE_NAME] $msg"
    curl -sS -m 10 -o /dev/null \
        -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d "chat_id=${chat_id}" \
        -d "text=${full_msg}" \
        -d "disable_notification=false" \
        || log WARN "telegram send failed"
}

# Alert once per hour per category to prevent spam
should_alert() {
    local category="$1"
    local marker="$LOG_DIR/.alert-${category}"
    local cooldown=3600  # 1 hour

    if [[ -f "$marker" ]]; then
        local last now age
        last=$(stat -f%m "$marker" 2>/dev/null || echo 0)
        now=$(date +%s)
        age=$((now - last))
        if (( age < cooldown )); then
            return 1
        fi
    fi
    touch "$marker"
    return 0
}

# ============================================================================
# Lock file — prevent concurrent runs
# ============================================================================
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log INFO "another instance running (pid $pid), skipping"
            exit 0
        else
            log WARN "stale lock (pid $pid), removing"
            rm -f "$LOCK_FILE"
        fi
    fi
    echo "$$" > "$LOCK_FILE"
    trap 'rm -f "$LOCK_FILE"' EXIT
}

# ============================================================================
# Git helpers
# ============================================================================
is_noise_file() {
    local file="$1"
    for pattern in "${NOISE_PATTERNS[@]}"; do
        if [[ "$file" == *"$pattern"* ]]; then
            return 0
        fi
    done
    return 1
}

# Returns 0 if working tree has only noise files (or is clean)
# Returns 1 if there are real unsaved changes
working_tree_only_noise() {
    local status_out
    status_out=$(git -C "$REPO" status --porcelain 2>/dev/null)
    if [[ -z "$status_out" ]]; then
        return 0
    fi

    while IFS= read -r line; do
        # Skip untracked files — they're not affected by pull
        if [[ "$line" == "??"* ]]; then
            continue
        fi
        # Extract file path (skip first 3 chars: XY + space)
        local file="${line:3}"
        if ! is_noise_file "$file"; then
            return 1
        fi
    done <<< "$status_out"

    return 0
}

stash_noise_files() {
    local files=()
    while IFS= read -r line; do
        if [[ "$line" == "??"* ]]; then continue; fi
        local file="${line:3}"
        if is_noise_file "$file"; then
            files+=("$file")
        fi
    done < <(git -C "$REPO" status --porcelain 2>/dev/null)

    if (( ${#files[@]} > 0 )); then
        local stash_msg
        stash_msg="nuz-sync auto-stash $(date '+%Y-%m-%d %H:%M')"
        git -C "$REPO" stash push -m "$stash_msg" -- "${files[@]}" >/dev/null 2>&1
        log INFO "stashed ${#files[@]} noise files"
    fi
}

# ============================================================================
# Main sync logic
# ============================================================================
sync_branch() {
    local branch="$1"
    local current
    current=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [[ -z "$current" ]]; then
        log WARN "could not determine current branch, skipping $branch"
        return 0
    fi
    if [[ "$current" == "HEAD" ]]; then
        log DEBUG "detached HEAD, fetch-only"
        return 0
    fi

    # Only operate if we're currently ON this branch.
    # If user is on a feature branch, we don't touch main.
    if [[ "$current" != "$branch" ]]; then
        log DEBUG "not on $branch (currently on $current), fetch-only"
        return 0
    fi

    # Check if working tree is safe for pull
    if ! working_tree_only_noise; then
        log INFO "working tree has real changes, fetch-only"
        return 0
    fi

    # Try to stash noise before pull (no-op if clean)
    stash_noise_files

    # Try fast-forward from origin first
    local origin_remote="origin"
    local peer_ref="$PEER_REMOTE/$branch"
    local origin_ref="$origin_remote/$branch"

    local local_sha origin_sha peer_sha
    local_sha=$(git -C "$REPO" rev-parse "$branch" 2>/dev/null)
    origin_sha=$(git -C "$REPO" rev-parse "$origin_ref" 2>/dev/null || echo "")
    peer_sha=$(git -C "$REPO" rev-parse "$peer_ref" 2>/dev/null || echo "")

    # Try FF to origin if origin is ahead
    if [[ -n "$origin_sha" && "$origin_sha" != "$local_sha" ]]; then
        if git -C "$REPO" merge-base --is-ancestor "$local_sha" "$origin_sha" 2>/dev/null; then
            if git -C "$REPO" merge --ff-only "$origin_ref" >/dev/null 2>&1; then
                log INFO "FF to origin/$branch ($origin_sha)"
                local_sha="$origin_sha"
            else
                log ERROR "FF to origin/$branch failed unexpectedly"
                if should_alert "ff-origin-fail"; then
                    send_alert "FF to origin/$branch failed on $branch"
                fi
            fi
        elif git -C "$REPO" merge-base --is-ancestor "$origin_sha" "$local_sha" 2>/dev/null; then
            log DEBUG "local $branch is ahead of origin — not pushing (policy: manual push)"
        else
            log WARN "diverged from origin/$branch (local=$local_sha origin=$origin_sha)"
            if should_alert "diverged-origin"; then
                local ahead behind
                ahead=$(git -C "$REPO" rev-list --count "$origin_ref..$branch" 2>/dev/null || echo ?)
                behind=$(git -C "$REPO" rev-list --count "$branch..$origin_ref" 2>/dev/null || echo ?)
                send_alert "DIVERGED from origin/$branch: $ahead ahead, $behind behind. Manual merge required."
            fi
        fi
    fi

    # Try FF to peer if peer is ahead
    if [[ -n "$peer_sha" && "$peer_sha" != "$local_sha" ]]; then
        if git -C "$REPO" merge-base --is-ancestor "$local_sha" "$peer_sha" 2>/dev/null; then
            if git -C "$REPO" merge --ff-only "$peer_ref" >/dev/null 2>&1; then
                log INFO "FF to $peer_ref ($peer_sha)"
            else
                log ERROR "FF to $peer_ref failed unexpectedly"
            fi
        fi
        # If we're ahead of peer, that's fine — peer will pull us on its tick
        # If diverged from peer but aligned with origin, origin is truth — peer will catch up
    fi
}

# ============================================================================
# Entry point
# ============================================================================
main() {
    rotate_log

    # Kill switch
    if [[ -f "$REPO/.git/sync-pause" ]]; then
        log INFO "kill switch active (.git/sync-pause), exiting"
        date +%s > "$HEARTBEAT_FILE"
        exit 0
    fi

    acquire_lock

    # Load Telegram token
    if [[ -f "$SECRETS_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$SECRETS_FILE" 2>/dev/null || true
        set +a
    fi

    if [[ ! -d "$REPO/.git" ]]; then
        log ERROR "repo not found at $REPO"
        exit 1
    fi

    # Fetch all remotes (quiet, don't fail the whole run on one timeout)
    local fetch_start
    fetch_start=$(date +%s)
    git -C "$REPO" fetch origin --quiet 2>/dev/null || log WARN "fetch origin failed"
    # Peer fetch gets a timeout wrapper since peer may be offline/LAN-slow
    ( timeout 15 git -C "$REPO" fetch "$PEER_REMOTE" --quiet 2>/dev/null ) || log DEBUG "fetch $PEER_REMOTE failed or timed out"
    local fetch_dur=$(($(date +%s) - fetch_start))
    log DEBUG "fetch completed in ${fetch_dur}s"

    # Sync each managed branch
    for branch in $MANAGED_BRANCHES; do
        sync_branch "$branch"
    done

    # Heartbeat
    date +%s > "$HEARTBEAT_FILE"
}

main "$@"
