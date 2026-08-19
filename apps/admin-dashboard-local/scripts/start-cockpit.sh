#!/bin/bash
# start-cockpit.sh — launch Zantara Cockpit dev server on port 3100
# Loads HMAC key from ~/.config/zantara-cockpit/hmac.key
# Refuses to start if the passphrase is not configured.

set -euo pipefail

readonly SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
readonly APP_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
readonly LAUNCHER_REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
readonly COCKPIT_OPERATOR_HOME="$HOME"

if [ -z "$LAUNCHER_REPO_ROOT" ] || [ "$APP_ROOT" != "$LAUNCHER_REPO_ROOT/apps/admin-dashboard-local" ]; then
    echo "ERROR: launcher is not inside the expected Git worktree" >&2
    exit 1
fi

cd "$APP_ROOT"

# Source optional local settings first. Protected launcher-derived values and
# the file-backed HMAC key are exported afterwards and cannot be overridden by
# .env.
if [ -f .env ]; then set -a; source .env; set +a; fi

export LOCAL_ONLY=1
export COCKPIT_REPO_ROOT="$LAUNCHER_REPO_ROOT"

CONFIG_DIR="$COCKPIT_OPERATOR_HOME/.config/zantara-cockpit"
PIN_HASH_FILE="$CONFIG_DIR/pin.hash"
HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"

if [ ! -f "$PIN_HASH_FILE" ]; then
    echo "ERROR: passphrase not configured. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

if [ ! -f "$HMAC_KEY_FILE" ]; then
    echo "ERROR: HMAC key missing. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

BACKEND_ROOT="$COCKPIT_REPO_ROOT/apps/backend-rag"
PREVIEW_PYTHON="$BACKEND_ROOT/.venv/bin/python"
PREVIEW_MODULE="$BACKEND_ROOT/backend/services/garuda_flow/internal_preview_cli.py"

if [ ! -x "$PREVIEW_PYTHON" ]; then
    echo "ERROR: GARUDA preview Python missing or not executable: $PREVIEW_PYTHON" >&2
    exit 1
fi

if [ ! -f "$PREVIEW_MODULE" ]; then
    echo "ERROR: GARUDA preview CLI module missing: $PREVIEW_MODULE" >&2
    exit 1
fi

# Verify pool config
if [ -z "${DATABASE_URL_LOCAL:-}" ] && [ -z "${FLY_TUNNEL_URL:-}" ]; then
    echo "WARNING: neither DATABASE_URL_LOCAL nor FLY_TUNNEL_URL set" >&2
fi

echo "Starting Zantara Cockpit on http://127.0.0.1:3100/cockpit"
echo "  COCKPIT_REPO_ROOT=$COCKPIT_REPO_ROOT"
echo "  Passphrase hash file: $PIN_HASH_FILE"
echo

# Read the protected key last so neither the parent shell nor .env can replace
# the file-backed value selected by this launcher.
export COCKPIT_HMAC_KEY="$(<"$HMAC_KEY_FILE")"

exec ./node_modules/.bin/next dev -H 127.0.0.1 -p 3100
