#!/bin/bash
# pro.iqoo_radar_relay — Relay P0 Incident Capsules to the iQOO RADAR node
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-iqoo_radar_relay.sh
# Live:  ~/scripts/pro-iqoo_radar_relay.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.iqoo_radar_relay"
LOG_DIR="$HOME/logs/pro-iqoo_radar_relay"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-iqoo_radar_relay.pid"

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
if [ "${PRO_IQOO_RADAR_RELAY_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_IQOO_RADAR_RELAY_ENABLED=false — exiting"
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
log "run start"
REPO="$HOME/nuzantara"
PYTHON="$REPO/.venv/bin/python"
RELAY="$REPO/scripts/iqoo_radar_relay.py"
TARGET="${PRO_IQOO_RADAR_RELAY_TARGET:-u0_a345@100.64.134.94}"
PORT="${PRO_IQOO_RADAR_RELAY_PORT:-8022}"
IDENTITY="${PRO_IQOO_RADAR_RELAY_IDENTITY:-$HOME/.ssh/nuzantara_iqoo_radar}"
KNOWN_HOSTS="${PRO_IQOO_RADAR_RELAY_KNOWN_HOSTS:-$HOME/.ssh/known_hosts_iqoo_radar}"

if [ ! -x "$PYTHON" ] || [ ! -f "$RELAY" ]; then
    log "FATAL: relay runtime missing"
    RC=66
elif [ ! -f "$IDENTITY" ] || [ ! -f "$KNOWN_HOSTS" ]; then
    # Prepared-but-unprovisioned is visible and never falls back to an admin key.
    log "FATAL: dedicated identity or pinned host key missing"
    RC=78
else
    "$PYTHON" "$RELAY" \
        --spool-dir "$HOME/.organism/tg_spool" \
        --state-dir "$HOME/.organism/iqoo-radar-relay" \
        --target "$TARGET" \
        --port "$PORT" \
        --identity "$IDENTITY" \
        --known-hosts "$KNOWN_HOSTS" \
        >> "$LOG" 2>&1
    RC=$?
fi

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
