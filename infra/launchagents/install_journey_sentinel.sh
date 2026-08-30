#!/bin/bash
# Install the production journey sentinel LaunchAgent
# (com.nuzantara.journey-sentinel).
#
# Why: scripts/journey_sentinel.sh + apps/mouth/e2e/production/*.spec.ts
# exist as TRACKED artifacts, but a plist with __HOME__/__REPO_ROOT__
# placeholders schedules nothing on its own — a cron armed only by
# hand-editing a copy in ~/Library/LaunchAgents/ is lost on re-setup, and
# (worse) a copy rendered once and never re-installed silently drifts from
# the tracked source (superscar #1 HOME-fork + #2 Esiste!=Armato). This
# installer renders the tracked template for the CURRENT host and
# (re)loads it — idempotent, safe to re-run after every pull that touches
# the sentinel wrapper or its specs.
#
# Kill switch (runtime, per tick):
#   JOURNEY_SENTINEL_ENABLED=false (env, read by the wrapper)
# Kill switch (uninstall):
#   launchctl bootout gui/$(id -u)/com.nuzantara.journey-sentinel
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# If invoked from a throwaway worktree, resolve the STABLE main checkout — a
# cron pointed at .worktrees/ would break the moment the worktree is reaped
# (scar W81: a plist that outlives the directory it points into).
case "$REPO" in
  */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;;
esac

LABEL="com.nuzantara.journey-sentinel"
PLIST_SRC="$REPO/infra/launchagents/$LABEL.plist"
WRAPPER="$REPO/scripts/journey_sentinel.sh"
SPEC_DIR="$REPO/apps/mouth/e2e/production"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -f "$PLIST_SRC" ] || { echo "FATAL: plist template not found at $PLIST_SRC"; exit 1; }
# Refuse to arm a cron pointed at a repo root that does not actually contain
# the wrapper or its specs — the wrapper itself has this exact guard
# (W105 class) for the runtime path; a bad REPO_ROOT baked into the plist at
# INSTALL time would still schedule a job that fires every hour and FATALs
# every single tick (cron theater — superscar #2). Catch it here, once.
[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found under resolved REPO_ROOT ($REPO) at $WRAPPER — refusing to install"; exit 1; }
[ -d "$SPEC_DIR" ] || { echo "FATAL: production spec dir not found under resolved REPO_ROOT ($REPO) at $SPEC_DIR — refusing to install"; exit 1; }
command -v npx >/dev/null 2>&1 || echo "WARN: no 'npx' on this installer's PATH — the wrapper resolves 'npx' at runtime via its own PATH, so this is advisory only"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/logs"

# Render placeholders for THIS host (no hardcoded /Users/<name> in the repo).
sed -e "s|__HOME__|$HOME|g" -e "s|__REPO_ROOT__|$REPO|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

echo "Installed $LABEL -> $PLIST_DST (REPO=$REPO)"
echo "Verify:   launchctl list | grep journey-sentinel"
echo "Run now:  launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "Logs:     tail -f $HOME/logs/journey-sentinel.log"
echo "Heartbeat: cat $HOME/.organism/last_seen/mini.journey_sentinel.json"
