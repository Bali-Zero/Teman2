#!/bin/bash
# NLM Deep Research Pipeline — Daily Runner
# Schedule: 01:10 WITA (17:10 UTC) Mon-Fri via OpenClaw cron
# Location: Pro (nuzantara@Nuzantara)
#
# This script is the entry point for the OpenClaw cron job.
# It activates the venv, runs the pipeline, and logs output.

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$HOME/.openclaw/logs"
LOG_FILE="$LOG_DIR/nlm-pipeline-$(date +%Y-%m-%d).log"
VENV_PATH="$PROJECT_ROOT/apps/backend-rag/.venv"

# --- Setup ---
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== NLM Pipeline Starting ==="
log "Project: $PROJECT_ROOT"
log "Python: $VENV_PATH/bin/python"

# --- Activate venv ---
if [ ! -f "$VENV_PATH/bin/python" ]; then
    log "ERROR: Virtualenv not found at $VENV_PATH"
    exit 1
fi

# --- Weekend check (skip Sat/Sun unless --force) ---
FORCE_FLAG=""
if [[ "${1:-}" == "--force" ]]; then
    FORCE_FLAG="--force"
    log "FORCE mode — weekend check bypassed"
fi

DOW=$(date +%u)  # 1=Mon, 7=Sun
if [ "$DOW" -gt 5 ] && [ -z "$FORCE_FLAG" ]; then
    log "Weekend (day $DOW) — skipping (use --force to override)"
    exit 0
fi

# --- Run pipeline ---
cd "$PROJECT_ROOT"
PYTHONPATH="$PROJECT_ROOT" "$VENV_PATH/bin/python" \
    -m apps.evaluator.nlm_deep_research.pipeline \
    --verbose $FORCE_FLAG \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" -eq 0 ]; then
    log "=== NLM Pipeline Completed Successfully ==="
else
    log "=== NLM Pipeline FAILED (exit code: $EXIT_CODE) ==="

    # Send Telegram alert on failure
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=⚠️ NLM Pipeline FAILED (exit $EXIT_CODE). Check: $LOG_FILE" \
            -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    fi
fi

# --- Cleanup old logs (keep 30 days) ---
find "$LOG_DIR" -name "nlm-pipeline-*.log" -mtime +30 -delete 2>/dev/null || true

exit "$EXIT_CODE"
