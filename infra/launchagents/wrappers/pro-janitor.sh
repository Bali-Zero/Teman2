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
    local note tmp
    note="$(printf '%s' "$2" | LC_ALL=C tr -d '[:cntrl:]\042\134' | cut -c1-300)"   # no control char, quote or backslash can break the JSON
    tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$note" > "$tmp" && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json"   # atomic: a reader never sees half a line
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

# G5b — the operator's kill-switch FILE (no plist edit needed); the payload checks it too, before every candidate
if [ -e "${PRO_JANITOR_STATE_DIR:-$HOME/.local/state/nuzantara/pro-janitor}/disabled" ]; then
    log "kill switch file present — exiting"
    heartbeat "disabled" "kill switch file"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup (the payload also holds a flock)
OLDPID="$(cat "$PIDFILE" 2>/dev/null)"
if [ -f "$PIDFILE" ] && [[ "$OLDPID" =~ ^[0-9]+$ ]] && kill -0 "$OLDPID" 2>/dev/null; then
    log "previous run still alive (pid $OLDPID) — skipping"
    heartbeat "warning" "skipped: previous run alive"   # never ok unread
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
log "run start"
RAW="$(/usr/bin/python3 -I "$HOME/.nuzantara-cron/pro_janitor.py" 2>&1)"
RC=$?
# the note is the payload's own summary line and nothing else: a traceback (with its paths) never reaches the sidecar
# the raw output (a traceback included) goes to the local run.log for a postmortem, capped; never to the sidecar
printf '%s\n' "$RAW" | head -c 65536 >> "$LOG"
OUT="$(printf '%s\n' "$RAW" | LC_ALL=C grep -E '^pro_janitor: [ -~]*$' | tail -n 1 | cut -c1-300)"
NOTE="${OUT:-payload rc=$RC}"
log "payload rc=$RC: $NOTE"

case "$RC" in
    0)  heartbeat "ok" "$NOTE" ;;
    10) heartbeat "warning" "$NOTE" ;;   # a rule error, BLACK or an invalid state: the VM-side trough is localci's
    11) heartbeat "warning" "skipped: previous run alive" ;;   # the payload's flock is held
    *)  heartbeat "error" "$NOTE" ;;   # G9: failure is VISIBLE in the sidecar too
esac
log "run done rc=$RC"
exit 0
