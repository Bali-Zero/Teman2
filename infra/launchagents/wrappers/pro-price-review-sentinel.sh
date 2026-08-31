#!/bin/bash
# pro.price_review_sentinel — Alerts when the Bali Zero price sheet loaded by pricing_service is past its 90-day review interval, or when metadata.last_updated has stopped tracking edits and can no longer answer the freshness question in either direction
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/pro-price-review-sentinel.sh
# Live:  ~/scripts/pro-price-review-sentinel.sh (declared pair, node=pro)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.price_review_sentinel"
LOG_DIR="$HOME/logs/pro-price_review_sentinel"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-pro-price_review_sentinel.pid"

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
if [ "${PRO_PRICE_REVIEW_SENTINEL_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_PRICE_REVIEW_SENTINEL_ENABLED=false — exiting"
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

# Byte offset of the log BEFORE this run, so the state line can be read from
# THIS run's output only. Without it, `grep ... "$LOG" | tail -1` over an
# append-only log returns the PREVIOUS run's outcome whenever the current run
# prints none -- and the ${STATE:-...} fallback could then only ever fire on
# the very first run ever. Staleness would be guaranteed, not merely possible.
LOG_OFFSET=$(wc -c < "$LOG" 2>/dev/null || echo 0)
LOG_OFFSET=${LOG_OFFSET// /}

# NOT /usr/bin/python3. This sentinel imports backend code to learn which file
# the live pricing service loads, and `/usr/bin/python3` is 3.9.6 on both Pro
# and M5 — the backend package's __init__ chain reaches a `str | None`
# annotation evaluated at class creation, which is a TypeError before 3.10. The
# organ would have returned CANNOT_VERIFY on every scheduled run, forever, and
# failed loud while never once answering the question it exists for. Measured on
# Pro and M5; the venv is 3.11.11. Two sibling wrappers already use the venv for
# exactly this reason.
"$HOME/nuzantara/apps/backend-rag/.venv/bin/python" "$HOME/nuzantara/scripts/price_review_sentinel.py" >> "$LOG" 2>&1
RC=$?

# Heartbeat semantics DIVERGE from the organ_birth default, deliberately.
#
# rc=1 is a FINDING that was computed AND delivered — the organ did its job, so
# the sidecar says "ok". The sidecar answers "am I alive and working", not "is
# the world good"; mapping a delivered finding to "error" would park this organ
# in permanent red until somebody edits a price, teaching the healer to ignore
# it. The condition itself is not discarded — it rides in the note.
#
# rc=2 (sheet unlocatable, unreadable, malformed, uncorroborated, or a crash)
# and rc=3 (a finding whose alert did NOT go out) are real malfunctions: in
# both cases the organism learned nothing this run.
# The sentinel prints one machine-readable last line; carrying it into the
# sidecar is what keeps "clean" distinguishable from "overdue for four months"
# in the organism's own state, instead of every run looking identical.
# Read ONLY the bytes this run appended. A run that died before printing must
# report that it printed nothing -- not the last thing a healthy run said.
STATE=$(tail -c "+$((LOG_OFFSET + 1))" "$LOG" 2>/dev/null | grep '^SENTINEL-STATE ' | tail -1)
STATE=${STATE:-SENTINEL-STATE outcome=UNKNOWN delivery=unknown note=this-run-printed-no-state-line}

# rc=2 is overloaded: the sentinel returns it for a COMPUTED cannot-verify, and
# CPython also exits 2 when it cannot open the script at all. The state line is
# what tells them apart -- a computed verdict always prints one. With the venv
# interpreter now load-bearing, and the venv being live infrastructure curated
# a package at a time, a missing python gives rc=127 and no line, which must
# not read as a verdict either.
case "$STATE" in
    *this-run-printed-no-state-line*) STATE_MISSING=1 ;;
    *)                                STATE_MISSING=0 ;;
esac

case $RC in
    0) heartbeat "ok" "no finding | ${STATE#SENTINEL-STATE }" ;;
    1) heartbeat "ok" "finding delivered | ${STATE#SENTINEL-STATE }" ;;
    2) if [ "$STATE_MISSING" = "1" ]; then
           heartbeat "error" "the payload did not run to a verdict (rc=2, no state line -- interpreter or script missing, not a computed cannot-verify) | ${STATE#SENTINEL-STATE }"
       else
           heartbeat "error" "cannot verify the price sheet | ${STATE#SENTINEL-STATE }"
       fi ;;
    3) heartbeat "error" "finding computed but NOT delivered | ${STATE#SENTINEL-STATE }" ;;
    *) heartbeat "error" "unexpected rc=$RC | ${STATE#SENTINEL-STATE }" ;;
esac
log "run done rc=$RC"
exit 0
