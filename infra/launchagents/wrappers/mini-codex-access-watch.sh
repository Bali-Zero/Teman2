#!/bin/bash
# mini.codex_access_watch — Watch balizero.com/codex access logs (Vercel) and WhatsApp-alert Zero when someone enters from outside the US (Leopoldo from Italy)
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/mini-codex_access_watch.sh
# Live:  ~/scripts/mini-codex_access_watch.sh (declared pair, node=mini)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="mini.codex_access_watch"
LOG_DIR="$HOME/logs/mini-codex_access_watch"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-mini-codex_access_watch.pid"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s)" != "Mini-Pro2" ]; then
    log "node guard: $(hostname -s) != Mini-Pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${MINI_CODEX_ACCESS_WATCH_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_CODEX_ACCESS_WATCH_ENABLED=false — exiting"
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

REPO="$HOME/Desktop/nuzantara"
WATCHER="$REPO/scripts/codex_access_watch.py"
ENV_FILE="$HOME/.config/nuzantara/codex-watch.env"   # 0600: vercel token + WA line id
MASTER_ENV="$HOME/.openclaw/workspace/.env.master"   # WHATSAPP_TOKEN lives here

if [ ! -f "$WATCHER" ]; then
    log "FATAL: watcher missing at $WATCHER (repo not pulled?)"
    heartbeat "error" "watcher missing"
    exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
    log "FATAL: env file missing at $ENV_FILE"
    heartbeat "error" "env file missing"
    exit 1
fi
set -a
source "$ENV_FILE"
[ -z "${WHATSAPP_TOKEN:-}" ] && [ -f "$MASTER_ENV" ] && \
    eval "$(grep -E '^WHATSAPP_TOKEN=' "$MASTER_ENV")"
set +a

/usr/bin/python3 "$WATCHER" >> "$LOG" 2>&1
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
