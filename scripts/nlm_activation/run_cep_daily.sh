#!/usr/bin/env bash
# run_cep_daily.sh — Stage 5 of NLM_ELEVATION_ACTIVATION.md.
#
# Daily CEP cycle: collect prod RAG answers for the 50 golden queries,
# grade them with DeepSeek Reasoner against the rubric, write a CSV
# report, and alert Telegram if hit rate <80%.
#
# Schedule (manual install when ready for Stage 5):
#   crontab -e
#   0 6 * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#       /Users/nuzantara/Desktop/nuzantara/scripts/nlm_activation/run_cep_daily.sh \
#       >> /tmp/cron-cep.log 2>&1
#
# Env required:
#   DEEPSEEK_API_KEY     — for grading (~$0.50/run, ~$15/month)
#   NUZANTARA_RAG_ENDPOINT (optional, default https://nuzantara-rag.fly.dev)
#   NUZANTARA_RAG_TOKEN  — only if endpoint requires auth
#
# DO NOT enable until Stage 4 (oracle gate) is stable for ≥7 days, OR
# explicitly run in observe-only mode in parallel with Stage 4.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
LOG_FILE="$HOME/.openclaw/logs/nlm_cep.log"
mkdir -p "$(dirname "$LOG_FILE")"

cd "$REPO_ROOT"

if [ -d apps/backend-rag/.venv ]; then
    PYTHON="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d apps/backend-rag/venv ]; then
    PYTHON="$REPO_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: no venv found in apps/backend-rag/" >&2
    exit 1
fi

DATE_STAMP=$(date +%Y-%m-%d)
ANSWERS_FILE="/tmp/cep-answers-${DATE_STAMP}.json"
REPORT_FILE="/tmp/cep-report-${DATE_STAMP}.csv"
SUMMARY_FILE="/tmp/cep-summary-${DATE_STAMP}.json"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] CEP daily $DATE_STAMP" >> "$LOG_FILE"

# Step 1: collect answers from prod endpoint
echo "$(date -u '+%H:%M:%S') Step 1/2: collecting answers from prod RAG..." >> "$LOG_FILE"
if ! PYTHONPATH=. "$PYTHON" scripts/nlm_activation/collect_cep_answers.py \
        --golden apps/evaluator/cep/golden_v20260425.json \
        --out "$ANSWERS_FILE" >> "$LOG_FILE" 2>&1; then
    echo "$(date -u '+%H:%M:%S') [FAIL] answer collection failed" >> "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="🔴 CEP daily FAILED at answer collection — see $LOG_FILE"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" >/dev/null 2>&1 || true
    fi
    exit 1
fi

# Step 2: grade with DeepSeek
echo "$(date -u '+%H:%M:%S') Step 2/2: grading with DeepSeek..." >> "$LOG_FILE"
SUMMARY_RAW=$(PYTHONPATH=. "$PYTHON" -m apps.evaluator.cep.run_cep \
    --golden apps/evaluator/cep/golden_v20260425.json \
    --answers-file "$ANSWERS_FILE" \
    --report "$REPORT_FILE" 2>>"$LOG_FILE")
EXIT_CODE=$?
echo "$SUMMARY_RAW" > "$SUMMARY_FILE"
echo "$SUMMARY_RAW" >> "$LOG_FILE"

# Parse hit_rate using python (jq may not be available everywhere)
HIT_RATE=$(echo "$SUMMARY_RAW" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('hit_rate', 0))" 2>/dev/null || echo "0")

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] CEP daily — hit_rate=$HIT_RATE exit=$EXIT_CODE" >> "$LOG_FILE"

# Telegram daily summary (always, not just on failure — operator wants trend)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    if [ "$EXIT_CODE" -eq 0 ]; then
        EMOJI="🟢"
    else
        EMOJI="🔴"
    fi
    MSG="${EMOJI} CEP $DATE_STAMP — hit_rate=$HIT_RATE — report=$REPORT_FILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
        -d "text=${MSG}" >/dev/null 2>&1 || true
fi

# Cleanup answers file (keep report + summary for trend analysis)
rm -f "$ANSWERS_FILE"

exit "$EXIT_CODE"
