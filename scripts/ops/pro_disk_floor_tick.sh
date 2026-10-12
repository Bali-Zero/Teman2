#!/bin/bash
# pro.disk_floor — reads Pro's free space every 30 min and pages under the floor (B6-4,
# docs/specs/localci-sovereign-2026-10-07.md: Pro keeps > 100 GB free, always; RULED 2026-10-08).
# ok above 100 GB, warning from 60 to 100, failed under 60: the sidecar writes `failed` as `error`, the word
# scripts/lib/heartbeat.sh canonicalises it to and the one sentinel-aggregate.py and the healer read.
# Born via scripts/organ_birth.py (genes imprinted). Canon: scripts/ops/pro_disk_floor_tick.sh
# Live:  ~/.nuzantara-cron/pro_disk_floor_tick.sh (declared pair, node=pro). One-shot: StartInterval, no KeepAlive (#7).

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="pro.disk_floor"
LOG_DIR="$HOME/logs/pro-disk_floor"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="${TMPDIR:-/tmp}/nuzantara-pro-disk_floor.pid"
DATA="${DISK_FLOOR_PATH:-/System/Volumes/Data}"   # never `df /`: that is the sealed system snapshot (disk-monitor, 2026-09-26)
OK_ABOVE_MB=100000    # ok above 100 GB: compared in MB, so 100.5 GB is above it (whole GB would floor it to 100)
FAIL_UNDER_MB=60000   # failed under 60 GB

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    local note
    note="$(printf '%s' "$2" | tr -d '\042\134' | tr '\n\t' '  ')"   # no quote or backslash can break the JSON
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$note" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    log "node guard: $(hostname -s) != nuzantara — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${PRO_DISK_FLOOR_ENABLED:-true}" = "false" ]; then
    log "kill switch PRO_DISK_FLOOR_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "warning" "skipped: previous run alive (pid $(cat "$PIDFILE" 2>/dev/null)), free space not read"   # never ok unread
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
log "run start"
# whole MB, floored (a floor is never met by rounding up); 1 GB = 10^9 bytes, as df -H and the localci prune report it
FREE_MB="$(df -Pk "$DATA" 2>/dev/null | awk 'NR==2 && $4 ~ /^[0-9]+$/ { printf "%d", $4 * 1024 / 1000000 }')"
if [ -z "$FREE_MB" ]; then
    log "df -Pk $DATA unreadable"
    heartbeat "error" "free space unreadable: df -Pk $DATA gave no number"
    exit 0
fi
if [ "$FREE_MB" -gt "$OK_ABOVE_MB" ]; then VERDICT="ok"
elif [ "$FREE_MB" -ge "$FAIL_UNDER_MB" ]; then VERDICT="warning"
else VERDICT="failed"
fi
FREE_GB="$(awk -v m="$FREE_MB" 'BEGIN { printf "%.1f", m / 1000 }')"
NOTE="free_gb=$FREE_GB on $DATA (ok > $((OK_ABOVE_MB / 1000)), failed < $((FAIL_UNDER_MB / 1000)))"
if [ "$VERDICT" != "ok" ]; then
    # the three biggest top-level directories of ~ — only when paging: the walk took 94 s on Pro (2026-10-08)
    TOP="$(du -sxk "$HOME"/* "$HOME"/.[!.]* 2>/dev/null | sort -rn | head -3 \
        | awk -v h="$HOME/" '{ p = $2; sub("^" h, "~/", p); printf "%s%s %.1fGB", (NR > 1 ? ", " : ""), p, $1 * 1024 / 1e9 }')"
    NOTE="$NOTE; biggest: ${TOP:-unread}"
fi
log "verdict=$VERDICT $NOTE"
case "$VERDICT" in
    ok) heartbeat "ok" "$NOTE" ;;
    warning) heartbeat "warning" "$NOTE" ;;
    *) heartbeat "error" "failed: $NOTE" ;;   # G9: failure is VISIBLE in the sidecar too
esac
echo "pro_disk_floor: $VERDICT $NOTE"
exit 0
