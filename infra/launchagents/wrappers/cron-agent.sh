#!/usr/bin/env bash
# cron-agent.sh — Universal cron wrapper for all automation tiers
#
# Usage:
#   cron-agent.sh exec  <job-name> <script> [args...]   # Tier 0: run script, alert on failure
#   cron-agent.sh agent <job-name> <prompt-file>         # Tier 2: claude -p with 3-token fallback
#
# Features:
#   - Telegram alert on failure (with cooldown)
#   - 3-account Claude OAuth fallback (TOKEN_1 → TOKEN_2 → TOKEN_3)
#   - Structured logging to ~/logs/cron-agent/
#   - Timeout enforcement
#   - Lock file (prevents concurrent runs of same job)
#   - Exit code tracking for health report
#
# Environment:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — alerts (loaded from ~/.nuzantara-secrets.env)
#   CLAUDE_CODE_OAUTH_TOKEN_{1,2,3} — 3 Claude Max accounts for agent tier
#   CRON_AGENT_TIMEOUT — override default timeout (default: 300s exec, 600s agent)
#   CRON_AGENT_DRY_RUN — set to "1" to print commands without executing
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5 in --print mode can
# silently spawn its work as a background task; the CLI kills it at the print-mode ceiling
# and exits 0 with no output (incident: regulatory-watcher 2026-07-05). run_agent() below
# raises the background ceiling and the prompt appends an inline anti-background sentence,
# plus an explicit "used: tier1-<label>" provenance log line per successful attempt.

set -uo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
TIER="${1:-}"
JOB_NAME="${2:-}"
SCRIPT_OR_PROMPT="${3:-}"
shift 3 2>/dev/null || true

if [[ -z "$TIER" || -z "$JOB_NAME" || -z "$SCRIPT_OR_PROMPT" ]]; then
    echo "Usage: cron-agent.sh {exec|agent} <job-name> <script-or-prompt-file> [args...]"
    exit 1
fi

# Paths
LOG_DIR="$HOME/logs/cron-agent"
LOG_FILE="$LOG_DIR/${JOB_NAME}.log"
STATE_DIR="$HOME/.cron-agent"
LOCK_FILE="$STATE_DIR/${JOB_NAME}.lock"
STATE_FILE="$STATE_DIR/${JOB_NAME}.state.json"
COOLDOWN_FILE="$STATE_DIR/${JOB_NAME}.cooldown"
SECRETS_FILE="$HOME/.nuzantara-secrets.env"

mkdir -p "$LOG_DIR" "$STATE_DIR"

# Load secrets
[[ -f "$SECRETS_FILE" ]] && { set -a; source "$SECRETS_FILE"; set +a; }

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${TELEGRAM_OWNER_CHAT_ID:-1125336968}}"

# Timeouts
case "$TIER" in
    exec)  DEFAULT_TIMEOUT=300 ;;
    agent) DEFAULT_TIMEOUT=600 ;;
    *)     echo "Unknown tier: $TIER"; exit 1 ;;
esac
TIMEOUT="${CRON_AGENT_TIMEOUT:-$DEFAULT_TIMEOUT}"

# ── Helpers ───────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] [$JOB_NAME] $*" >> "$LOG_FILE"; }

send_telegram() {
    local msg="$1"
    # Notification gateway (post-#2263 canon promotion): tg_notify.py owns token
    # resolution + tiering + 6h dedup; this wrapper keeps its own 30-min cooldown.
    # No env-token gate: an alert must not vanish silently when env lacks the token.
    if [[ -f "$COOLDOWN_FILE" ]]; then
        local age=$(( $(date +%s) - $(stat -f%m "$COOLDOWN_FILE" 2>/dev/null || echo 0) ))
        [[ $age -lt 1800 ]] && { log "Telegram cooldown active (${age}s < 1800s)"; return; }
    fi
    local gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/Desktop/nuzantara/scripts/tg_notify.py"
    python3 "$gateway" --tier p0 --source cron-agent \
        --dedup-key "cron-agent:${JOB_NAME}:$(hostname -s)" -- "$msg" >/dev/null 2>&1 || true
    touch "$COOLDOWN_FILE"
}

save_state() {
    local status="$1" exit_code="$2" duration="$3" error="${4:-}"
    cat > "$STATE_FILE" << STATEEOF
{"job":"$JOB_NAME","tier":"$TIER","ts":$(date +%s),"status":"$status","exit_code":$exit_code,"duration_s":$duration,"error":"$(echo "$error" | head -c 200 | tr '"' "'" | tr '\n' ' ')","host":"$(hostname)"}
STATEEOF
}

