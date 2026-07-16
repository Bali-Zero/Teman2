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

REPO="$HOME/nuzantara"
PY="/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3"
[ -x "$PY" ] || PY="python3"
LOGDIR="$HOME/.local/state/modus-autoloop"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/run.log"

# G10 single-instance: a nightly tick must never overlap itself.
LOCK="$LOGDIR/modus-autoloop.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "[$(date)] another tick holds the lock — exiting" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# G2 heartbeat: prove-of-life the organism guardian reads (scar #2 esiste≠armato).
HB_DIR="$HOME/.organism/last_seen"; mkdir -p "$HB_DIR"
_hb() {  # _hb <status> <note>
    printf '{"ts": %s, "status": "%s", "note": "%s"}\n' \
        "$(date +%s)" "$1" "${2:-}" > "$HB_DIR/modus-autoloop.json" 2>/dev/null || true
}

# Defense-in-depth: never pay-per-token Anthropic (a spawned session uses the
# CLI OAuth path, not the SDK).
unset ANTHROPIC_API_KEY

cd "$REPO" 2>/dev/null || { echo "[$(date)] FATAL: no repo at $REPO" >> "$LOG"; _hb error "no repo"; exit 78; }

echo "[$(date)] modus-autoloop tick (enabled=${MODUS_AUTOLOOP_ENABLED:-unset} dryrun=${MODUS_AUTOLOOP_DRYRUN:-unset-default-true})" >> "$LOG"
"$PY" scripts/modus_autoloop.py >> "$LOG" 2>&1
rc=$?
echo "[$(date)] modus-autoloop tick done rc=$rc" >> "$LOG"
[ "$rc" -eq 0 ] && _hb ok "tick rc=0" || _hb error "tick rc=$rc"
exit "$rc"
