#!/bin/bash
# mini.restore_drill — monthly proof that the newest Tigris pg_dump is restorable.
# Canon: infra/launchagents/wrappers/mini-restore-drill.sh
# Live:  ~/scripts/mini-restore-drill.sh (declared pair, node=mini)

set -u
umask 077

ORGAN_ID="mini.restore_drill"
LOG_DIR="$HOME/logs/mini-restore_drill"
LOG="$LOG_DIR/run.log"
SIDECAR_DIR="$HOME/.organism/last_seen"
LOCKDIR="/tmp/nuzantara-mini-restore_drill.lock"
REPO="$HOME/nuzantara"
PAYLOAD="$REPO/scripts/restore_drill/run_drill.sh"
GATEWAY="$REPO/scripts/tg_notify.py"
mkdir -p "$LOG_DIR" "$SIDECAR_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

heartbeat() { # $1 status, $2 note — written to a temp file and renamed, so a failed write never truncates the last verdict
    local tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$tmp" \
        && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json" \
        || { rm -f "$tmp"; return 1; }
}

notify() { # $1 tier, $2 dedup key, $3 safe message
    tier=$1
    key=$2
    message=$3
    /usr/bin/python3 "$GATEWAY" --tier "$tier" --source restore-drill \
        --dedup-key "$key" -- "$message" >> "$LOG" 2>&1
}


# Mini-only singleton: a second host would duplicate a heavy restore and its alerts.
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

if [ "${MINI_RESTORE_DRILL_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_RESTORE_DRILL_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# Atomic singleton (mkdir is one syscall; macOS has no flock). A lock is stale only when its owner
# is gone or is no longer this wrapper (a recycled PID must not make every later run skip).
# A live run is left alone and its sidecar is NOT touched: the skip is not a result.
# The owner is identified by PID + process start time + command, so a recycled PID cannot pass for it.
proc_id() { echo "$1 $(ps -p "$1" -o lstart= 2>/dev/null | tr -s ' ')"; }
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    owner=$(cat "$LOCKDIR/pid" 2>/dev/null || true)
    owner_pid=${owner%% *}
    age=$(( $(date +%s) - $(stat -f %m "$LOCKDIR" 2>/dev/null || echo 0) ))
    if [ -z "$owner" ] && [ "$age" -lt 120 ]; then
        log "lock just created by another run — skipping, sidecar untouched"
        exit 0
    fi
    if [ -n "$owner_pid" ] && kill -0 "$owner_pid" 2>/dev/null \
        && [ "$(proc_id "$owner_pid")" = "$owner" ] \
        && ps -p "$owner_pid" -o command= 2>/dev/null | grep -q "mini-restore-drill.sh"; then
        log "previous run (pid $owner_pid) still alive — skipping, sidecar untouched"
        exit 0
    fi
    log "stale lock (owner ${owner_pid:-unknown} gone) — taking it over"
    # rename is atomic: of two racers only one moves the stale lock away, the other's mkdir then loses.
    mv "$LOCKDIR" "$LOCKDIR.stale.$$" 2>/dev/null && rm -rf "$LOCKDIR.stale.$$"
    mkdir "$LOCKDIR" 2>/dev/null || { log "cannot take the lock — another run won the race"; exit 0; }
fi
proc_id $$ > "$LOCKDIR/pid"
FINISHED=0
on_exit() {
    rc=$?
    # Any exit before the verdict block (crash, signal, launchctl kill) must still leave a visible trace.
    if [ "$FINISHED" -ne 1 ]; then
        MONTH=${MONTH:-$(date +%Y-%m)}
        heartbeat "error" "wrapper exited before a verdict rc=$rc"
        notify p0 "restore-drill:${MONTH}" \
            "Monthly restore drill on Mini ended before a verdict (rc=$rc). Investigate the local private log." || true
    fi
    # Release only a lock this process still owns.
    if [ "$(cat "$LOCKDIR/pid" 2>/dev/null)" = "$(proc_id $$)" ]; then
        rm -rf "$LOCKDIR"
    fi
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi
# This job never needs a model; do not pass a paid Anthropic credential to children.
unset ANTHROPIC_API_KEY 2>/dev/null || true

if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi

log "run start"
# No start heartbeat: "running" reads dead and "ok" would paint over the last verdict (a SIGKILL or power-off
# mid-restore would then stay green for the whole 33-day window). The sidecar only ever holds a verdict.
RC=0
if [ ! -f "$PAYLOAD" ]; then
    echo "CANNOT-VERIFY: payload missing" >> "$LOG"
    RC=2
else
    /bin/bash "$PAYLOAD" >> "$LOG" 2>&1 || RC=$?
fi

MONTH=$(date +%Y-%m)
if [ "$RC" -eq 0 ] && ! heartbeat "ok" "restore and Level-5 verification passed"; then
    # A green that cannot be recorded is not a green: it becomes CANNOT-VERIFY and alerts below.
    log "heartbeat write failed after a passing drill"
    RC=2
fi
if [ "$RC" -eq 0 ]; then
    notify digest "restore-drill:${MONTH}:success" \
        "Monthly restore drill passed on Mini (restore + Level-5 verification)." || \
        log "digest notification failed or was spooled"
else
    if [ "$RC" -eq 2 ] || [ "$RC" -eq 124 ]; then
        OUTCOME="CANNOT-VERIFY"
    else
        OUTCOME="FAILED"
    fi
    heartbeat "error" "$OUTCOME rc=$RC" || log "heartbeat write failed (error verdict)"
    notify p0 "restore-drill:${MONTH}" \
        "Monthly restore drill $OUTCOME on Mini (rc=$RC). Investigate the local private log." || \
        log "p0 notification failed or was spooled"
fi

FINISHED=1
log "run done rc=$RC"
exit "$RC"
