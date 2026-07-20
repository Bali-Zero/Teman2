#!/bin/bash
# pro.git_pull_main — Pro auto-sync of ~/nuzantara main checkout (collision-robust; Mini has the 5min sibling)
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-git_pull_main.sh
# Live:  ~/scripts/pro-git_pull_main.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.git_pull_main"
LOG_DIR="$HOME/logs/pro-git_pull_main"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-git_pull_main.pid"

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
if [ "${PRO_GIT_PULL_MAIN_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_GIT_PULL_MAIN_ENABLED=false — exiting"
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

# ---- payload: collision-robust pull. The logic lives in a separately-TESTED script
# (scripts/pro/pro-git-pull.sh + test_pro_git_pull.sh, 28 assertions) so it can be
# exercised on any machine; this wrapper only adds the genome shell around it. Run it
# from the DEPLOY checkout (kept current by the deploy-puller) so the puller never
# executes from the very tree it rewrites (self-mod); fall back to the main tree.
log "run start"
PAYLOAD="$HOME/nuzantara-deploy/scripts/pro/pro-git-pull.sh"
[ -f "$PAYLOAD" ] || PAYLOAD="$HOME/nuzantara/scripts/pro/pro-git-pull.sh"
if [ -f "$PAYLOAD" ]; then
    log "payload: $PAYLOAD"
    bash "$PAYLOAD"; RC=$?
else
    log "FATAL: payload not found in deploy or main"
    heartbeat "error" "payload missing"
    exit 1
fi

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
