#!/usr/bin/env bash
# NB-2 Immigration & Visa Pipeline — cron wrapper
# Schedule: Mon-Sat 02:10 WITA (18:10 UTC prev day)
# Cron: 10 18 * * 0-5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/logs/nb2_pipeline_$(date +%Y%m%d).log"
PID_FILE="/tmp/nz_nb2_pipeline.pid"

mkdir -p "$(dirname "$LOG_FILE")"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%H:%M:%S') [NB2] Already running (pid=$OLD_PID) — exiting" | tee -a "$LOG_FILE"
        exit 0
    fi
fi
echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

if [ -f "$HOME/.zshrc.secrets" ]; then
    set +u
    source "$HOME/.zshrc.secrets" 2>/dev/null || true
    set -u
fi

VENV="$PROJECT_ROOT/apps/backend-rag/.venv"
if [ ! -f "$VENV/bin/activate" ]; then
    VENV="$PROJECT_ROOT/apps/backend-rag/venv"
fi
source "$VENV/bin/activate"

echo "$(date '+%H:%M:%S') [NB2] Starting Immigration pipeline" | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.pipeline 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "nb2_pipeline" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [NB2] FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="🚨 NB2 Immigration pipeline FAILED (exit $EXIT_CODE) — check $LOG_FILE"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" >/dev/null 2>&1 || true
    fi
fi

echo "$(date '+%H:%M:%S') [NB2] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
