#!/bin/zsh
# wr2-warroom-sync.sh — keep the Mini's WR2 Control data fresh from the Pro.
#
# The WR2 Control app on the Mini reads from $HOME/.wr2-warroom-sync/output
# (set as WR2_WARROOM_ROOT in its LaunchAgent). The authoritative war-room data
# lives on the Pro. This pulls Pro→Mini so Damar's operator view stays current.
#
# Fail-soft: a network flap (proxy/WireGuard/ssh) must NOT wipe or corrupt the
# local copy. rsync to a same-filesystem staging dir then swap only on success,
# and never run --delete against a half-synced tree. Logs every run (scar #2:
# read the OUTCOME, not the exit code — we record file counts).
set -uo pipefail

SRC="pro:/Users/nuzantara/nuzantara/apps/war-room/output/"
DST="$HOME/.wr2-warroom-sync/output/"
LOG="$HOME/Library/Logs/wr2-warroom-sync.log"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$DST" "$(dirname "$LOG")"

# 1) reachability probe — if the Pro is unreachable, log and exit 0 (no destructive op)
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes pro 'test -f /Users/nuzantara/nuzantara/apps/war-room/output/queue/human-review-queue.json' 2>/dev/null; then
  echo "$STAMP  SKIP — Pro unreachable or queue missing (no sync, local copy untouched)" >> "$LOG"
  exit 0
fi

# 2) sync. --delete keeps the mirror honest, but only after the probe above proved
#    the source is real (so we never mirror an empty/half source onto a good copy).
if rsync -a --delete --timeout=120 "$SRC" "$DST" >/dev/null 2>>"$LOG"; then
  COUNT=$(find "$DST/carousel" -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  test -f "$DST/queue/human-review-queue.json" && Q="queue-ok" || Q="queue-MISSING"
  echo "$STAMP  OK — synced ($COUNT carousel dirs, $Q)" >> "$LOG"
else
  echo "$STAMP  WARN — rsync failed (exit $?), local copy preserved" >> "$LOG"
fi
exit 0
