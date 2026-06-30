#!/bin/zsh
# Mata Garuda Consumer-Lag Monitor — runs check_consumer_lag.py every 30min
# Invoked by com.matagaruda.consumer-lag.check.plist.
#
# W10 cicatrix 2026-05-22: W5 follow-up. Script + library shipped (commit
# 063945e1e) but no LaunchAgent wrapped it. Without a cron, the monitor
# is invoked only manually and the 4-6 alerts surface only when an
# operator remembers to run the script.
#
# Exit semantics:
#   0   = all groups under threshold (silent success)
#   1   = at least one group above threshold (JSON-per-line alerts → stderr →
#         launchd error log → operator visibility)
#
# We do NOT translate exit 1 → 0 here. We *want* launchd to record
# `last exit code != 0` so `launchctl print` reflects "alerts active".

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Self-locating from THIS script's path (cicatrix #1: no hardcoded HOME-fork).
REPO="${MATA_GARUDA_REPO:-${0:A:h:h}}"
VENV_PY="$REPO/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[lag-check] venv python not found at $VENV_PY" >&2
    exit 1
fi

cd "$REPO"
PYTHONPATH="$REPO" "$VENV_PY" scripts/check_consumer_lag.py
