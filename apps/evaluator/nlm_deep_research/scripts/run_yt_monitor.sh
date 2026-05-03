#!/usr/bin/env bash
# YouTube Channel Monitor for NLM Notebooks
# Cron: 30 */6 * * *  (every 6h at :30, offset from T4 monitor at :00)
# Runs on Pro via OpenClaw

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv
if [ -f "apps/backend-rag/.venv/bin/activate" ]; then
    source apps/backend-rag/.venv/bin/activate
elif [ -f "apps/backend-rag/venv/bin/activate" ]; then
    source apps/backend-rag/venv/bin/activate
fi

# Run monitor
python -m apps.evaluator.nlm_deep_research.yt_monitor \
    --max-age 30 \
    --threshold 0.35 \
    2>&1 | tee -a "$PROJECT_ROOT/apps/evaluator/nlm_deep_research/yt_monitor.log"

EXIT_CODE=${PIPESTATUS[0]}

# Alert on failure
if [ "$EXIT_CODE" -ne 0 ]; then
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
            -d text="⚠️ YT Monitor failed (exit $EXIT_CODE). Check yt_monitor.log" \
            > /dev/null 2>&1
    fi
fi

exit "$EXIT_CODE"
