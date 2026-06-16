#!/bin/bash
# install_drive_intake.sh <scope-folder-id> [sa-file] — installer for the Drive→intake drain cron.
#
# Run ON the Pro, AFTER the Dropbox backfill has completed (arming during the
# backfill would flood intake_queue with the historical corpus). The first run
# seeds the changes cursor at "now" → only files added from arming onward are
# ingested (historical smistamento happens via targeted campaigns, not here).
#
# <scope-folder-id> = Drive folder id of Dropbox-Intake/ — find it with:
#   rclone lsf gdrive: --dirs-only --format "ip" | grep Dropbox-Intake
# [sa-file] = path to the Drive service-account JSON (0600). Defaults to
#   $HOME/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json
#   (override via arg 2 or $INTAKE_SA_FILE). Read at runtime by the wrapper —
#   never inlined in the plist (cicatrix #4).
set -euo pipefail

SCOPE_ID="${1:-}"
[ -n "$SCOPE_ID" ] || { echo "usage: $0 <scope-folder-id> [sa-file]"; exit 2; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC="$REPO_ROOT/infra/launchagents/com.balizero.drive-intake-drain.plist"
SCRIPT="$REPO_ROOT/scripts/drive_intake_drain.py"
WRAPPER="$REPO_ROOT/scripts/drive-intake-drain-run.sh"
VENV_PYTHON="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
SA_FILE="${2:-${INTAKE_SA_FILE:-$HOME/.config/nuzantara/service-accounts/nuzantara-google-drive-sa-20260530.json}}"
LABEL="com.balizero.drive-intake-drain"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -f "$PLIST_SRC" ] || { echo "SKIP: $PLIST_SRC missing"; exit 0; }
[ -f "$SCRIPT" ] || { echo "SKIP: $SCRIPT missing"; exit 0; }
[ -f "$WRAPPER" ] || { echo "SKIP: $WRAPPER missing"; exit 0; }
[ -x "$VENV_PYTHON" ] || { echo "SKIP: venv python missing at $VENV_PYTHON"; exit 0; }
# Do NOT arm a blind drain: the SA file must be present + readable, else the
# wrapper would exit 78 every tick (cron theater — superscar #2).
[ -r "$SA_FILE" ] || { echo "SKIP: SA file unreadable at $SA_FILE (set arg 2 or \$INTAKE_SA_FILE)"; exit 0; }

chmod +x "$WRAPPER"
mkdir -p "$HOME/logs"

# No secrets in the plist by design (scar 2026-04-29): the folder id and the SA
# FILE PATH are identifiers, not credentials. The SA JSON itself is read from
# the 0600 file at runtime by the wrapper (cicatrix #4).
sed -e "s|__HOME__|$HOME|g" \
    -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
    -e "s|__SA_FILE__|$SA_FILE|g" \
    -e "s|__SCOPE_FOLDER_ID__|$SCOPE_ID|g" \
    "$PLIST_SRC" > "$PLIST_DST"
chmod 0644 "$PLIST_DST"
plutil -lint "$PLIST_DST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl kickstart "gui/$(id -u)/$LABEL"

echo "OK: $LABEL installed + kickstarted (scope=$SCOPE_ID, repo=$REPO_ROOT, sa=$SA_FILE)"
