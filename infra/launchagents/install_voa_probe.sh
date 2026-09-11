#!/bin/bash
# Install the VOA journey probe LaunchAgent (com.nuzantara.voa-probe).
#
# Why: scripts/probes/voa_journey_probe.mjs + its wrapper
# (infra/launchagents/wrappers/voa-probe-wrapper.sh) exist as TRACKED
# artifacts, but a plist with __HOME__/__REPO_ROOT__ placeholders schedules
# nothing on its own — a cron armed only by hand-editing a copy in
# ~/Library/LaunchAgents/ is lost on re-setup, and (worse) a copy rendered
# once and never re-installed silently drifts from the tracked source
# (superscar #1 HOME-fork + #2 Esiste!=Armato). This installer renders the
# tracked template for the CURRENT host and (re)loads it — idempotent, safe
# to re-run after every pull that touches the probe or the wrapper.
#
# Kill switch:
#   launchctl bootout gui/$(id -u)/com.nuzantara.voa-probe
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# If invoked from a throwaway worktree, resolve the STABLE main checkout — a
# cron pointed at .worktrees/ would break the moment the worktree is reaped
# (scar W81: a plist that outlives the directory it points into).
case "$REPO" in
  */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;;
esac

LABEL="com.nuzantara.voa-probe"
PLIST_SRC="$REPO/infra/launchagents/$LABEL.plist"
PROBE="$REPO/scripts/probes/voa_journey_probe.mjs"
WRAPPER="$REPO/infra/launchagents/wrappers/voa-probe-wrapper.sh"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${VOA_PROBE_CRON_ENABLED:-true}" = "false" ]; then
    echo "VOA_PROBE_CRON_ENABLED=false — skipping install"; exit 0
fi

[ -f "$PLIST_SRC" ] || { echo "FATAL: plist template not found at $PLIST_SRC"; exit 1; }
# Refuse to arm a cron pointed at a repo root that does not actually contain
# the probe — the wrapper itself has this exact guard (W105 class) for the
# runtime path, but a bad REPO_ROOT baked into the plist at INSTALL time
# would still schedule a job that fires every 15 minutes and FATALs every
# single tick (cron theater — superscar #2). Catch it here, once, instead.
[ -f "$PROBE" ] || { echo "FATAL: probe not found under resolved REPO_ROOT ($REPO) at $PROBE — refusing to install"; exit 1; }
[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found under resolved REPO_ROOT ($REPO) at $WRAPPER — refusing to install"; exit 1; }
command -v node >/dev/null 2>&1 || echo "WARN: no 'node' on this installer's PATH — the wrapper resolves its own interpreter at runtime (/opt/homebrew/bin/node first), so this is advisory only"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/logs"

# Render placeholders for THIS host (no hardcoded /Users/<name> in the repo).
sed -e "s|__HOME__|$HOME|g" -e "s|__REPO_ROOT__|$REPO|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

echo "Installed $LABEL -> $PLIST_DST (REPO=$REPO)"
echo "Verify:   launchctl list | grep voa-probe"
echo "Run now:  launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "Logs:     tail -f $HOME/logs/voa-probe.log"
echo "Heartbeat: cat $HOME/logs/voa-probe-heartbeat.json"
