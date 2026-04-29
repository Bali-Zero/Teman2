#!/bin/bash
# Curiosity Loop — SYMBIOSIS Pillar 6 cron wrapper
# Invoked by ~/Library/LaunchAgents/com.graph.curiosity-loop.plist (04:30 WITA)
#
# gap_detector.scan_all_domains() → prioritize → tier dispatch
# → Self-RAG grade → propose-only in kg_proposals.
# Zero approves via `kg-propose apply <id>`. No auto-apply.
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
export PYTHONPATH="$REPO/apps/graph-engine/src:$REPO/packages/cell-core:${PYTHONPATH:-}"

exec "$PY" scripts/gap_fill_autonomous.py \
    >> "$LOG_DIR/curiosity-loop.log" 2>&1
