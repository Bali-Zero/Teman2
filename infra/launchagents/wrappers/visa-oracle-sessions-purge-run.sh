#!/bin/bash
# One-shot payload for the Visa Oracle SESSIONS purge (migration 317's
# enforcement arm — distinct from visa-oracle-retention-run.sh, which covers
# visa DECISIONS + evaluate-idempotency, not sessions).
# Lock, timeout, retry, heartbeat and P0 notification are provided by the
# repository's scripts/cron-wrapper.sh; this payload deliberately duplicates
# none of those mechanisms.

set -euo pipefail

REPO_ROOT="${NUZANTARA_REPO_ROOT:-/Users/nuzantara/nuzantara}"
BACKEND_ROOT="$REPO_ROOT/apps/backend-rag"
PYTHON_BIN="${VISA_ORACLE_PYTHON_BIN:-$BACKEND_ROOT/.venv/bin/python}"
APPLY_MODE="${VISA_ORACLE_SESSIONS_PURGE_APPLY:-false}"

case "$APPLY_MODE" in
  false)
    APPLY_FLAG=false
    ;;
  true)
    APPLY_FLAG=true
    ;;
  *)
    echo "FATAL: VISA_ORACLE_SESSIONS_PURGE_APPLY must be exactly true or false" >&2
    exit 78
    ;;
esac

cd "$BACKEND_ROOT"
if [ "$APPLY_FLAG" = true ]; then
  exec env PYTHONPATH=. "$PYTHON_BIN" -m backend.scripts.visa_engine.visa_oracle_sessions_purge_worker --apply
fi
exec env PYTHONPATH=. "$PYTHON_BIN" -m backend.scripts.visa_engine.visa_oracle_sessions_purge_worker
