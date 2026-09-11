#!/bin/bash
# pro.git_pull_main — Pro auto-sync of ~/nuzantara main checkout (collision-robust; Mini has the 5min sibling)
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-git-pull-main.sh
# Live:  ~/scripts/pro-git-pull-main.sh (declared pair, node=pro)

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
# exercised on any machine; this wrapper only adds the genome shell around it.
#
# ONE TREE (2026-09-10): the payload used to be read from the frozen ~/nuzantara-deploy
# checkout so the puller never executed from the very tree it rewrites. That checkout is
# retired, and the hazard it defended against turns out not to exist — MEASURED, not
# assumed: git replaces a worktree file by unlink+create, so a bash process already
# executing it keeps its open fd on the OLD inode and runs the original script to
# completion. Proved on 2026-09-10 with a scratch repo: a `git checkout` that swapped a
# running script for entirely different content mid-`sleep` still printed the original's
# last line and exited 0.
#
# A first attempt at this cure ran a mktemp SNAPSHOT of the payload instead. Cross-family
# review (codex-gpt-5.6-sol) killed it: the payload resolves both its runtime-state
# allowlist and its Telegram gateway from `dirname "$0"`, so running the copy out of /tmp
# silently disabled the protected-file handling this puller exists to honour. Running in
# place keeps `$0` inside the checkout, which is what those two lookups need.
log "run start"
PAYLOAD="$HOME/nuzantara/scripts/pro/pro-git-pull.sh"
if [ -f "$PAYLOAD" ]; then
    log "payload: $PAYLOAD"
    bash "$PAYLOAD"; RC=$?
else
    log "FATAL: payload not found at $PAYLOAD"
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
