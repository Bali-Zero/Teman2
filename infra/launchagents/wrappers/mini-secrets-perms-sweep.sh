#!/bin/bash
# mini.secrets_perms_sweep — recurring sweep+fix of group/other-readable secret-named files (memory notes, tokens, keys) via secrets_permissions_audit.py --fix — closes the one-shot debt from PR #3621
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/mini-secrets-perms-sweep.sh
# Live:  ~/scripts/mini-secrets-perms-sweep.sh (declared pair, node=mini)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="mini.secrets_perms_sweep"
LOG_DIR="$HOME/logs/mini-secrets_perms_sweep"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-mini-secrets_perms_sweep.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${MINI_SECRETS_PERMS_SWEEP_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_SECRETS_PERMS_SWEEP_ENABLED=false — exiting"
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
/usr/bin/python3 "$HOME/nuzantara/scripts/secrets_permissions_audit.py" --fix >> "$LOG" 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
