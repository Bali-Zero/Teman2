#!/bin/bash
# Install metabolic rollup LaunchAgent on Pro.
# Idempotent: safe to run multiple times (bootout before bootstrap).
#
# Organ: scripts/ install → produce LaunchAgent Pro
# Consume: nothing

set -euo pipefail

if [ "$(whoami)" != "nuzantara" ]; then
    echo "ERR: this script must run on Pro (whoami=nuzantara, got $(whoami))" >&2
    exit 1
fi

REPO="/Users/nuzantara/Desktop/nuzantara"
PLIST_SRC="$REPO/scripts/launchd/com.cell.metabolic-rollup.pro.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.cell.metabolic-rollup.plist"
LABEL="com.cell.metabolic-rollup"
DOMAIN="gui/$(id -u)"

if [ ! -f "$PLIST_SRC" ]; then
    echo "ERR: template plist missing: $PLIST_SRC" >&2
    exit 1
fi

# Ensure wrapper is executable (commit-safe: test + chmod)
WRAPPER="$REPO/scripts/metabolic_rollup_pro.sh"
if [ ! -x "$WRAPPER" ]; then
    chmod +x "$WRAPPER"
fi

# 1. Place plist
mkdir -p "$(dirname "$PLIST_DST")"
cp "$PLIST_SRC" "$PLIST_DST"
echo "[install] copied plist to $PLIST_DST"

# 2. Unload if already loaded (idempotence). Scoped to label only — does NOT affect other agents.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

# 3. Load
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
launchctl enable "$DOMAIN/$LABEL"

# 4. Verify
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "[install] OK: $LABEL loaded in $DOMAIN"
else
    echo "ERR: launchctl print failed for $DOMAIN/$LABEL" >&2
    exit 1
fi
