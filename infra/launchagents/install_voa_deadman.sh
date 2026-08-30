#!/bin/bash
# Install the VOA dead-man receptor LaunchAgent (com.nuzantara.voa-deadman).
#
# Why: scripts/probes/voa_deadman.py + its wrapper
# (infra/launchagents/wrappers/voa-deadman-wrapper.sh) exist as TRACKED
# artifacts, but a plist with __HOME__/__REPO_ROOT__ placeholders schedules
# nothing on its own — a cron armed only by hand-editing a copy in
# ~/Library/LaunchAgents/ is lost on re-setup, and (worse) a copy rendered
# once and never re-installed silently drifts from the tracked source
# (superscar #1 HOME-fork + #2 Esiste!=Armato). This installer renders the
# tracked template for the CURRENT host and (re)loads it — idempotent, safe
# to re-run after every pull that touches the organ or its wrapper. Mirrors
# infra/launchagents/install_voa_probe.sh (the sibling organ this one
# watches) line for line, renamed.
#
# Kill switch:
#   launchctl bootout gui/$(id -u)/com.nuzantara.voa-deadman
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# If invoked from a throwaway worktree, resolve the STABLE main checkout — a
# cron pointed at .worktrees/ would break the moment the worktree is reaped
# (scar W81: a plist that outlives the directory it points into).
case "$REPO" in
  */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;;
esac

LABEL="com.nuzantara.voa-deadman"
PLIST_SRC="$REPO/infra/launchagents/$LABEL.plist"
PAYLOAD="$REPO/scripts/probes/voa_deadman.py"
WRAPPER="$REPO/infra/launchagents/wrappers/voa-deadman-wrapper.sh"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${VOA_DEADMAN_CRON_ENABLED:-true}" = "false" ]; then
    echo "VOA_DEADMAN_CRON_ENABLED=false — skipping install"; exit 0
fi

[ -f "$PLIST_SRC" ] || { echo "FATAL: plist template not found at $PLIST_SRC"; exit 1; }
# Refuse to arm a cron pointed at a repo root that does not actually contain
# the organ — the wrapper itself has this exact guard (W105 class) for the
# runtime path, but a bad REPO_ROOT baked into the plist at INSTALL time
# would still schedule a job that fires every 5 minutes and FATALs every
# single tick (cron theater — superscar #2). Catch it here, once, instead.
[ -f "$PAYLOAD" ] || { echo "FATAL: payload not found under resolved REPO_ROOT ($REPO) at $PAYLOAD — refusing to install"; exit 1; }
[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found under resolved REPO_ROOT ($REPO) at $WRAPPER — refusing to install"; exit 1; }
command -v python3 >/dev/null 2>&1 || echo "WARN: no 'python3' on this installer's PATH — the wrapper resolves its own interpreter at runtime (/usr/bin/python3 first), so this is advisory only"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/logs"

# Render placeholders for THIS host (no hardcoded /Users/<name> in the repo).
sed -e "s|__HOME__|$HOME|g" -e "s|__REPO_ROOT__|$REPO|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

echo "Installed $LABEL -> $PLIST_DST (REPO=$REPO)"
echo "Verify:   launchctl list | grep voa-deadman"
echo "Run now:  launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "Logs:     tail -f $HOME/logs/voa-deadman.log"
echo "Watching: cat \${VOA_PROBE_HEARTBEAT:-\$HOME/logs/voa-probe-heartbeat.json}"
