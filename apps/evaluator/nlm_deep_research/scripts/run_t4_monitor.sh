#!/usr/bin/env bash
# T4 Social Media Monitor — cron wrapper
# Schedule: 0 */6 * * *  (every 6 hours)
# Machine:  Air (antonellosiano@Nuzantara-9)
# Log:      ~/.openclaw/logs/t4_monitor.log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Air uses venv (not .venv). Pro uses .venv — detect at runtime.
if [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
fi

LOCK_FILE="$SCRIPT_DIR/../t4.lock"
LOG_FILE="${HOME}/.openclaw/logs/t4_monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

# PID lock — prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] T4 monitor already running (PID $PID)" >> "$LOG_FILE"
        exit 0
    fi
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [WARN] Stale lock (PID $PID) — cleaning up" >> "$LOG_FILE"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

cd "$PROJECT_ROOT"

# Load env vars from backend .env (needed for OPENAI_API_KEY, ANTHROPIC_API_KEY etc.)
ENV_FILE="$PROJECT_ROOT/apps/backend-rag/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] T4 monitor (PID $$)" >> "$LOG_FILE"

PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "cff93ab0-813a-42f2-a8de-36987e724271" \
    --log-level INFO \
    2>&1 | tee -a "$LOG_FILE"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] T4 monitor completed" >> "$LOG_FILE"
