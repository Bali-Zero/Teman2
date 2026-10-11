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
PIDFILE="/tmp/nuzantara-mini-restore_drill.pid"
REPO="$HOME/nuzantara"
PAYLOAD="$REPO/scripts/restore_drill/run_drill.sh"
GATEWAY="$REPO/scripts/tg_notify.py"
mkdir -p "$LOG_DIR" "$SIDECAR_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

heartbeat() { # $1 status, $2 note
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

notify() { # $1 tier, $2 dedup key, $3 safe message
    tier=$1
    key=$2
    message=$3
    /usr/bin/python3 "$GATEWAY" --tier "$tier" --source restore-drill \
        --dedup-key "$key" -- "$message" >> "$LOG" 2>&1
}

write_failure_escalation() { # $1 outcome, $2 rc
    outcome=$1
    payload_rc=$2
    (
        export RESTORE_DRILL_OUTCOME="$outcome"
        export RESTORE_DRILL_RC="$payload_rc"
        cd "$REPO" || exit 1
        /usr/bin/python3 -c 'import os; from scripts.sentinel_lib.escalations import write_escalation; outcome=os.environ["RESTORE_DRILL_OUTCOME"]; rc=os.environ["RESTORE_DRILL_RC"]; write_escalation({"job":"mini.restore_drill","type":"restore_drill_failure","source":"mini-restore-drill","priority":"HIGH","outcome":outcome,"error_summary":"Monthly restore drill %s (rc=%s)" % (outcome, rc),"description":"Investigate the monthly restore proof; no production dump rows were included."})'
    ) >> "$LOG" 2>&1
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

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

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
RC=0
if [ ! -f "$PAYLOAD" ]; then
    echo "CANNOT-VERIFY: payload missing" >> "$LOG"
    RC=2
else
    /bin/bash "$PAYLOAD" >> "$LOG" 2>&1 || RC=$?
fi

MONTH=$(date +%Y-%m)
if [ "$RC" -eq 0 ]; then
    heartbeat "ok" "restore and Level-5 verification passed"
    notify digest "restore-drill:${MONTH}:success" \
        "Monthly restore drill passed on Mini (restore + Level-5 verification)." || \
        log "digest notification failed or was spooled"
else
    if [ "$RC" -eq 2 ] || [ "$RC" -eq 124 ]; then
        OUTCOME="CANNOT-VERIFY"
    else
        OUTCOME="FAILED"
    fi
    heartbeat "error" "$OUTCOME rc=$RC"
    notify p0 "restore-drill:${MONTH}" \
        "Monthly restore drill $OUTCOME on Mini (rc=$RC). Investigate the local private log." || \
        log "p0 notification failed or was spooled"
    write_failure_escalation "$OUTCOME" "$RC" || \
        log "write_escalation failed"
fi

log "run done rc=$RC"
exit "$RC"
