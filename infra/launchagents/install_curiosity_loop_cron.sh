#!/bin/bash
# Install the curiosity_loop daily cron (com.nuzantara.curiosity-loop.daily).
#
# Why: scripts/curiosity_loop.sh declared in its header that it is invoked by
# ~/Library/LaunchAgents/com.graph.curiosity-loop.plist, but that plist was
# never installed (or was lost) — so the gap-research robot never ran
# autonomously and kg_proposals stayed empty (superscar #2 Esiste!=Armato; the
# schedule lived only as a code comment, not a tracked artifact). This installer
# renders the tracked template for the current host and loads it.
#
# Idempotent. Kill switch:
#   launchctl bootout gui/$(id -u)/com.nuzantara.curiosity-loop.daily
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# If invoked from a throwaway worktree, resolve the STABLE main checkout — a
# cron pointed at .worktrees/ would break when the worktree is reaped (W81:
# cron armed on an ephemeral path).
case "$REPO" in
  */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;;
esac

HOME_DIR="$HOME"
LABEL="com.nuzantara.curiosity-loop.daily"
SRC="$REPO/infra/launchagents/$LABEL.plist"
DST="$HOME_DIR/Library/LaunchAgents/$LABEL.plist"

if [ "${CURIOSITY_LOOP_CRON_ENABLED:-true}" = "false" ]; then
    echo "CURIOSITY_LOOP_CRON_ENABLED=false — skipping install"; exit 0
fi
[ -f "$SRC" ] || { echo "FATAL: template not found at $SRC"; exit 1; }

mkdir -p "$HOME_DIR/Library/LaunchAgents" "$HOME_DIR/logs"

# Render placeholders for THIS host (no hardcoded /Users/<name> in the repo).
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME_DIR|g" "$SRC" > "$DST"
chmod 644 "$DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DST"

echo "Installed $LABEL -> $DST (REPO=$REPO)"
echo "Verify:  launchctl list | grep curiosity-loop"
echo "Run now: launchctl kickstart -k gui/$(id -u)/$LABEL"
