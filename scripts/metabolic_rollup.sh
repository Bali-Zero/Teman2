#!/bin/bash
# Metabolic Rollup — SYMBIOSIS Pillar 7 daily cron wrapper
# Invoked by ~/Library/LaunchAgents/com.cell.metabolic-rollup.plist @ 23:30 WITA (Air)
#
# Organ: cell-core metabolic → produce organism_metrics.db + Telegram report
# Consume: cell_pulse_log (PG), kg_nodes/kg_edges (PG), cron JSONL, MOS, escalations
#
# VADEMECUM §11: launchd does NOT inherit PATH/HOME. Declare explicitly.

set -euo pipefail

REPO="/Users/antonellosiano/Projects/nuzantara"
CELLCORE="$REPO/packages/cell-core"
LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

# Load secrets from central env file (pattern used by other Air cron jobs).
# File ownership: 600, contains TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID,
# METABOLIC_PG_DSN.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Python via pyenv shim (Air convention: CLAUDE.md §14)
PY="/Users/antonellosiano/.pyenv/shims/python3"
if [ ! -x "$PY" ]; then
    PY="/usr/bin/python3"
fi

cd "$REPO"

export PYTHONPATH="$CELLCORE:${PYTHONPATH:-}"
export METABOLIC_DB_PATH="${METABOLIC_DB_PATH:-$HOME/.agent/decisions/organism_metrics.db}"

# Run rollup with Telegram notification
exec "$PY" scripts/metabolic_rollup.py \
    --db-path "$METABOLIC_DB_PATH" \
    --notify \
    >> "$LOG_DIR/metabolic-rollup.log" 2>&1
