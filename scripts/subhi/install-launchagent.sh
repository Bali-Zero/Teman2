#!/usr/bin/env bash
# install-launchagent.sh — install/reinstall the Subhi mirror+publish LaunchAgent.
# Reference: cicatrix-scars 2026-04-29 plist corruption — install with mode 0444.
set -euo pipefail

SRC=/Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.subhi-mirror-and-publish.daily.plist
DST=/Users/nuzantara/Library/LaunchAgents/com.balizero.subhi-mirror-and-publish.daily.plist
LABEL=com.balizero.subhi-mirror-and-publish.daily

# Validate source
plutil -lint "$SRC" || { echo "Plist invalid"; exit 1; }

# Unload if already loaded
if launchctl print "gui/$(id -u)/$LABEL" &>/dev/null; then
  echo "Unloading existing $LABEL..."
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
fi

# Atomic install with read-only mode (cf. cicatrix-scars)
chmod u+w "$DST" 2>/dev/null || true
install -m 0444 "$SRC" "$DST"

# Bootstrap into launchd
launchctl bootstrap "gui/$(id -u)" "$DST"

# Verify
sleep 1
if launchctl print "gui/$(id -u)/$LABEL" 2>&1 | grep -qE "state = (waiting|not running)"; then
  echo "✓ Installed $LABEL — next fire at 04:00 WITA daily"
  echo "  Manual test: bash $SRC"
  echo "  Logs: ~/logs/subhi-mirror-and-publish.log"
else
  echo "✗ Install verification failed — printing state:"
  launchctl print "gui/$(id -u)/$LABEL" 2>&1 | head -20
  exit 1
fi
