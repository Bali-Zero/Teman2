#!/bin/bash
# Genome Decay — SYMBIOSIS Pillar 5 (Sogno) cron wrapper
# Invoked by ~/Library/LaunchAgents/com.cell.genome-decay.plist (02:30 WITA)
#
# Ebbinghaus: confidence × 0.95^days_unused, min_idle=7d, threshold 0.3
# → silence (non-destructive valid_to). Scars immune (fear memory persists).
#
# VADEMECUM §11: launchd does NOT inherit PATH/HOME.

set -euo pipefail

# Machine-aware repo + python (Pro vs Air). Dirname fallback so a future
# user rename doesn't silently fail.
case "$(whoami)" in
    nuzantara)      REPO="$HOME/Desktop/nuzantara" ;;
    antonellosiano) REPO="$HOME/Projects/nuzantara" ;;
    *)
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
        ;;
esac

CELLCORE="$REPO/packages/cell-core"
LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

PY="$HOME/.pyenv/shims/python3"
if [ ! -x "$PY" ]; then
    PY="/usr/bin/python3"
fi

cd "$REPO"
export PYTHONPATH="$CELLCORE:${PYTHONPATH:-}"

exec "$PY" scripts/genome_decay_cron.py \
    >> "$LOG_DIR/genome-decay.log" 2>&1