acquire_lock() {
    # macOS: use shlock (PID-based lockfile). Stale detection via PID check.
    if [[ -f "$LOCK_FILE" ]]; then
        local old_pid
        old_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
        if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
            log "SKIP: lock held by PID $old_pid"
            exit 0
        fi
        # Stale lock — previous process died
        log "Removing stale lock (PID $old_pid dead)"
        rm -f "$LOCK_FILE"
    fi
    echo $$ > "$LOCK_FILE"
}

release_lock() {
    rm -f "$LOCK_FILE"
}

# ── PATH setup ────────────────────────────────────────────────────────────────
export PATH="/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/Users/nuzantara/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/Users/nuzantara"

# sonnet-5 --print + background tasks (W89 class-audit, 2026-07-11): the CLI kills
# backgrounded work after the print-mode ceiling; 30min keeps a legitimate long agent
# run alive across every job that dispatches through the agent tier below.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# ── Lock ──────────────────────────────────────────────────────────────────────
acquire_lock
trap 'release_lock' EXIT

# ── Tier: exec ────────────────────────────────────────────────────────────────

run_exec() {
    local script="$SCRIPT_OR_PROMPT"
    if [[ ! -f "$script" ]]; then
        # Try expanding ~
        script="${script/#\~/$HOME}"
    fi
    if [[ ! -f "$script" ]]; then
        log "ERROR: script not found: $SCRIPT_OR_PROMPT"
        save_state "error" 127 0 "script not found: $SCRIPT_OR_PROMPT"
        send_telegram "❌ <b>$JOB_NAME</b>: script not found: $SCRIPT_OR_PROMPT"
        exit 127
    fi

    log "START tier=exec script=$script"
    local start_ts=$(date +%s)

    if [[ "${CRON_AGENT_DRY_RUN:-}" == "1" ]]; then
        echo "[DRY RUN] Would execute: bash $script $*"
        log "DRY RUN: bash $script $*"
        save_state "dry_run" 0 0
        return 0
    fi

    local output exit_code
    output=$(timeout "$TIMEOUT" bash "$script" "$@" 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}
    local duration=$(( $(date +%s) - start_ts ))

    # Log output (last 50 lines)
    echo "$output" | tail -50 >> "$LOG_FILE"

    if [[ $exit_code -eq 0 ]]; then
        log "OK duration=${duration}s"
        save_state "ok" 0 "$duration"
    elif [[ $exit_code -eq 124 ]]; then
        log "TIMEOUT after ${TIMEOUT}s"
        save_state "timeout" 124 "$duration" "timeout after ${TIMEOUT}s"
        send_telegram "⏰ <b>$JOB_NAME</b> timeout after ${TIMEOUT}s"
    else
        local err_tail
        err_tail=$(echo "$output" | tail -3 | tr '\n' ' ' | head -c 200)
        log "FAILED exit=$exit_code err=$err_tail"
        save_state "error" "$exit_code" "$duration" "$err_tail"
        send_telegram "❌ <b>$JOB_NAME</b> failed (exit $exit_code)
${err_tail}"
    fi
    return $exit_code
}

# ── Tier: agent ───────────────────────────────────────────────────────────────

