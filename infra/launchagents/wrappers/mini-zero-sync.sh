#!/bin/bash
# mini.zero_sync — one-way mirror of canonical main into FastLabsNet/zero main (every 30 min)
# Canon: infra/launchagents/wrappers/mini-zero-sync.sh
# Live:  ~/scripts/mini-zero-sync.sh (declared pair, node=mini)
# Payload: scripts/zero_sync/zero_sync.py (README beside it). The payload writes the organ
# heartbeat itself on every outcome it reaches (ok / warning / error); this wrapper only speaks
# for the paths the payload cannot: wrong node, kill switch, payload missing, payload not started.

set -u   # unset vars crash, they do not expand empty

ORGAN_ID="mini.zero_sync"
LOG_DIR="$HOME/logs/mini-zero_sync"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# Wrong node exits VISIBLY (#10): two mirrors pushing to one zero would race.
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# Operator stop without uninstall; a disabled heartbeat keeps the healer from resurrecting it.
if [ "${MINI_ZERO_SYNC_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_ZERO_SYNC_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# launchd hands a job a minimal PATH. git, gh and npm all live outside it; the interpreter and
# the payload are absolute so the reporter does not share a failure mode with the thing it reports.
PATH="/opt/homebrew/bin:$HOME/.local/share/mise/shims:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

REPO="$HOME/nuzantara"
PAYLOAD="$REPO/scripts/zero_sync/zero_sync.py"

# One generation of size-based rotation (wc -c, not stat: the corpus also runs on Linux CI).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi

log "run start"

if [ ! -f "$PAYLOAD" ]; then
    log "payload missing at $PAYLOAD"
    heartbeat "error" "payload missing: $PAYLOAD"
    exit 0
fi

# The payload writes the heartbeat on every outcome it reaches. A run that never reached one (a
# SyntaxError on this interpreter, a failed cd, a broken heartbeat import) must not look like the last
# good run: compare the sidecar against a marker touched before the run, whatever the exit code.
MARKER="$LOG_DIR/.run-start"
touch "$MARKER"

# rc captured from the command itself, never through a pipe, errexit-immune.
OUT=""
RC=0
OUT=$(cd "$REPO" && /usr/bin/python3 "$PAYLOAD" 2>&1) || RC=$?
printf '%s\n' "$OUT" >> "$LOG"

if [ -z "$(find "$SIDECAR_DIR/$ORGAN_ID.json" -newer "$MARKER" 2>/dev/null)" ]; then
    heartbeat "error" "payload wrote no heartbeat rc=$RC"   # e.g. 2 usage, 127 no interpreter, import crash
fi

log "run done rc=$RC"
exit 0
