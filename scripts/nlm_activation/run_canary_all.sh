#!/usr/bin/env bash
# run_canary_all.sh — Stage 3 of NLM_ELEVATION_ACTIVATION.md.
#
# Iterates verify_ingestion_uuid over the 5 NB domain notebooks. Persists
# results to apps/evaluator/nlm_deep_research/freshness_monitor_state.json
# under ingestion_verifications[notebook_id]. Sentinel + oracle gate read
# this state.
#
# Schedule (manual install when ready for Stage 3):
#   crontab -e
#   30 4 * * 1-6 /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#       /Users/nuzantara/Desktop/nuzantara/scripts/nlm_activation/run_canary_all.sh \
#       >> /tmp/cron-canary.log 2>&1
#
# Prerequisites:
#   - Sprint 0/1 PRs merged (claim_extractor fix, bridge timeout, S1.2 verify_ingestion)
#   - `nlm` CLI authenticated on Pro (user-level OAuth, not Anthropic)
#   - 5min cooldown between NB queries to avoid NLM rate limit
#
# DO NOT enable this until Stage 2 (heartbeat truth) is stable for 48h.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
LOG_FILE="$HOME/.openclaw/logs/nlm_canary.log"
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

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] NLM ingestion canary — 5 domains" >> "$LOG_FILE"

# 5 NB domain UUIDs (canonical, mirrors backend nlm_notebook_registry).
# Update here if registry changes.
declare -a NBS=(
    "cff93ab0-813a-42f2-a8de-36987e724271:NB-2 Immigration"
    "933509f9-1561-403d-bd44-4a7a67a36df2:NB-3 Company"
    "d4b2eedb-9863-4a1a-81ff-a11b0b45d853:NB-4 Tax"
    "d9438180-5e63-4e2a-a473-6061101f6a8d:NB-5 Property"
    "85207af3-352f-4554-8d2a-18f42cc541ba:NB-6 Operations"
)

OK_COUNT=0
FAIL_COUNT=0

for entry in "${NBS[@]}"; do
    NB_ID="${entry%%:*}"
    NB_LABEL="${entry##*:}"
    echo "$(date -u '+%H:%M:%S') canary $NB_LABEL ($NB_ID)" >> "$LOG_FILE"

    # The canary uploads a UUID-tagged source, queries for it, cleans up.
    # Exit code 0 = status=ok, 1 = stale|error.
    if PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.freshness_monitor \
            --verify-ingestion "$NB_ID" >> "$LOG_FILE" 2>&1; then
        OK_COUNT=$((OK_COUNT + 1))
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        # Per-NB Telegram alert if creds set
        if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
            MSG="🔴 NLM canary FAIL $NB_LABEL — see $LOG_FILE"
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
                -d "text=${MSG}" >/dev/null 2>&1 || true
        fi
    fi

    # Cooldown to avoid hitting NLM rate limit (the bridge has soft limits).
    sleep 30
done

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] canaries: ok=$OK_COUNT fail=$FAIL_COUNT" >> "$LOG_FILE"

# Aggregate alert if 2+ failed
if [ "$FAIL_COUNT" -ge 2 ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    MSG="🚨 NLM canary aggregate: $FAIL_COUNT/5 NB stale — oracle gate may refuse queries"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
        -d "text=${MSG}" >/dev/null 2>&1 || true
fi

# Exit 0 even if individual NB failed — overall script succeeded by running
# all 5. Failure tracking is in the state file + Telegram. This avoids the
# sentinel marking the whole script as failing when only 1 NB had an issue.
exit 0
