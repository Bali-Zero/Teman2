#!/usr/bin/env bash
# DB→NLM Sync — cron wrapper
# Schedule: 30 4 * * *  (04:30 WITA daily, after pg backup)
# Machine:  Air (antonellosiano@Nuzantara-9) or Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/db_nlm_sync.log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# --- Venv detection (Air=venv, Pro=.venv) ---
if [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
fi

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python not found at $PYTHON" >&2
    exit 1
fi

# --- Lock & Log ---
LOCK_FILE="$SCRIPT_DIR/../db_nlm_sync.lock"
LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/db_nlm_sync.log"
mkdir -p "$LOG_DIR"

if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] DB→NLM sync already running (PID $PID)" >> "$LOG_FILE"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

# --- Load .env ---
export PATH="$HOME/.local/bin:$PATH"

ENV_FILE="$PROJECT_ROOT/apps/backend-rag/.env"
if [ -f "$ENV_FILE" ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        [[ "$key" =~ [^A-Za-z0-9_] ]] && continue
        export "$key=$value"
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=.+$' "$ENV_FILE")
fi

# --- Notebook IDs (set these after creating notebooks) ---
export NB_OPS_ID="${NB_OPS_ID:-}"
export NB_INTEL_ID="${NB_INTEL_ID:-}"
export NB_TELEMETRY_ID="${NB_TELEMETRY_ID:-}"

# --- Run ---
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] DB→NLM sync (PID $$)" >> "$LOG_FILE"

EXIT_CODE=0
cd "$PROJECT_ROOT"
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.db_to_nlm_sync \
    --log-level INFO \
    2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] DB→NLM sync completed successfully" >> "$LOG_FILE"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "db_nlm_sync" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] DB→NLM sync exited with code $EXIT_CODE" >> "$LOG_FILE"
    # Telegram alert on failure
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="⚠️ DB→NLM Sync FAILED (exit $EXIT_CODE) on $(hostname)"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" > /dev/null 2>&1 || true
    fi
fi

exit $EXIT_CODE
