#!/bin/bash
# One-shot decision/idempotency payload for Visa Oracle retention.
# Lock, timeout, retry, heartbeat and P0 notification are provided by the
# repository's scripts/cron-wrapper.sh; this payload deliberately duplicates
# none of those mechanisms.

set -euo pipefail

REPO_ROOT="${NUZANTARA_REPO_ROOT:-/Users/nuzantara/nuzantara}"
BACKEND_ROOT="$REPO_ROOT/apps/backend-rag"
PYTHON_BIN="${VISA_ORACLE_PYTHON_BIN:-$BACKEND_ROOT/.venv/bin/python}"
APPLY_MODE="${VISA_ORACLE_RETENTION_APPLY:-false}"

case "$APPLY_MODE" in
  false)
    APPLY_FLAG=false
    ;;
  true)
    APPLY_FLAG=true
    ;;
  *)
    echo "FATAL: VISA_ORACLE_RETENTION_APPLY must be exactly true or false" >&2
    exit 78
    ;;
esac

cd "$BACKEND_ROOT"
if [ "$APPLY_FLAG" = true ]; then
  exec env PYTHONPATH=. "$PYTHON_BIN" -m backend.scripts.visa_engine.retention_worker --apply
fi
exec env PYTHONPATH=. "$PYTHON_BIN" -m backend.scripts.visa_engine.retention_worker
