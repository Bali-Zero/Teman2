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
RUN_OUTPUT=$(mktemp "$LOG_DIR/run.XXXXXX")
trap 'rm -f "$PIDFILE" "$RUN_OUTPUT"' EXIT
CD_FAILED=0
if cd "$REPO" 2>>"$LOG"; then
    "$PY" scripts/llm_burn_alarm.py > "$RUN_OUTPUT" 2>&1
    RC=$?
else
    log "FATAL: cd $REPO failed"
    RC=70
    CD_FAILED=1
fi
cat "$RUN_OUTPUT" >> "$LOG"

# Exit contract: 0=OK, 1=ALARM only with the ALARM output marker,
# 2=CANNOT_VERIFY. A crash without the marker or a failed cd is an error.
case "$RC" in
    0) heartbeat "ok" "run done: no anomaly" ;;
    1) if grep -q "llm_burn_alarm: ALARM" "$RUN_OUTPUT"; then
           heartbeat "ok" "run done: ALARM dispatched"
       else
           heartbeat "error" "run done: rc=1 without an ALARM marker (probe crashed)"
       fi ;;
    2) heartbeat "error" "run done: CANNOT_VERIFY (rc=2)" ;;
    *) if [ "$CD_FAILED" -eq 1 ]; then
           heartbeat "error" "run done: cd failed"
       else
           heartbeat "error" "run done: unexpected rc=$RC"
       fi ;;
esac
rm -f "$RUN_OUTPUT"
log "run done rc=$RC"
exit 0
