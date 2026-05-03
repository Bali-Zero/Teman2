#!/usr/bin/env bash
# nlm_shadow_run_all.sh — Stage 6 of NLM_ELEVATION_ACTIVATION.md.
#
# Nightly Shadow Graphing extraction: ask NLM for atomic claims per domain,
# validate each with DeepSeek, embed via OpenAI, upsert into Qdrant
# collection nlm_shadow_hybrid. Runs after the NB-N domain pipelines have
# completed at ~02:30-02:50 WITA.
#
# Schedule (manual install when ready for Stage 6):
#   crontab -e
#   30 3 * * 1-6 /bin/bash /Users/nuzantara/scripts/cron-runner.sh \
#       /Users/nuzantara/Desktop/nuzantara/scripts/nlm_activation/nlm_shadow_run_all.sh \
#       >> /tmp/cron-shadow-extractor.log 2>&1
#
# Env required:
#   DEEPSEEK_API_KEY     — claim validation (~$0.01 × 50 claims × 5 NB = ~$2.50/night)
#   OPENAI_API_KEY       — embedding (text-embedding-3-small, FROZEN)
#   QDRANT_URL           — default http://localhost:6333
#   QDRANT_API_KEY       — only for cloud Qdrant
#
# DO NOT enable until Stage 5 (CEP baseline) has 7+ days of measurements.
# This populates the shadow collection but no caller reads from it until
# Stage 7 (NLM_SHADOW_RETRIEVAL_ENABLED=1).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
LOG_FILE="$HOME/.openclaw/logs/nlm_shadow_extractor.log"
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

# Load secrets (DEEPSEEK_API_KEY, OPENAI_API_KEY, QDRANT_*)
# These files are user-managed and may not exist on Air — that's fine,
# the extractor itself will refuse to run without the keys.
[ -f "$HOME/.ai_keys.env" ] && set -a && source "$HOME/.ai_keys.env" && set +a
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

# Sanity check before paying for API calls
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] DEEPSEEK_API_KEY not set — skipping" >> "$LOG_FILE"
    exit 0
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] OPENAI_API_KEY not set — skipping" >> "$LOG_FILE"
    exit 0
fi

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] shadow extraction — all 5 domains" >> "$LOG_FILE"

# Run the extractor across 5 domains. The script itself handles per-domain
# isolation (one bad domain doesn't kill the others) and the 5s throttle
# between NBs.
PYTHONPATH=. "$PYTHON" scripts/nlm_shadow_extractor.py --all-domains --limit 25 >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] shadow extraction exit=$EXIT_CODE" >> "$LOG_FILE"

# ARCH-9 heartbeat so truth_dashboard can verify the cron actually ran
if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "shadow_extractor" 2>/dev/null || true
fi

# Telegram alert only on failure (success is silent — daily extractor is
# operational background)
if [ "$EXIT_CODE" -ne 0 ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    MSG="🔴 NLM Shadow extractor FAILED (exit $EXIT_CODE) — see $LOG_FILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
        -d "text=${MSG}" >/dev/null 2>&1 || true
fi

exit "$EXIT_CODE"
