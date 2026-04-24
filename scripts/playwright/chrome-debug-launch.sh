#!/usr/bin/env bash
# Launch Chrome with remote debugging port, using your Default profile.
# Playwright can then attach via CDP and Cloudflare sees a real Chrome session.
#
# Usage:
#   bash scripts/playwright/chrome-debug-launch.sh
# Then from another terminal:
#   python3 scripts/playwright/playwright_explore.py
set -e
PROFILE_DIR="$HOME/.nuzantara/playwright-profiles/canva"
mkdir -p "$PROFILE_DIR"

# Close any existing Chrome first (remote debug only works with single instance)
pkill -x "Google Chrome" 2>/dev/null || true
sleep 1

open -na "Google Chrome" --args \
    --remote-debugging-port=9222 \
    --user-data-dir="$PROFILE_DIR" \
    --disable-blink-features=AutomationControlled \
    --no-first-run \
    --no-default-browser-check

echo "Chrome launched with remote debugging on :9222"
echo "Profile: $PROFILE_DIR"
echo ""
echo "Next: from another terminal, run Playwright attach:"
echo "  cd ~/Desktop/nuzantara && python3 scripts/playwright/playwright_explore.py canva"
