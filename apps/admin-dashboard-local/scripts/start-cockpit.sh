#!/bin/bash
# start-cockpit.sh — launch Zantara Cockpit dev server on port 3100
# Loads separate audit-HMAC and session keys from ~/.config/zantara-cockpit/
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
# both file-backed keys are exported afterwards and cannot be overridden by
# .env.
if [ -f .env ]; then set -a; source .env; set +a; fi

export LOCAL_ONLY=1
export COCKPIT_REPO_ROOT="$LAUNCHER_REPO_ROOT"

CONFIG_DIR="$COCKPIT_OPERATOR_HOME/.config/zantara-cockpit"
PIN_HASH_FILE="$CONFIG_DIR/pin.hash"
HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"
SESSION_KEY_FILE="$CONFIG_DIR/session.key"

if [ ! -f "$PIN_HASH_FILE" ]; then
    echo "ERROR: passphrase not configured. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

if [ ! -f "$HMAC_KEY_FILE" ]; then
    echo "ERROR: HMAC key missing. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

if [ ! -f "$SESSION_KEY_FILE" ]; then
    echo "ERROR: session key missing. Run: bash scripts/setup-cockpit-pin.sh" >&2
    exit 1
fi

for PROTECTED_KEY_FILE in "$HMAC_KEY_FILE" "$SESSION_KEY_FILE"; do
    if [ ! -s "$PROTECTED_KEY_FILE" ] || [ "$(stat -f '%Lp' "$PROTECTED_KEY_FILE")" != "600" ]; then
        echo "ERROR: protected cockpit key must be non-empty with mode 0600: $PROTECTED_KEY_FILE" >&2
        exit 1
    fi
done

BACKEND_ROOT="$COCKPIT_REPO_ROOT/apps/backend-rag"
PREVIEW_PYTHON="$BACKEND_ROOT/.venv/bin/python"
PREVIEW_MODULE="$BACKEND_ROOT/backend/services/garuda_flow/internal_preview_cli.py"
PREVIEW_CWD="$BACKEND_ROOT/backend/services/garuda_flow"

if [ ! -x "$PREVIEW_PYTHON" ]; then
    echo "ERROR: GARUDA preview Python missing or not executable: $PREVIEW_PYTHON" >&2
    exit 1
fi

if [ ! -f "$PREVIEW_MODULE" ]; then
    echo "ERROR: GARUDA preview CLI module missing: $PREVIEW_MODULE" >&2
    exit 1
fi


if [ -e "$PREVIEW_CWD/.env" ] || [ -L "$PREVIEW_CWD/.env" ]; then
    echo "ERROR: GARUDA preview cwd must not contain a .env file: $PREVIEW_CWD" >&2
    exit 1
fi

# Verify pool config
if [ -z "${DATABASE_URL_LOCAL:-}" ] && [ -z "${FLY_TUNNEL_URL:-}" ]; then
    echo "INFO: no database configured; GARUDA preview/login remain available, but DB-backed widgets will be unavailable" >&2
fi

echo "Starting Zantara Cockpit on http://127.0.0.1:3100/cockpit"
echo "  COCKPIT_REPO_ROOT=$COCKPIT_REPO_ROOT"
echo "  Passphrase hash file: $PIN_HASH_FILE"
echo

# Read both protected keys last so neither the parent shell nor .env can
# replace the file-backed values selected by this launcher. The audit key is
# intentionally stable; setup rotates only the session key.
export COCKPIT_HMAC_KEY="$(<"$HMAC_KEY_FILE")"
export COCKPIT_SESSION_KEY="$(<"$SESSION_KEY_FILE")"

exec ./node_modules/.bin/next dev -H 127.0.0.1 -p 3100
