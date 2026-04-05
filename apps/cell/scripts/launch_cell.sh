#!/usr/bin/env bash
# launch_cell.sh — LaunchAgent wrapper that loads secrets from .env
# Called by com.cell.organism.plist instead of python directly
set -euo pipefail

CELL_DIR="/Users/nuzantara/Desktop/nuzantara/apps/cell"
ENV_FILE="$CELL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "FATAL: Missing $ENV_FILE — create it from .env.example" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

export PYTHONPATH="$CELL_DIR"
exec "$CELL_DIR/.venv/bin/python" -m cell.main
