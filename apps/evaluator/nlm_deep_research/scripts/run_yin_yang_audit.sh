#!/usr/bin/env bash
# Yin-Yang Audit — weekly balance check wrapper
# Schedule: 5 9 * * 0  (Sunday 17:05 WITA — 5 min after yajna_scan populates metrics)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/yin_yang_audit.log
# Depends:  yajna_metrics.jsonl (written by run_yajna_scan.sh at 17:00)
#
# Kill switch: env YIN_YANG_AUTO_DISABLED=1 → audit still runs, recs still built,
# but auto_applied=false on every recommendation (Zero must approve manually).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Venv
if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: no virtualenv found" >&2
    exit 1
fi

LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/yin_yang_audit.log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] Yin-Yang audit" >> "$LOG_FILE"

EXIT_CODE=0
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.yin_yang_audit --audit \
    2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] Yin-Yang audit ok" >> "$LOG_FILE"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "yin_yang_audit" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] Yin-Yang audit exit=$EXIT_CODE" >> "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="⚠️ Yin-Yang audit FAILED (exit $EXIT_CODE) — check ~/.openclaw/logs/yin_yang_audit.log"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" > /dev/null 2>&1 || true
    fi
fi

exit "$EXIT_CODE"
