#!/usr/bin/env bash
# T4 Social Monitor for NB-5 Property & Real Estate Indonesia
# Monitors: Instagram (ATR/BPN, Kanwil, Kantah), X/Twitter, Web (tarubali, JDIH)
# Cron: 0 18 * * 2,4  (02:00 WITA Tue/Thu = 18:00 UTC Mon/Wed)
# Runs on Pro via OpenClaw — before NB-5 NLM pipeline at 02:25 WITA

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/nb5_t4_monitor.log"
cd "$PROJECT_ROOT"

# Activate venv
if [ -f "apps/backend-rag/.venv/bin/activate" ]; then
    source apps/backend-rag/.venv/bin/activate
elif [ -f "apps/backend-rag/venv/bin/activate" ]; then
    source apps/backend-rag/venv/bin/activate
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] NB-5 T4 monitor starting..." >> "$LOG_FILE"

# Run T4 monitor for NB-5 Property & Real Estate
# notebook-id = d9438180-5e63-4e2a-a473-6061101f6a8d (from t4_nb5_config.json)
python -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "d9438180-5e63-4e2a-a473-6061101f6a8d" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

# Alert on failure
if [ "$EXIT_CODE" -ne 0 ]; then
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
            -d text="⚠️ NB-5 T4 monitor failed (exit $EXIT_CODE). Check nb5_t4_monitor.log" \
            > /dev/null 2>&1
    fi
fi

exit "$EXIT_CODE"
