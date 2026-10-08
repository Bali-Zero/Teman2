#!/bin/bash
# pro.visa_reattestation — Weekly Visa Oracle portal re-attestation: reads the OFFICIAL_PORTAL pages, judges them, folds an UNSIGNED candidate pack and opens a PR for a session to sign
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-visa-reattestation.sh
# Live:  ~/scripts/pro-visa-reattestation.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.visa_reattestation"
LOG_DIR="$HOME/logs/pro-visa_reattestation"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-visa_reattestation.pid"

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
if [ "${PRO_VISA_REATTESTATION_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_VISA_REATTESTATION_ENABLED=false — exiting"
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
# The runner owns its own worktree, branch and PR; this wrapper only proves life.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
log "run start"
/usr/bin/python3 "$HOME/nuzantara/scripts/visa_reattestation_organ.py" >> "$LOG" 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
