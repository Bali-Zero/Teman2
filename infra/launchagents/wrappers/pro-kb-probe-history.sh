#!/bin/bash
# pro.kb_probe_history — records a kb/ops/probe_history.py snapshot of the legal KB retrieval journeys every 6h so the kb-current-live mandate can point at a scheduled job, not a hand-run probe
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-kb-probe-history.sh
# Live:  ~/scripts/pro-kb-probe-history.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.kb_probe_history"
LOG_DIR="$HOME/logs/pro-kb_probe_history"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-kb_probe_history.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    log "node guard: $(hostname -s) != nuzantara — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${PRO_KB_PROBE_HISTORY_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_KB_PROBE_HISTORY_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartCalendarInterval, no KeepAlive)
#
# NOTE ON `RC=$?`: organ_birth.py's template puts `RC=$?` directly after a COMMENT,
# which captures the exit status of the PRECEDING `log` call — always 0. An organ
# wired that way heartbeats "ok" no matter how its payload died (superscar #2,
# "esiste != armato": green is not working). The assignment below therefore sits
# immediately after the real command, with nothing in between.
REPO="$HOME/nuzantara"
PY="$REPO/apps/backend-rag/.venv/bin/python3"

log "run start"
if [ ! -x "$PY" ]; then
    log "interpreter missing/not executable: $PY"
    heartbeat "error" "venv interpreter missing"
    exit 1
fi
cd "$REPO" || {
    log "repo missing: $REPO"
    heartbeat "error" "repo missing"
    exit 1
}
"$PY" kb/ops/probe_history.py record --collection legal_unified >> "$LOG" 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
