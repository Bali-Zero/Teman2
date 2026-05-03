#!/usr/bin/env bash
# compliance_alert_retrain.sh — weekly autotune job (Sun 03:00 WITA).
#
# Adjusts per-category URGENT thresholds based on outcome precision
# observed in the configured window (default: 90 days).
#
# Cron entry on Air:
#   0 3 * * 0  /bin/bash ~/Desktop/nuzantara/scripts/compliance_alert_retrain.sh
#
# Kill-switch: system_settings.compliance_alert_autotune_enabled must be 'true'.
# Safe to run when disabled — retrain() returns {reason: "autotune_disabled"}.
#
# Auth: Max OAuth token via Claude CLI (NOT ANTHROPIC_API_KEY).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../apps/backend-rag"

cd "${BACKEND_DIR}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: no venv found (tried .venv and venv)" >&2
    exit 1
fi

PYTHONPATH=. python -c "
import asyncio
import json
import sys

from backend.app.core.config import settings
from backend.services.compliance.alert_feedback import AlertFeedback
import asyncpg


async def main() -> None:
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
    try:
        result = await AlertFeedback(db_pool=pool).retrain()
        print(json.dumps(result, indent=2))
        if result.get('reason') == 'applied':
            print(f'[retrain] {len(result[\"changed\"])} threshold(s) adjusted.', file=sys.stderr)
        elif result.get('reason') == 'autotune_disabled':
            print('[retrain] kill-switch active — nothing changed.', file=sys.stderr)
        else:
            print('[retrain] no changes needed.', file=sys.stderr)
    finally:
        await pool.close()


asyncio.run(main())
"
