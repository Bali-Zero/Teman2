#!/bin/bash
# Install the WR2 IG metrics scraper daily cron (com.balizero.wr2.ig-metrics-scrape.daily).
#
# Why: scripts/wr2_ig_metrics_scraper.py is the metric PRODUCER the WR2 pipeline
# lacked (it wrote engagement_metrics=None; the analyst consumed metrics only a
# manual backfill produced). The schedule must live as a TRACKED artifact, not just
# a hand-loaded plist on one machine (superscar #1 HOME-fork + #2 Esiste!=Armato:
# a cron armed only in ~/Library/LaunchAgents/ is lost on re-setup). This installer
# renders the tracked template for the current host and loads it.
#
# Idempotent. Kill switch:
#   launchctl bootout gui/$(id -u)/com.balizero.wr2.ig-metrics-scrape.daily
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# If invoked from a throwaway worktree, resolve the STABLE main checkout — a cron
# pointed at .worktrees/ would break when the worktree is reaped (W81).
case "$REPO" in
  */.worktrees/*) REPO="${REPO%%/.worktrees/*}" ;;
esac

HOME_DIR="$HOME"
LABEL="com.balizero.wr2.ig-metrics-scrape.daily"
SRC="$REPO/infra/launchagents/$LABEL.plist"
DST="$HOME_DIR/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$HOME_DIR/.openclaw/bin/wr2/wr2-ig-metrics-scrape.sh"

if [ "${WR2_IG_METRICS_CRON_ENABLED:-true}" = "false" ]; then
    echo "WR2_IG_METRICS_CRON_ENABLED=false — skipping install"; exit 0
fi
[ -f "$SRC" ] || { echo "FATAL: template not found at $SRC"; exit 1; }

mkdir -p "$HOME_DIR/Library/LaunchAgents" "$HOME_DIR/logs" "$(dirname "$WRAPPER")"

# Keep the live wrapper in sync with the tracked copy (the wrapper is the executed
# artifact; the repo copy is the source of truth — defeats HOME-fork drift).
if [ -f "$REPO/scripts/wr2-ig-metrics-scrape.sh" ]; then
    cp "$REPO/scripts/wr2-ig-metrics-scrape.sh" "$WRAPPER"
    chmod 755 "$WRAPPER"
fi

# Render placeholders for THIS host (no hardcoded /Users/<name> in the repo).
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME_DIR|g" "$SRC" > "$DST"
chmod 644 "$DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DST"

echo "Installed $LABEL -> $DST (REPO=$REPO)"
echo "Verify:  launchctl list | grep ig-metrics-scrape"
echo "Run now: launchctl kickstart -k gui/$(id -u)/$LABEL"
