#!/bin/bash
# Wrapper for @UkrBaliVisaAssistant_bot (Pro / launchd).
# Sources the secret env file (token), ensures claude + python on PATH, execs the bot.
set -uo pipefail

# --- secrets (token lives here, NOT in the plist — chmod 600) ---
ENV_FILE="${UKRBALI_ENV_FILE:-$HOME/.ukrbali-bot.env}"
if [ ! -f "$ENV_FILE" ]; then
  echo "[wrapper] FATAL: $ENV_FILE missing. Create it with: echo 'export UKRBALI_BOT_TOKEN=...' > $ENV_FILE && chmod 600 $ENV_FILE" >&2
  exit 78  # EX_CONFIG
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

if [ -z "${UKRBALI_BOT_TOKEN:-}" ]; then
  echo "[wrapper] FATAL: UKRBALI_BOT_TOKEN not set after sourcing $ENV_FILE" >&2
  exit 78
fi

# --- PATH so launchd's minimal env can find claude (Homebrew) + pyenv python ---
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.pyenv/shims:/usr/bin:/bin:$PATH"

# Pick a python3 (stdlib-only script, any 3.x works)
PY="$(command -v python3 || true)"
[ -z "$PY" ] && PY="/usr/bin/python3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$PY" "$SCRIPT_DIR/ukrbali_bot.py"
