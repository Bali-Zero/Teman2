#!/bin/zsh
# modus_autoloop_cron.sh — nightly wrapper for the modus autonomous loop consumer.
# Installed to ~/.nuzantara-cron/ (outside ~/Desktop, W84 TCC-safe) but is a
# byte-identical copy of THIS repo file (scar #1 HOME-fork: the installer must
# refuse to run if the live copy diverges from the tracked one).
#
# Runs scripts/modus_autoloop.py from the repo. The consumer itself enforces:
#   - MODUS_AUTOLOOP_ENABLED default OFF (does nothing unless explicitly true)
#   - MODUS_AUTOLOOP_DRYRUN default TRUE (logs 'would launch', never spawns)
#   - single-machine guard, K-cap, deferred-on-dead-gate.
set -uo pipefail

REPO="$HOME/Desktop/nuzantara"
PY="/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3"
[ -x "$PY" ] || PY="python3"
LOGDIR="$HOME/.local/state/modus-autoloop"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/run.log"

# Defense-in-depth: never pay-per-token Anthropic (a spawned session uses the
# CLI OAuth path, not the SDK).
unset ANTHROPIC_API_KEY

cd "$REPO" 2>/dev/null || { echo "[$(date)] FATAL: no repo at $REPO" >> "$LOG"; exit 78; }

echo "[$(date)] modus-autoloop tick (enabled=${MODUS_AUTOLOOP_ENABLED:-unset} dryrun=${MODUS_AUTOLOOP_DRYRUN:-unset-default-true})" >> "$LOG"
"$PY" scripts/modus_autoloop.py >> "$LOG" 2>&1
rc=$?
echo "[$(date)] modus-autoloop tick done rc=$rc" >> "$LOG"
exit "$rc"
