#!/usr/bin/env bash
# Yajña Ledger — weekly scan wrapper
# Schedule: 0 9 * * 0  (Sunday 17:00 WITA = 09:00 UTC)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/yajna_scan.log
# Output:   apps/evaluator/nlm_deep_research/yajna_metrics.jsonl (append)
#
# Invokes:
#   python -m apps.evaluator.nlm_deep_research.yajna_ledger --scan
#
# Kill switch: env YAJNA_LEDGER_DISABLED=1 → script still runs but no events are
# read/emitted. Metrics line will show offered=0/cited=0 which is distinguishable
# from a "ledger empty" case only by context.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Venv detection (Pro=.venv, Air=venv)
if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: no virtualenv found" >&2
    exit 1
fi

LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/yajna_scan.log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] Yajña scan" >> "$LOG_FILE"

EXIT_CODE=0
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.yajna_ledger --scan \
    2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] Yajña scan ok" >> "$LOG_FILE"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "yajna_scan" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] Yajña scan exit=$EXIT_CODE" >> "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="⚠️ Yajña scan FAILED (exit $EXIT_CODE) — check ~/.openclaw/logs/yajna_scan.log"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" > /dev/null 2>&1 || true
    fi
fi

exit "$EXIT_CODE"
