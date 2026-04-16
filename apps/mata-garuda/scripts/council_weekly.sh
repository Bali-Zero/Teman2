#!/bin/bash
# Council Weekly — SYMBIOSIS Pillar 4 deliberation cron wrapper
# Invoked by ~/Library/LaunchAgents/com.matagaruda.council-weekly.plist (Sunday 10:00 WITA)
#
# VADEMECUM §11: launchd does NOT inherit PATH/HOME. Declare explicitly.

set -euo pipefail

REPO="/Users/antonellosiano/Projects/nuzantara"
MG="$REPO/apps/mata-garuda"
LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

# Load secrets (Telegram token, DeepSeek API key, etc.)
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

PY="/Users/antonellosiano/.pyenv/shims/python3"
if [ ! -x "$PY" ]; then
    PY="/usr/bin/python3"
fi

cd "$MG"
export PYTHONPATH="$MG:${PYTHONPATH:-}"

# Run council weekly cycle: auto-select topic → deliberate → Telegram report
exec "$PY" scripts/council_weekly.py \
    >> "$LOG_DIR/council-weekly.log" 2>&1
