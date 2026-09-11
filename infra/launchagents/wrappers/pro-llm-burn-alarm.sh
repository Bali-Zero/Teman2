#!/bin/bash
# pro.llm_burn_alarm — burn-rate alarm on llm_cost_events — trailing 24h vs 7-day median, names endpoint+model
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-llm-burn-alarm.sh
# Live:  ~/scripts/pro-llm-burn-alarm.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.llm_burn_alarm"
LOG_DIR="$HOME/logs/pro-llm_burn_alarm"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-llm_burn_alarm.pid"

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
if [ "${PRO_LLM_BURN_ALARM_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_LLM_BURN_ALARM_ENABLED=false — exiting"
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
# REPO is the canonical Pro main checkout (the pre-migration ~/Desktop path
# is a symlink to this same tree, origin-tracked) — llm_burn_alarm.py
# resolves scripts/pg.sh and scripts/tg_notify.py as siblings via __file__,
# so it must run FROM the full repo tree, not a standalone HOME copy (only
# this wrapper is forked, per G3_declared_pair — the payload script stays
# repo-relative).
REPO="$HOME/nuzantara"
# Telegram + Postgres credentials for tg_notify.py / scripts/pg.sh — sourced
# here, never baked into the plist (VADEMECUM: no secrets in plists).
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
PY="$REPO/apps/backend-rag/.venv/bin/python"
[ -x "$PY" ] || PY="/opt/homebrew/bin/python3"
[ -x "$PY" ] || PY="python3"
if cd "$REPO" 2>>"$LOG"; then
    "$PY" scripts/llm_burn_alarm.py >> "$LOG" 2>&1
    RC=$?
else
    log "FATAL: cd $REPO failed"
    RC=1
fi

# llm_burn_alarm.py's own exit contract: 0=OK (quiet), 1=ALARM (dispatched —
# the organ worked correctly, it just found something), 2=CANNOT_VERIFY (the
# organ could NOT do its job — genuinely degraded, worth the healer's
# attention). Only rc=2 (or anything unexpected) counts as an organ failure
# here — rc=1 is a successful run whose finding happens to be bad news, and
# collapsing it into "error" would train the healer to chase a working alarm.
case "$RC" in
    0) heartbeat "ok" "run done: no anomaly" ;;
    1) heartbeat "ok" "run done: ALARM dispatched" ;;
    2) heartbeat "error" "run done: CANNOT_VERIFY (rc=2)" ;;
    *) heartbeat "error" "run done: unexpected rc=$RC" ;;
esac
log "run done rc=$RC"
exit 0
