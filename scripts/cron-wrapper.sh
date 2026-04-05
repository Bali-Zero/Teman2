#!/usr/bin/env bash
# cron-wrapper.sh — Universal cron wrapper with retry + Telegram alerting
#
# Usage: cron-wrapper.sh <job-name> <command...>
#   e.g.: cron-wrapper.sh fly-health /bin/bash /Users/nuzantara/scripts/fly-health-check.sh
#
# Features:
#   - Retry on failure (configurable via CRON_MAX_RETRIES, default 2)
#   - Telegram alert on final failure
#   - Structured JSON log per run
#   - Timeout protection (CRON_TIMEOUT, default 300s)
#   - Lock file to prevent overlapping runs
#
# Environment (from ~/.nuzantara-secrets.env or crontab):
#   TELEGRAM_BOT_TOKEN — required for alerts
#   TELEGRAM_ADMIN_CHAT_ID — required for alerts
#   CRON_MAX_RETRIES — default 2
#   CRON_TIMEOUT — default 300 (seconds)
#   CRON_LOG_DIR — default ~/logs/cron

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
JOB_NAME="${1:?Usage: cron-wrapper.sh <job-name> <command...>}"
shift
COMMAND=("$@")

MAX_RETRIES="${CRON_MAX_RETRIES:-2}"
TIMEOUT="${CRON_TIMEOUT:-300}"
LOG_DIR="${CRON_LOG_DIR:-$HOME/logs/cron}"
LOCK_DIR="/tmp/cron-locks"
SECRETS_FILE="$HOME/.nuzantara-secrets.env"

# Load secrets if available
if [ -f "$SECRETS_FILE" ]; then
    set -a; source "$SECRETS_FILE"; set +a
fi

mkdir -p "$LOG_DIR" "$LOCK_DIR"

LOCK_FILE="$LOCK_DIR/$JOB_NAME.lock"
LOG_FILE="$LOG_DIR/$JOB_NAME.log"
JSON_LOG="$LOG_DIR/$JOB_NAME.jsonl"
HOSTNAME_SHORT=$(hostname -s)
START_TS=$(date +%s)
START_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ── Lock (skip if already running) ───────────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "$START_ISO [$JOB_NAME] SKIP — already running (pid $LOCK_PID)" >> "$LOG_FILE"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ── Telegram helper ──────────────────────────────────────────────────────────
send_telegram() {
    local msg="$1"
    local token="${TELEGRAM_BOT_TOKEN:-}"
    local chat_id="${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_OWNER_CHAT_ID:-}}"

    if [ -z "$token" ] || [ -z "$chat_id" ]; then
        echo "$START_ISO [$JOB_NAME] WARN: no Telegram credentials — alert skipped" >> "$LOG_FILE"
        return 0
    fi

    curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d chat_id="$chat_id" \
        -d parse_mode="HTML" \
        -d text="$msg" \
        > /dev/null 2>&1 || true
}

# ── Execute with retry ───────────────────────────────────────────────────────
ATTEMPT=0
EXIT_CODE=1
OUTPUT=""

while [ $ATTEMPT -le $MAX_RETRIES ]; do
    ATTEMPT=$((ATTEMPT + 1))

    OUTPUT=$(timeout "$TIMEOUT" "${COMMAND[@]}" 2>&1) && EXIT_CODE=0 || EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        break
    fi

    if [ $EXIT_CODE -eq 124 ]; then
        echo "$START_ISO [$JOB_NAME] attempt $ATTEMPT/$((MAX_RETRIES+1)) TIMEOUT after ${TIMEOUT}s" >> "$LOG_FILE"
    else
        echo "$START_ISO [$JOB_NAME] attempt $ATTEMPT/$((MAX_RETRIES+1)) FAILED (exit $EXIT_CODE)" >> "$LOG_FILE"
    fi

    if [ $ATTEMPT -le $MAX_RETRIES ]; then
        sleep $((ATTEMPT * 5))
    fi
done

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

# ── Log result ───────────────────────────────────────────────────────────────
STATUS="ok"
if [ $EXIT_CODE -ne 0 ]; then
    STATUS="failed"
fi

# Structured JSON log (one line per run)
printf '{"job":"%s","status":"%s","exit_code":%d,"attempts":%d,"duration_s":%d,"host":"%s","ts":"%s"}\n' \
    "$JOB_NAME" "$STATUS" "$EXIT_CODE" "$ATTEMPT" "$DURATION" "$HOSTNAME_SHORT" "$START_ISO" \
    >> "$JSON_LOG"

# Human-readable log (last 100 lines of output)
{
    echo "=== $START_ISO | $JOB_NAME | $STATUS | ${DURATION}s | attempts=$ATTEMPT ==="
    echo "$OUTPUT" | tail -100
    echo ""
} >> "$LOG_FILE"

# ── Alert on failure ─────────────────────────────────────────────────────────
if [ $EXIT_CODE -ne 0 ]; then
    LAST_LINES=$(echo "$OUTPUT" | tail -5 | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')
    MSG="<b>CRON FAIL</b> $HOSTNAME_SHORT
<b>Job:</b> $JOB_NAME
<b>Exit:</b> $EXIT_CODE (after $ATTEMPT attempts)
<b>Duration:</b> ${DURATION}s
<pre>$LAST_LINES</pre>"
    send_telegram "$MSG"
fi

# Rotate log if > 1MB
if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 1048576 ]; then
    mv "$LOG_FILE" "$LOG_FILE.old"
fi

exit $EXIT_CODE
