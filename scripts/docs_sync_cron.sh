#!/bin/bash
# DocSentinel daily cron — updates doc stats and auto-commits if changed
# Add to crontab: 17 3 * * * /path/to/nuzantara/scripts/docs_sync_cron.sh
set -e
cd "$(dirname "$0")/.."
LOG="logs/docs_sync_cron.log"
mkdir -p logs

echo "[$(date)] DocSentinel cron start" >> "$LOG"
python3 scripts/docs_sync.py >> "$LOG" 2>&1

# Auto-commit if docs changed
if ! git diff --quiet README.md CLAUDE.md docs/AI_ONBOARDING.md 2>/dev/null; then
    git add README.md CLAUDE.md docs/AI_ONBOARDING.md
    git commit --no-verify -m "docs: auto-sync stats via DocSentinel [skip ci]"
    echo "[$(date)] Auto-committed doc updates" >> "$LOG"
else
    echo "[$(date)] No changes needed" >> "$LOG"
fi
