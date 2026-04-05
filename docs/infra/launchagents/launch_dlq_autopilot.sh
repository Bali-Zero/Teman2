#!/usr/bin/env bash
# launch_dlq_autopilot.sh — LaunchAgent wrapper that loads secrets from .env
set -euo pipefail

ENV_FILE="$HOME/.nuzantara-secrets.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "FATAL: Missing $ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.pyenv/versions/3.11.11/bin"
exec "$HOME/.pyenv/versions/3.11.11/bin/python3" "$HOME/scripts/dlq_autopilot.py"
