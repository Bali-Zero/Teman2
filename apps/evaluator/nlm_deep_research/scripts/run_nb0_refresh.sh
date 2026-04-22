#!/usr/bin/env bash
# NB-0 Meta-NLM daily refresh — Sprint 4 Action 4 wrapper
# Schedule: 0 9 * * *  (daily 09:00 WITA, after yajna/yin-yang/hexagram have fired)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/nb0_refresh.log
#
# Requires NB0_NOTEBOOK_ID env var — sourced from ~/.zshrc.secrets.
# Without it, nb0_refresh.py refuses to run in --push mode and exits with
# a clear error message on stderr.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: no virtualenv found" >&2
    exit 1
fi

# Load secrets (contains NB0_NOTEBOOK_ID + TELEGRAM_*)
if [ -f "$HOME/.zshrc.secrets" ]; then
    set +u
    # shellcheck disable=SC1090
    source "$HOME/.zshrc.secrets"
    set -u
fi

LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/nb0_refresh.log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] NB-0 refresh" >> "$LOG_FILE"

EXIT_CODE=0
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.nb0_refresh --push \
    2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] NB-0 refresh ok" >> "$LOG_FILE"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "nb0_refresh" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] NB-0 refresh exit=$EXIT_CODE" >> "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="⚠️ NB-0 refresh FAILED (exit $EXIT_CODE) — check ~/.openclaw/logs/nb0_refresh.log"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" > /dev/null 2>&1 || true
    fi
fi

exit "$EXIT_CODE"
