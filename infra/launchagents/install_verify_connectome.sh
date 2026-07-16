#!/bin/bash
# install_verify_connectome.sh — idempotent installer for the connectome
# drift-verifier LaunchAgent (authorized by Antonello 2026-06-13).
#
# Schedule by machine:
#   Pro (user nuzantara) : DAILY  07:30 WITA — canonical guardian, runs from
#                          ~/nuzantara-deploy (hourly-synced, W71 rule)
#   M5  (user balizero)  : WEEKLY Monday 08:30 WITA — covers m5-local edges
#                          the Pro cannot probe (no ssh map to M5)
#
# The plist is GENERATED here (not static) because $HOME differs per machine
# (Pro /Users/nuzantara vs M5 /Users/balizero — W50/W51/W52 path-drift class).
# Re-run after script changes: it bootout+bootstraps cleanly.
# /bin/bash 3.2-compatible.
set -uo pipefail

LABEL="com.nuzantara.verify-connectome"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/logs"
mkdir -p "$LOG_DIR"

if [[ "$(whoami)" == "balizero" ]]; then
    REPO_ROOT="$HOME/nuzantara"
    # Weekly: Monday 08:30 (Weekday 1)
    CALENDAR='<dict>
            <key>Weekday</key><integer>1</integer>
            <key>Hour</key><integer>8</integer>
            <key>Minute</key><integer>30</integer>
        </dict>'
else
    REPO_ROOT="$HOME/nuzantara-deploy"
    # Daily 07:30
    CALENDAR='<dict>
            <key>Hour</key><integer>7</integer>
            <key>Minute</key><integer>30</integer>
        </dict>'
fi

RUNNER="$REPO_ROOT/scripts/verify_connectome_run.sh"
if [[ ! -f "$RUNNER" ]]; then
    echo "[install] SKIP: runner not found at $RUNNER (checkout not synced yet?)" >&2
    exit 0
fi

cat > "$DEST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>REPO_ROOT</key><string>$REPO_ROOT</string>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StartCalendarInterval</key>
    $CALENDAR
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>$LOG_DIR/verify-connectome.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/verify-connectome.log</string>
</dict>
</plist>
PLIST
chmod 0400 "$DEST"

UID_VAL="$(id -u)"
launchctl bootout "gui/$UID_VAL" "$DEST" 2>/dev/null || true
launchctl bootstrap "gui/$UID_VAL" "$DEST"
RC=$?
if [[ $RC -eq 0 ]]; then
    echo "[install] $LABEL armed (repo=$REPO_ROOT, $( [[ $(whoami) == balizero ]] && echo 'weekly Mon 08:30' || echo 'daily 07:30' ))"
else
    echo "[install] ERROR: bootstrap failed rc=$RC" >&2
fi
exit $RC
