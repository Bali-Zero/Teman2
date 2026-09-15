#!/usr/bin/env bash
# Build "Claude Seats.app" into ~/Applications and (re)launch it.
#
#   build.sh                 build from this checkout, launch, start at login
#   build.sh --remote pro    also make the widget read Pro's report over `ssh pro`
#                            (machines without the logged-in profiles: M5, Mini)
#   build.sh --local         drop a previous --remote setting
#   build.sh --no-launch     build only
#   build.sh --no-autostart  remove the login LaunchAgent, launch with `open` instead
#
# Bundles scripts/claude_seat_quota.py and FLEET_TOPOLOGY.json into the app so the widget
# never depends on the state of a checkout. Needs swiftc (Xcode or Command Line Tools).
# Ad-hoc signed: local use only.
#
# Autostart is a LaunchAgent, not a Login Item: both fleet Macs rebooted while the widget
# existed only as an app you had to reopen, and it silently stayed dead for days.
# KeepAlive is SuccessfulExit=false — relaunched after a crash or a kill, NOT after «Esci».
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SEAT_WIDGET_REPO:-$HERE/../..}"
APP="${SEAT_WIDGET_APP:-$HOME/Applications/Claude Seats.app}"
SUPPORT="$HOME/Library/Application Support/Claude Seats"
LABEL="com.nuzantara.claude-seats"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
LAUNCH=1
AUTOSTART=1
REMOTE=""
LOCAL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-launch) LAUNCH=0 ;;
        --no-autostart) AUTOSTART=0 ;;
        --remote) REMOTE="$2"; shift ;;
        --local) LOCAL=1 ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
    shift
done

[[ -f "$ROOT/scripts/claude_seat_quota.py" ]] || { echo "no scripts/claude_seat_quota.py under $ROOT" >&2; exit 2; }
[[ -f "$ROOT/FLEET_TOPOLOGY.json" ]] || { echo "no FLEET_TOPOLOGY.json under $ROOT" >&2; exit 2; }

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/scripts"
swiftc -O -target arm64-apple-macos13.0 \
    -framework AppKit -framework SwiftUI \
    "$HERE/main.swift" -o "$APP/Contents/MacOS/ClaudeSeats"
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/scripts/claude_seat_quota.py" "$APP/Contents/Resources/scripts/claude_seat_quota.py"
cp "$ROOT/FLEET_TOPOLOGY.json" "$APP/Contents/Resources/FLEET_TOPOLOGY.json"
codesign --force --sign - "$APP" >/dev/null 2>&1

mkdir -p "$SUPPORT"
if [[ -n "$REMOTE" ]]; then
    printf '%s\n' "$REMOTE" > "$SUPPORT/remote"
    echo "source: via ssh $REMOTE"
elif [[ $LOCAL -eq 1 ]]; then
    rm -f "$SUPPORT/remote"
    echo "source: local"
elif [[ -f "$SUPPORT/remote" ]]; then
    echo "source: via ssh $(cat "$SUPPORT/remote") (kept)"
else
    echo "source: local"
fi

# Stop whatever runs now, under either launcher, before replacing the way it is started.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
pkill -x ClaudeSeats 2>/dev/null || true

if [[ $AUTOSTART -eq 1 ]]; then
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    cat > "$AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>$APP/Contents/MacOS/ClaudeSeats</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key>
    <dict><key>SuccessfulExit</key><false/></dict>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>LimitLoadToSessionType</key><string>Aqua</string>
    <key>ProcessType</key><string>Interactive</string>
    <key>StandardErrorPath</key><string>$HOME/Library/Logs/SeatWidget.err.log</string>
</dict>
</plist>
PLIST
    plutil -lint "$AGENT" >/dev/null
    echo "autostart: $AGENT"
else
    rm -f "$AGENT"
    echo "autostart: off"
fi

if [[ $LAUNCH -eq 1 ]]; then
    if [[ $AUTOSTART -eq 1 ]]; then
        launchctl bootstrap "$DOMAIN" "$AGENT"
    else
        open "$APP"
    fi
fi
echo "built: $APP"
