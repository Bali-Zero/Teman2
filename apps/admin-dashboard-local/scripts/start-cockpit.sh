#!/bin/bash
# start-cockpit.sh — launch Zantara Cockpit dev server on port 3100
# Loads HMAC key from ~/.config/zantara-cockpit/hmac.key
# Refuses to start if PIN not configured.

set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_DIR="$HOME/.config/zantara-cockpit"
PIN_HASH_FILE="$CONFIG_DIR/pin.hash"
HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"

if [ ! -f "$PIN_HASH_FILE" ]; then
    echo "ERROR: PIN not configured. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

if [ ! -f "$HMAC_KEY_FILE" ]; then
    echo "ERROR: HMAC key missing. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

export LOCAL_ONLY=1
export COCKPIT_HMAC_KEY=$(cat "$HMAC_KEY_FILE")
export COCKPIT_REPO_ROOT="${COCKPIT_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"

# Source DB envs
if [ -f .env ]; then set -a; source .env; set +a; fi

# Verify pool config
if [ -z "${DATABASE_URL_LOCAL:-}" ] && [ -z "${FLY_TUNNEL_URL:-}" ]; then
    echo "WARNING: neither DATABASE_URL_LOCAL nor FLY_TUNNEL_URL set" >&2
fi

echo "Starting Zantara Cockpit on http://localhost:3100/cockpit"
echo "  COCKPIT_REPO_ROOT=$COCKPIT_REPO_ROOT"
echo "  PIN hash file: $PIN_HASH_FILE"
echo

npx next dev -p 3100
