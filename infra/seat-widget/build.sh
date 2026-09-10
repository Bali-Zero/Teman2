#!/usr/bin/env bash
# Build "Claude Seats.app" into ~/Applications and (re)launch it.
#
#   build.sh                 build from this checkout, launch
#   build.sh --remote pro    also make the widget measure over `ssh pro` (machines
#                            without the logged-in profiles: M5, Mini)
#   build.sh --local         drop a previous --remote setting
#   build.sh --no-launch     build only
#
# Bundles scripts/claude_seat_quota.py and FLEET_TOPOLOGY.json into the app so the widget
# never depends on the state of a checkout. Needs swiftc (Xcode or Command Line Tools).
# Ad-hoc signed: local use only.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SEAT_WIDGET_REPO:-$HERE/../..}"
APP="${SEAT_WIDGET_APP:-$HOME/Applications/Claude Seats.app}"
SUPPORT="$HOME/Library/Application Support/Claude Seats"
LAUNCH=1
REMOTE=""
LOCAL=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-launch) LAUNCH=0 ;;
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

if [[ $LAUNCH -eq 1 ]]; then
    pkill -x ClaudeSeats 2>/dev/null || true
    open "$APP"
fi
echo "built: $APP"
