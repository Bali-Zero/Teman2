#!/bin/bash
# pro.board_seat_consumer — drain the gateway-routed rows a seat can close
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-board-seat-consumer.sh
# Live:  ~/scripts/pro-board-seat-consumer.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.board_seat_consumer"
LOG_DIR="$HOME/logs/pro-board_seat_consumer"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-board_seat_consumer.pid"

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
if [ "${PRO_BOARD_SEAT_CONSUMER_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_BOARD_SEAT_CONSUMER_ENABLED=false — exiting"
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

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
REPO="$HOME/nuzantara"
log "run start"
cd "$REPO" || { log "FATAL: repo missing at $REPO"; heartbeat "error" "repo missing"; exit 0; }

REPORT=$(python3 scripts/board_seat_consumer.py --json 2>>"$LOG")
RC=$?
log "report: ${REPORT:-<empty>}"

# The sidecar carries the WORK, not just the pulse: an organ that reports "ok"
# every hour while closing nothing is the green-but-dead shape this consumer
# exists to drain (superscar #2).
NOTE=$(printf '%s' "$REPORT" | python3 -c "
import json, sys
try:
    r = json.loads(sys.stdin.read())
except Exception:
    print('report unparseable'); sys.exit(0)
print('closed=%d left=%d seen=%d' % (len(r.get('resolved', [])), len(r.get('left', [])), r.get('seen', 0)))
" 2>/dev/null) || NOTE="report unparseable"

if [ $RC -eq 0 ]; then
    heartbeat "ok" "${NOTE:-no report}"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
