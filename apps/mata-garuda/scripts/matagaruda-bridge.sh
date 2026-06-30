#!/bin/zsh
# Mata Garuda Bridge — bidirectional Pro<->Fly nerve.
# Invoked by com.matagaruda.bridge.adaptive.plist every 60s.
#
# TCC-safe: calls venv python directly (adhoc-signed binaries bypass TCC).

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Load secrets
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
# Mythos-P3 (2026-06-14): BRIDGE_API_KEY lives in the cell-bridge-state
# env file (0600), not in .nuzantara-secrets.env — so the bridge aborted
# every 60s with "BRIDGE_API_KEY not set" and wrote 48 MB of identical
# errors. Source it here too (the wa-media-pull + intake-gate-pusher
# wrappers already source the same file).
if [ -f "$HOME/.cell-bridge-state/wa-media.env" ]; then
    set -a
    source "$HOME/.cell-bridge-state/wa-media.env"
    set +a
fi

# Self-locating: derive the app root from THIS script's path
# (<repo>/apps/mata-garuda/scripts/<this>.sh → :h:h = apps/mata-garuda).
# Avoids the hardcoded-HOME-fork drift (cicatrix #1) and the dead-.worktrees
# override (cicatrix #1 dead-worktree 2026-06-30) — a moved checkout still resolves.
REPO="${MATA_GARUDA_REPO:-${0:A:h:h}}"
VENV_PY="$REPO/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[bridge] venv python not found at $VENV_PY" >&2
    exit 1
fi

cd "$REPO"
PYTHONPATH="$REPO" "$VENV_PY" -m mata_garuda.bridge.nerve
