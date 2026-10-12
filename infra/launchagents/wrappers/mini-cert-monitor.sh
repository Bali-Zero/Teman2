#!/bin/bash
# mini.cert_monitor — daily verified TLS certificate monitor.
# Canon: infra/launchagents/wrappers/mini-cert-monitor.sh
# Live:  ~/scripts/mini-cert-monitor.sh (declared pair, node=mini)
# The Pro HOME twin stays untouched until the first green Mini heartbeat, then retires at cutover.

set -u
umask 077

ORGAN_ID="mini.cert_monitor"
LOG_DIR="$HOME/logs/mini-cert-monitor"
LOG="$LOG_DIR/run.log"
SIDECAR_DIR="$HOME/.organism/last_seen"
LOCKDIR="/tmp/nuzantara-mini-cert_monitor.lock"
REPO="$HOME/nuzantara"
PAYLOAD="$REPO/scripts/cert_monitor.py"
GATEWAY="$REPO/scripts/tg_notify.py"
PYTHON_BIN="${CERT_MONITOR_PYTHON:-/usr/bin/python3}"
mkdir -p "$LOG_DIR" "$SIDECAR_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }
heartbeat() {
    local tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    if printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$tmp" \
        && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json"; then
        return 0
    fi
    rm -f "$tmp"
    return 1
}
notify() {
    TG_ACT_ROUTING_ENABLED=false TG_RELAY_SSH='' /usr/bin/python3 "$GATEWAY" \
        --tier p0 --source cert-monitor --dedup-key "$1" -- "$2" >> "$LOG" 2>&1
}

if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: wrong node"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi
if [ "${MINI_CERT_MONITOR_ENABLED:-true}" = "false" ]; then
    log "kill switch enabled"
    heartbeat "disabled" "kill switch"
    exit 0
fi

if ! mkdir "$LOCKDIR" 2>/dev/null; then
    owner=$(cat "$LOCKDIR/pid" 2>/dev/null || true)
    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null \
        && ps -p "$owner" -o command= 2>/dev/null | grep -q "mini-cert-monitor.sh"; then
        # A live previous run is normal for seconds (7 hosts x 8 s timeout); one alive for an
        # hour is hung, and must not read green every day (superscar #2).
        age=$(( $(date +%s) - $(stat -f %m "$LOCKDIR" 2>/dev/null || date +%s) ))
        if [ "$age" -lt 3600 ]; then
            heartbeat "ok" "monitor already running"
        else
            heartbeat "warning" "previous run alive for ${age}s"
        fi
        exit 0
    fi
    rm -rf "$LOCKDIR"
    mkdir "$LOCKDIR" 2>/dev/null || { heartbeat "error" "lock unavailable"; exit 0; }
fi
echo $$ > "$LOCKDIR/pid"
FINISHED=0
# shellcheck disable=SC2329 # invoked by the EXIT trap
on_exit() {
    rc=$?
    if [ "$FINISHED" -ne 1 ]; then
        heartbeat "error" "cert monitor broken rc=$rc"
        notify "cert:monitor:broken" "cert monitor broken" || true
    fi
    rm -rf "$LOCKDIR"
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi

OUT=""; RC=0
if [ -f "$PAYLOAD" ]; then
    OUT=$(cd "$REPO" && "$PYTHON_BIN" "$PAYLOAD" 2>> "$LOG") || RC=$?
else
    RC=127
fi
printf '%s\n' "$OUT" >> "$LOG"

PARSED=""; PARSE_RC=0
PARSED=$(printf '%s\n' "$OUT" | /usr/bin/python3 -c '
import json, sys
d=json.load(sys.stdin); rows=d["results"]
valid={"ok","expiring","unreachable","verify_failed","parse_error"}
expected={"balizero.com","kita.balizero.com","mail.balizero.com","calendar.balizero.com","drive.balizero.com","knowledge.balizero.com","nuzantara-rag.fly.dev"}
if not isinstance(rows,list) or len(rows) != len(expected): raise ValueError("host count")
for r in rows:
    if not isinstance(r.get("host"),str) or r.get("status") not in valid: raise ValueError("row")
    if r.get("days_left") is not None and not isinstance(r.get("days_left"),int): raise ValueError("days")
if {r["host"] for r in rows} != expected: raise ValueError("host set")
bad=[r for r in rows if r["status"] != "ok"]
days=[r["days_left"] for r in rows if isinstance(r.get("days_left"),int)]
print("SUMMARY\t%d\t%d\t%s" % (len(rows),len(bad),min(days) if days else "unknown"))
import re
def clean(x): return re.sub(r"[^A-Za-z0-9 .:_()/-]", "", str(x or "-"))[:80]
for r in bad: print("FINDING\t%s\t%s\t%s\t%s" % (r["host"],r["status"],r["days_left"] if r["days_left"] is not None else "unknown",clean(r.get("reason"))))
') || PARSE_RC=$?

SUMMARY=$(printf '%s\n' "$PARSED" | grep '^SUMMARY' || true)
IFS=$'\t' read -r _ TOTAL FINDINGS MIN_DAYS <<EOF
$SUMMARY
EOF
if [ "$PARSE_RC" -ne 0 ] || [ -z "$SUMMARY" ] \
    || { [ "$RC" -eq 0 ] && [ "$FINDINGS" -ne 0 ]; } \
    || { [ "$RC" -eq 1 ] && [ "$FINDINGS" -eq 0 ]; } \
    || { [ "$RC" -ne 0 ] && [ "$RC" -ne 1 ]; }; then
    heartbeat "error" "cert monitor broken rc=$RC"
    notify "cert:monitor:broken" "cert monitor broken" || log "broken alert failed or spooled"
elif [ "$RC" -eq 0 ]; then
    heartbeat "ok" "$TOTAL hosts ok, min ${MIN_DAYS}d"
else
    printf '%s\n' "$PARSED" | while IFS=$'\t' read -r tag host status days reason; do
        [ "$tag" = "FINDING" ] || continue
        notify "cert:$host:$status" "$host status=$status days=$days reason=$reason" \
            || log "finding alert failed or spooled"
    done
    heartbeat "ok" "$FINDINGS findings"
fi

FINISHED=1
log "run done monitor_rc=$RC"
exit 0
