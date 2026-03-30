#!/usr/bin/env bash
# Peraturan Ingestion Trigger
# Reads 'list peraturan' Google Sheet → downloads PDFs → ingests to Qdrant/KG + Drive + NLM NB-6
#
# Cron (Pro, weekly Sunday 05:30 WITA = 21:30 UTC Saturday):
#   30 21 * * 0  /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_peraturan_ingestion.sh
#
# Manual run:
#   ./scripts/run_peraturan_ingestion.sh           # production
#   ./scripts/run_peraturan_ingestion.sh --dry-run  # preview only
#   ./scripts/run_peraturan_ingestion.sh --row 5    # single row

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/peraturan_ingestion.log"
LOCK_FILE="/tmp/peraturan_ingestion.lock"

cd "$PROJECT_ROOT"

# ── PID lock (prevent overlapping runs) ──────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Already running (PID $OLD_PID). Exiting." >> "$LOG_FILE"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ── Activate virtualenv ───────────────────────────────────────────────────────
if [ -f "apps/backend-rag/.venv/bin/activate" ]; then
    source apps/backend-rag/.venv/bin/activate
elif [ -f "apps/backend-rag/venv/bin/activate" ]; then
    source apps/backend-rag/venv/bin/activate
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: no venv found" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Peraturan ingestion starting..." >> "$LOG_FILE"

# ── Run trigger ───────────────────────────────────────────────────────────────
PYTHONPATH="$PROJECT_ROOT" python -m apps.evaluator.nlm_deep_research.peraturan_ingestion_trigger \
    "$@" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

# ── Alert on failure ──────────────────────────────────────────────────────────
if [ "$EXIT_CODE" -ne 0 ]; then
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
            -d text="⚠️ Peraturan ingestion failed (exit $EXIT_CODE). Check peraturan_ingestion.log" \
            > /dev/null 2>&1
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Peraturan ingestion FAILED (exit $EXIT_CODE)" >> "$LOG_FILE"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Peraturan ingestion completed OK" >> "$LOG_FILE"
fi

exit "$EXIT_CODE"
