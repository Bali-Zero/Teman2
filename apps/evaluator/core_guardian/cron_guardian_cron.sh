#!/usr/bin/env bash
set -uo pipefail

# Resolve REPO from this script's location — portable across Pro (.../Desktop/nuzantara)
# and Air (.../Projects/nuzantara) without hardcoding machine-specific paths.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Venv naming differs: Pro uses .venv, Air uses venv. Prefer .venv, fallback to venv.
if [ -x "$REPO/apps/backend-rag/.venv/bin/python3" ]; then
    PY="$REPO/apps/backend-rag/.venv/bin/python3"
elif [ -x "$REPO/apps/backend-rag/venv/bin/python3" ]; then
    PY="$REPO/apps/backend-rag/venv/bin/python3"
else
    echo "[cron_guardian_cron.sh] FATAL: no backend-rag venv found at $REPO/apps/backend-rag/{.venv,venv}" >&2
    exit 1
fi

GUARDIAN="$REPO/apps/evaluator/core_guardian/cron_guardian.py"

cd "$REPO"
exec "$PY" "$GUARDIAN" "$@"