run_agent() {
    local prompt_file="$SCRIPT_OR_PROMPT"
    if [[ ! -f "$prompt_file" ]]; then
        prompt_file="${prompt_file/#\~/$HOME}"
    fi
    if [[ ! -f "$prompt_file" ]]; then
        log "ERROR: prompt file not found: $SCRIPT_OR_PROMPT"
        save_state "error" 127 0 "prompt file not found: $SCRIPT_OR_PROMPT"
        send_telegram "❌ <b>$JOB_NAME</b>: prompt file not found: $SCRIPT_OR_PROMPT"
        exit 127
    fi

    local prompt
    prompt=$(cat "$prompt_file")
    # W89 class-audit (2026-07-11): tell the model inline never to background this run —
    # a backgrounded task is killed at the print-mode ceiling, leaving no output at all.
    prompt="${prompt}

Do ALL the work inline in this turn — never spawn a background task or background agent
for this; this is a one-shot print-mode run and backgrounded work is terminated at exit,
leaving no output (W89 class-audit, regulatory-watcher incident 2026-07-05)."

    log "START tier=agent prompt_file=$prompt_file prompt_len=${#prompt}"
    local start_ts=$(date +%s)

    if [[ "${CRON_AGENT_DRY_RUN:-}" == "1" ]]; then
        echo "[DRY RUN] Would run claude -p with prompt from $prompt_file (${#prompt} chars)"
        log "DRY RUN: claude -p (${#prompt} chars)"
        save_state "dry_run" 0 0
        return 0
    fi

    # 3-token OAuth fallback chain
    local tokens=()
    local labels=()
    for i in 1 2 3; do
        local var_name="CLAUDE_CODE_OAUTH_TOKEN_${i}"
        local tok="${!var_name:-}"
        if [[ -n "$tok" ]]; then
            tokens+=("$tok")
            labels+=("token_$i")
        fi
    done
    # Legacy fallback
    if [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
        local is_dup=0
        for t in "${tokens[@]:-}"; do
            [[ "$t" == "$CLAUDE_CODE_OAUTH_TOKEN" ]] && is_dup=1
        done
        if [[ $is_dup -eq 0 ]]; then
            tokens+=("$CLAUDE_CODE_OAUTH_TOKEN")
            labels+=("token_legacy")
        fi
    fi
    # Keychain fallback (no token = use system keychain)
    tokens+=("")
    labels+=("keychain")

    local RATE_LIMIT_PATTERN="rate.limit\|too many requests\|429\|exhausted\|quota\|hit your limit\|capacity\|overloaded"
    local output="" exit_code=1

    for idx in "${!tokens[@]}"; do
        local token="${tokens[$idx]}"
        local label="${labels[$idx]}"
        log "Trying $label..."

        local env_args=()
        if [[ -n "$token" ]]; then
            env_args=(env "CLAUDE_CODE_OAUTH_TOKEN=$token")
        else
            env_args=(env -u CLAUDE_CODE_OAUTH_TOKEN)
        fi

        # --permission-mode bypassPermissions: no approval waits.
        # Note: --bare is incompatible with OAuth tokens (requires ANTHROPIC_API_KEY).
        # --model haiku: Routing A (2026-04-22) — cron automatici usano Haiku,
        # libera quota Opus per sessioni interattive. Override via CLAUDE_CRON_MODEL env var.
        # Data-driven decision: cron = 82% sessions but 0.6% output value (empirical analysis 2026-04-22).
        local cron_model="${CLAUDE_CRON_MODEL:-claude-haiku-4-5-20251001}"
        output=$("${env_args[@]}" timeout "$TIMEOUT" claude -p --model "$cron_model" --permission-mode bypassPermissions "$prompt" 2>&1) && exit_code=0 || exit_code=$?

        # Check if rate limited (explicit error message)
        if [[ $exit_code -ne 0 ]] && echo "$output" | grep -qi "$RATE_LIMIT_PATTERN"; then
            log "$label: rate limited (explicit), trying next"
            continue
        fi

        # Check if token is silently exhausted (empty output, any exit code).
        # Claude CLI with exhausted Max-plan token returns empty output with exit 0 or 143.
        # Real errors have messages; real success has non-empty output.
        local output_trimmed="${output//[[:space:]]/}"
        if [[ -z "$output_trimmed" ]] && [[ $exit_code -ne 124 ]]; then
            log "$label: empty output (likely quota/rate issue), trying next"
            continue
        fi

        # Success or non-empty error output — stop trying
        break
    done

    local duration=$(( $(date +%s) - start_ts ))

    # Log output (last 80 lines)
    echo "$output" | tail -80 >> "$LOG_FILE"

    if [[ $exit_code -eq 0 ]]; then
        log "OK duration=${duration}s label=${labels[$idx]}"
        # Explicit tier-provenance line (W89 class-audit, 2026-07-11): which of the
        # 4 fallback slots (token_1/2/3/legacy/keychain) actually answered.
        log "[cron-agent] used: tier2-claude-${labels[$idx]} (exit=0)"
        save_state "ok" 0 "$duration"
    elif [[ $exit_code -eq 124 ]]; then
        log "TIMEOUT all tokens exhausted after ${TIMEOUT}s"
        save_state "timeout" 124 "$duration" "all tokens exhausted, timeout"
        send_telegram "⏰ <b>$JOB_NAME</b> agent timeout (all 3 tokens tried)"
    else
        local err_tail
        err_tail=$(echo "$output" | tail -3 | tr '\n' ' ' | head -c 200)
        log "FAILED exit=$exit_code label=${labels[$idx]:-?} err=$err_tail"
        save_state "error" "$exit_code" "$duration" "$err_tail"
        send_telegram "❌ <b>$JOB_NAME</b> agent failed (exit $exit_code, last token: ${labels[$idx]:-?})
${err_tail}"
    fi
    return $exit_code
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "$TIER" in
    exec)  run_exec "$@" ;;
    agent) run_agent ;;
    *)     echo "Unknown tier: $TIER"; exit 1 ;;
esac
