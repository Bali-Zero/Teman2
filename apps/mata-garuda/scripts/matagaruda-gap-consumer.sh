#!/bin/zsh
# Mata Garuda Gap Consumer — reads nexus:gaps, dispatches agents.
# Runs every 10 minutes during 06:00-22:00 WITA.

set -e
# Mythos-P3 (2026-06-14): include ~/.local/bin so the gap_consumer's
# CLIRuntime can find the `claude` binary (it lives at ~/.local/bin/claude,
# not /opt/homebrew/bin). Under launchd's minimal PATH it was unresolved
# → every agent dispatch failed "Command not found: claude" → gaps were
# detected but never resolved.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Path-aware default: derive from THIS script's location
# (<repo>/apps/mata-garuda/scripts/). MATA_GARUDA_REPO may still override,
# but it must point at a LIVE checkout — a dead .worktrees/ path made the
# gap.consumer cron exit 1 for 62 runs (cicatrix #1 dead-worktree, 2026-06-30).
SCRIPT_DIR="${0:A:h}"
REPO="${MATA_GARUDA_REPO:-${SCRIPT_DIR:h}}"
VENV_PY="${MATA_GARUDA_VENV_PY:-$REPO/.venv/bin/python}"

if [ ! -x "$VENV_PY" ]; then
    echo "[gap_consumer] venv python not found at $VENV_PY" >&2
    exit 1
fi

# Skip outside operating window (06:00-22:00 WITA — local time)
HOUR=$(date +%H)
if [ "$HOUR" -lt 6 ] || [ "$HOUR" -ge 22 ]; then
    echo "[gap_consumer] Outside operating window ($HOUR:00) — skipping"
    exit 0
fi

cd "$REPO"
PYTHONPATH="$REPO" "$VENV_PY" -m mata_garuda.workers.gap_consumer
