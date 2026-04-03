#!/usr/bin/env bash
# NLM Pipeline Heartbeat Monitor — cron wrapper
# Schedule: 0 8 * * *   (08:00 WITA daily — digest)
#           */30 * * * * (every 30min — check)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/heartbeat_monitor.log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Detect venv (Pro uses .venv, Air uses venv)
if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: No virtualenv found" >&2
    exit 1
fi

LOG_FILE="${HOME}/.openclaw/logs/heartbeat_monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

cd "$PROJECT_ROOT"

MODE="${1:---check}"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] Heartbeat monitor ($MODE)" >>"$LOG_FILE"

PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor "$MODE" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] Heartbeat monitor ($MODE) completed" >>"$LOG_FILE"
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] Heartbeat monitor ($MODE) failed (exit $EXIT_CODE)" >>"$LOG_FILE"
fi

exit $EXIT_CODE
