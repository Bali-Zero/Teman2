#!/bin/bash
# curiosity-batch.sh — SYMBIOSIS Pillar 6 weekly Telegram digest wrapper.
#
# Reads the top cell_curiosity_findings and sends Zero a weekly Telegram summary.
# Promoted into the repo (was a ~/scripts HOME-fork, superscar #1). The DB
# password that used to be exported here in cleartext (cicatrix #4) is gone:
# DATABASE_URL now comes from ~/.nuzantara-secrets.env like every other secret.
#
# Runs every Sunday 20:00 WITA (12:00 UTC) via com.nuzantara.curiosity-batch.weekly.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$REPO" in */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;; esac

LOG="$HOME/logs/curiosity-batch.log"
SCRIPT="$REPO/scripts/cron-agent-python/curiosity_batch.py"
VENV="$REPO/apps/backend-rag/.venv"
SECRETS="$HOME/.nuzantara-secrets.env"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Starting curiosity batch" >> "$LOG"

if [ -f "$SECRETS" ]; then
    set -a; source "$SECRETS"; set +a
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): WARNING secrets file not found at $SECRETS" >> "$LOG"
fi

source "$VENV/bin/activate"

# DATABASE_URL must come from the secrets file (env-only, no hardcoded password).
if [ -z "${DATABASE_URL:-}" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): FATAL DATABASE_URL not set — aborting" >> "$LOG"
    exit 1
fi

python3 "$SCRIPT" >> "$LOG" 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Curiosity batch completed" >> "$LOG"
