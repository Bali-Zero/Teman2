#!/bin/bash
# install_dropbox_intake.sh — idempotent installer for the Dropbox→Drive intake cron.
# Run ON the target machine (Pro). Re-run after every change to script/plist.
# Prereq: rclone remotes 'dropbox-bayu' + 'gdrive' in ~/.config/rclone/rclone.conf (0600).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_SRC="$REPO_ROOT/scripts/dropbox_intake_sync.sh"
PLIST_SRC="$REPO_ROOT/infra/launchagents/com.balizero.dropbox-intake.plist"
LABEL="com.balizero.dropbox-intake"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -f "$SCRIPT_SRC" ] || { echo "SKIP: $SCRIPT_SRC missing"; exit 0; }
[ -f "$PLIST_SRC" ] || { echo "SKIP: $PLIST_SRC missing"; exit 0; }

mkdir -p "$HOME/scripts" "$HOME/logs"
install -m 0755 "$SCRIPT_SRC" "$HOME/scripts/dropbox-intake-sync.sh"

# No secrets in the plist by design (scar 2026-04-29 plist-secret-leak).
sed "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "OK: $LABEL installed + kickstarted (script: ~/scripts/dropbox-intake-sync.sh)"
