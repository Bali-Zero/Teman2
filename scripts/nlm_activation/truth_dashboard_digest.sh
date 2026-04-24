#!/usr/bin/env bash
# truth_dashboard_digest.sh — daily honest-monitoring summary to Telegram.
#
# Runs heartbeat_monitor --truth and sends the resulting table to Telegram
# every morning. This is the operational counterpart to PR #244's
# truth_dashboard CLI: instead of relying on Antonello to ssh in and run
# the command, the digest is pushed daily so silent failures (GATEWAY_LIES,
# DEAD pipelines) become visible without manual intervention.
#
# Schedule (manual install when ready):
#   crontab -e
#   0 7 * * * /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#       /Users/nuzantara/Desktop/nuzantara/scripts/nlm_activation/truth_dashboard_digest.sh \
#       >> /tmp/cron-truth-digest.log 2>&1
#
# Safe to enable from Stage 1 onwards — it only reads, never writes.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
LOG_FILE="$HOME/.openclaw/logs/nlm_truth_digest.log"
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

DATE_STAMP=$(date '+%Y-%m-%d %H:%M WITA')

# Capture the dashboard output
TABLE=$(PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor --truth 2>&1 || true)

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') === Truth digest ===" >> "$LOG_FILE"
echo "$TABLE" >> "$LOG_FILE"

# Count the non-OK verdicts to highlight in the message header
PROBLEM_COUNT=$(echo "$TABLE" | grep -cE "GATEWAY_LIES|LOG_NO_HEARTBEAT|DEAD|DEGRADED" || true)

# Send to Telegram (only if creds set and there's something to report)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    if [ "$PROBLEM_COUNT" -gt 0 ]; then
        HEADER="⚠️ NLM truth $DATE_STAMP — $PROBLEM_COUNT problem(s)"
    else
        HEADER="✅ NLM truth $DATE_STAMP — all OK"
    fi

    # Telegram message limit is 4096 chars; keep the table compact
    BODY=$(echo "$TABLE" | head -25)
    MSG="${HEADER}"$'\n'"\`\`\`"$'\n'"${BODY}"$'\n'"\`\`\`"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
        -d "parse_mode=Markdown" \
        --data-urlencode "text=${MSG}" >/dev/null 2>&1 || true
fi

exit 0
