#!/bin/bash
# pro.janitor — Watermark free-space keeper for Pro: host-cache allowlist, tiers with hysteresis, dry-run first
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-janitor.sh
# Live:  ~/scripts/pro-janitor.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.janitor"
LOG_DIR="$HOME/logs/pro-janitor"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="${TMPDIR:-/tmp}/nuzantara-pro-janitor.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    local note
    note="$(printf '%s' "$2" | tr -d '\042\134' | tr '\n\t' '  ')"   # no quote or backslash can break the JSON
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$note" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    log "node guard: $(hostname -s) != nuzantara — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${PRO_JANITOR_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_JANITOR_ENABLED=false — exiting"
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
OUT="$(/usr/bin/python3 -I "$HOME/.nuzantara-cron/pro_janitor.py" 2>&1)"
RC=$?
OUT="$(printf '%s' "$OUT" | tail -n 1 | cut -c1-300)"
log "payload rc=$RC: $OUT"

case "$RC" in
    0)  heartbeat "ok" "${OUT:-run done}" ;;
    10) heartbeat "warning" "${OUT:-rule error or BLACK tier}" ;;   # a rule error, or BLACK: the VM-side trough is localci's
    *)  heartbeat "error" "rc=$RC ${OUT}" ;;   # G9: failure is VISIBLE in the sidecar too
esac
log "run done rc=$RC"
exit 0
