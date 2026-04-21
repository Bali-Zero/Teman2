#!/usr/bin/env bash
# NB-1 Daily Bundle Refresh — cron wrapper (ARCH-1 + ARCH-8)
# Schedule: daily 04:30 WITA (20:30 UTC prev day)
# Cron: 30 20 * * *
#
# Loads secrets, calls nlm_nb1_daily_refresh.py (which takes ARCH-8 snapshot
# before upload and fires Telegram alert if source count > threshold).

set -euo pipefail

PROJECT_ROOT="/Users/nuzantara/Desktop/nuzantara"
PYTHON="/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3"
SCRIPT="$PROJECT_ROOT/scripts/nlm_nb1_daily_refresh.py"

# Load secrets for Telegram alerts
source /Users/nuzantara/.zshrc.secrets 2>/dev/null || true
export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID

_send_telegram() {
    local msg="$1"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            --data-urlencode "text=${msg}" \
            > /dev/null 2>&1 || true
    fi
}

cd "$PROJECT_ROOT"

"$PYTHON" "$SCRIPT" "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    # Record heartbeat via the shared monitor helper (matches registry key used
    # by apps/evaluator/nlm_deep_research/pipeline_heartbeat_registry.json).
    cd "$PROJECT_ROOT"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "nb1_daily_refresh" 2>/dev/null || true
    # Keep the legacy breadcrumb so any consumer that still reads the old path
    # (pre-ARCH-9) does not silently regress. This is a transitional guard.
    HEARTBEAT_DIR="$HOME/.agent/decisions/state"
    mkdir -p "$HEARTBEAT_DIR"
    echo "{\"job\":\"nb1_daily_refresh\",\"ts\":$(date +%s),\"status\":\"ok\",\"host\":\"$(hostname)\"}" \
        > "$HEARTBEAT_DIR/nb1_daily_refresh.last.json"
else
    _send_telegram "❌ NB-1 daily refresh FAILED (exit ${EXIT_CODE}) — $(date '+%Y-%m-%d %H:%M WITA')"
fi

exit $EXIT_CODE
