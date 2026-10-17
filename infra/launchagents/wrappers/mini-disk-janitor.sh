#!/bin/bash
# mini.disk_janitor — Daily bounded disk hygiene on the Mini: prunes the self-hosted runner caches when idle, prunes dangling docker images and build cache, trims the Colima VM, ages out allowlisted user caches, GCs npm/uv, and alarms on host/runner disk ceilings
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/mini-disk-janitor.sh
# Live:  ~/scripts/mini-disk-janitor.sh (declared pair, node=mini)

set -u   # G9_fail_visible: unset vars crash, they do not expand empty
# launchd hands a job /usr/bin:/bin:/usr/sbin:/sbin — docker, colima, npm live in /opt/homebrew/bin
# and /usr/local/bin, uv in ~/.local/bin; without this their steps are dead forever. PREPENDED so a
# test can still put its own dirs behind it. ${HOME:-}: set -u must not kill us before the trap is armed.
PATH="/opt/homebrew/bin:/usr/local/bin:${HOME:-}/.local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"; export PATH

ORGAN_ID="mini.disk_janitor"
SIDECAR_DIR="${MINI_DISK_JANITOR_SIDECAR_DIR:-${HOME:+$HOME/.organism/last_seen}}"   # injectable so a test never touches the live sidecar
if [ -z "$SIDECAR_DIR" ]; then
    echo "$ORGAN_ID: HOME is unset and no sidecar dir given — cannot write a heartbeat, exiting visibly" >&2
    exit 1
fi
LOG_DIR="${MINI_DISK_JANITOR_LOG_DIR:-${HOME:+$HOME/logs/mini-disk_janitor}}"
LOG_DIR="${LOG_DIR:-$SIDECAR_DIR}"
LOG="$LOG_DIR/run.log"
PIDFILE="${MINI_DISK_JANITOR_PIDFILE:-/tmp/nuzantara-mini-disk_janitor.pid}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG" 2>/dev/null; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
HB_DONE=0; HB_FAIL=0
heartbeat() { # $1 status, $2 note — HB_DONE only after the sidecar is really on disk
    mkdir -p "$SIDECAR_DIR" 2>/dev/null
    if printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json" 2>/dev/null; then
        HB_DONE=1
    else
        HB_FAIL=1
        echo "$ORGAN_ID: heartbeat write FAILED ($SIDECAR_DIR/$ORGAN_ID.json) status=$1 note=$2" >&2
        log "heartbeat write FAILED status=$1 note=$2"
    fi
}
# A signal or an unset-var crash reaches the EXIT trap, which writes an error heartbeat when no branch did.
on_exit() {
    local rc=$?
    [ "$HB_DONE" = 1 ] || heartbeat "error" "abnormal exit rc=$rc"
    [ "$(cat "$PIDFILE" 2>/dev/null)" = "$$" ] && rm -f "$PIDFILE"   # only our own lock
    [ "$HB_FAIL" = 0 ] || exit 1   # the ONE non-zero exit, on every path: a sidecar that cannot be written is the only signal left
    return 0
}
trap 'exit 143' TERM; trap 'exit 130' INT; trap 'exit 129' HUP
trap on_exit EXIT
mkdir -p "$LOG_DIR" 2>/dev/null

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${MINI_DISK_JANITOR_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_DISK_JANITOR_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup. The Mini healer
# (scripts/healer_receptor_registry.py) reads only ok/success/healthy/starting/running as alive, so
# every non-failure here is status ok and the nuance rides in the note.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "previous-run-active"
    exit 0
fi
echo $$ > "$PIDFILE"

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartCalendarInterval, no KeepAlive)
log "run start"
# Payload lives in the canonical main checkout (never a worktree). The cron is the one caller that
# applies; the payload prints `summary ...` then `level=...` on stdout and logs on stderr.
PAYLOAD="${MINI_DISK_JANITOR_PAYLOAD:-${HOME:-}/nuzantara/scripts/ops/mini_disk_janitor.sh}"
if [ ! -f "$PAYLOAD" ]; then
    log "payload missing: $PAYLOAD"
    heartbeat "error" "payload missing"
    exit 0
fi
OUT=$(bash "$PAYLOAD" --apply 2>>"$LOG")
RC=$?
SUMMARY=$(printf '%s\n' "$OUT" | grep '^summary ' | tail -1)
LEVEL=$(printf '%s\n' "$OUT" | grep '^level=' | tail -1 | sed 's/^level=//')
FREED_KB=$(printf '%s' "$SUMMARY" | sed -n 's/.*freed_kb=\(-\{0,1\}[0-9][0-9]*\).*/\1/p')
HOST_GB=$(printf '%s' "$SUMMARY" | sed -n 's/.*host_free_gb=\([0-9][0-9]*\).*/\1/p')
RUNNER_PCT=$(printf '%s' "$SUMMARY" | sed -n 's/.*runner_pct=\([0-9a-z]*\).*/\1/p')
BUSY=$(printf '%s' "$SUMMARY" | sed -n 's/.*busy=\([0-9]\).*/\1/p')
FREED_GB=$(( ${FREED_KB:-0} / 1048576 ))
NOTE="level=${LEVEL:-none}$([ "${BUSY:-0}" = "1" ] && echo " runner-busy") freed ${FREED_GB}GiB host_free ${HOST_GB:-?}GiB runner ${RUNNER_PCT:-?}%"

if [ "$RC" -ne 0 ]; then
    heartbeat "error" "rc=$RC $NOTE"   # G9: failure is VISIBLE in the sidecar too
else
    case "${LEVEL:-}" in
        ok|warning) heartbeat "ok" "$NOTE" ;;
        critical|unknown) heartbeat "error" "$NOTE" ;;
        *) heartbeat "error" "no level from payload rc=$RC" ;;   # a payload that printed nothing proves nothing
    esac
fi
log "run done rc=$RC $NOTE"
# exit 0 by design (a failed payload is already visible in the sidecar) — EXCEPT when the sidecar
# itself could not be written: on_exit turns that into exit 1 on every path.
exit 0
