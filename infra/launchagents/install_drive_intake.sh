#!/bin/bash
# install_drive_intake.sh <scope-folder-id> — installer for the Drive→intake drain cron.
#
# Run ON the Pro, AFTER the Dropbox backfill has completed (arming during the
# backfill would flood intake_queue with the historical corpus). The first run
# seeds the changes cursor at "now" → only files added from arming onward are
# ingested (historical smistamento happens via targeted campaigns, not here).
#
# <scope-folder-id> = Drive folder id of Dropbox-Intake/ — find it with:
#   rclone lsf gdrive: --dirs-only --format "ip" | grep Dropbox-Intake
set -euo pipefail

SCOPE_ID="${1:-}"
[ -n "$SCOPE_ID" ] || { echo "usage: $0 <scope-folder-id>"; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC="$REPO_ROOT/infra/launchagents/com.balizero.drive-intake-drain.plist"
SCRIPT="$REPO_ROOT/scripts/drive_intake_drain.py"
VENV_PYTHON="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
LABEL="com.balizero.drive-intake-drain"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -f "$PLIST_SRC" ] || { echo "SKIP: $PLIST_SRC missing"; exit 0; }
[ -f "$SCRIPT" ] || { echo "SKIP: $SCRIPT missing"; exit 0; }
[ -x "$VENV_PYTHON" ] || { echo "SKIP: venv python missing at $VENV_PYTHON"; exit 0; }

mkdir -p "$HOME/logs"

# No secrets in the plist by design (scar 2026-04-29) — the folder id is an
# identifier, not a credential.
sed -e "s|__HOME__|$HOME|g" \
    -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
    -e "s|__SCOPE_FOLDER_ID__|$SCOPE_ID|g" \
    "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "OK: $LABEL installed + kickstarted (scope=$SCOPE_ID, repo=$REPO_ROOT)"
