#!/bin/bash
# pro.disk_janitor — Daily bounded disk janitor on Pro: prunes session scratch, codex transcripts, old log archives, uv/docker dangling, brew leftovers and applies qdrant backup retention; never touches PII, pilots, worktrees, models
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-disk-janitor.sh
# Live:  ~/scripts/pro-disk-janitor.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.disk_janitor"
LOG_DIR="$HOME/logs/pro-disk_janitor"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-disk_janitor.pid"

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
if [ "${PRO_DISK_JANITOR_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_DISK_JANITOR_ENABLED=false — exiting"
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
# Payload lives in the canonical main checkout (never a worktree, whose path dies with it).
# DRY-RUN is the payload's default; the cron is the one caller that applies. The payload's
# log() already tees every line into DISK_JANITOR_LOG, so its stdout/stderr are dropped
# here — appending them too would write every line twice (council finding R6-1). The
# receipts journal stays at ~/logs/disk-janitor.receipts.jsonl (payload default).
PAYLOAD="${PRO_DISK_JANITOR_PAYLOAD:-$HOME/nuzantara/scripts/disk_janitor.sh}"
if [ ! -f "$PAYLOAD" ]; then
    log "payload missing: $PAYLOAD"
    heartbeat "error" "payload missing"
    exit 0
fi
DISK_JANITOR_LOG="$LOG" bash "$PAYLOAD" --apply >/dev/null 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
