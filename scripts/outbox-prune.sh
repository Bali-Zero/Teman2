#!/bin/bash
# outbox-prune.sh — daily prune of consumed events_outbox rows older than 30 days.
#
# Phase-3 Outbox companion: replay_unconsumed leaves rows acked but not deleted
# so audit/debugging stays possible. Without pruning the table grows unbounded
# (~10k rows/day at current write volume). This script bounds retention at 30d.
#
# Schedule: ~/Library/LaunchAgents/com.nuzantara.outbox-prune.daily.plist
#   StartCalendarInterval Hour=3, Minute=15 (after fly-pg-backup at 03:00).
#
# Exit codes: 0 success (prints rows deleted), 1 prune RPC failed, 2 env missing.

set -euo pipefail

LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/outbox-prune.log"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"
}

# Source secrets.
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [ -f "$SECRETS_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
    set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
    log "ERROR: DATABASE_URL not set, exiting"
    exit 2
fi

REPO_ROOT="${HOME}/Desktop/nuzantara"
VENV="${REPO_ROOT}/apps/backend-rag/.venv/bin/python"

if [ ! -x "$VENV" ]; then
    log "ERROR: backend-rag .venv not found at $VENV"
    exit 2
fi

OLDER_THAN_DAYS="${OUTBOX_PRUNE_DAYS:-30}"

log "starting prune: older_than_days=$OLDER_THAN_DAYS"

cd "$REPO_ROOT/apps/backend-rag"

DELETED=$(PYTHONPATH=. "$VENV" -c "
import asyncio
import os
import sys
import asyncpg
from backend.services.events.outbox import prune_consumed

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], command_timeout=300)
    try:
        n = await prune_consumed(conn, older_than_days=int(os.environ.get('OUTBOX_PRUNE_DAYS', '30')))
        print(n)
    finally:
        await conn.close()

asyncio.run(main())
" 2>>"$LOG")

if [ -z "$DELETED" ]; then
    log "ERROR: prune RPC returned empty output"
    exit 1
fi

log "completed: deleted $DELETED row(s)"

# Heartbeat for the Innervation Genoma supervisor.
HEARTBEAT_DIR="${HOME}/.organism/last_seen"
mkdir -p "$HEARTBEAT_DIR"
cat > "${HEARTBEAT_DIR}/pro.outbox_prune_daily.json" <<EOF
{"ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "status": "ok", "deleted": $DELETED}
EOF

exit 0
