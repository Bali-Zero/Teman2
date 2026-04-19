#!/usr/bin/env bash
set -uo pipefail

REPO="/Users/nuzantara/Desktop/nuzantara"
PY="$REPO/apps/backend-rag/.venv/bin/python3"
GUARDIAN="$REPO/apps/evaluator/core_guardian/cron_guardian.py"

cd "$REPO"
exec "$PY" "$GUARDIAN" "$@"
