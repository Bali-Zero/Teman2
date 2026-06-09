#!/bin/bash
# intake_review_reader_run.sh — LaunchAgent wrapper for the Pro-side intake-review reader.
#
# WHY a wrapper (W65 / P0-3 scar): secrets must NOT live in the plist (world-readable plist
# leaks are a recurring P0). This wrapper sources a 0600 env-file, then execs uvicorn. The
# plist only points at this script; no secret value ever touches git or the plist.
#
# Env-file (chmod 0600, owner nuzantara only) — create it on the Pro, NEVER commit it:
#   ~/.cell-bridge-state/intake-review-reader.env
# with keys:
#   JWT_SECRET_KEY=<the Fly JWT_SECRET_KEY secret — must match Fly for cookie/Bearer JWT>
#   API_KEYS=<any non-empty value; settings requires it, reader is JWT-only in practice>
#   INTAKE_REVIEW_DATABASE_URL=postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev
#   INTAKE_REVIEW_BRIDGE_SECRET=<shared X-Bridge-Auth secret, added by the Fly proxy>
# (INTAKE_WRITER_ENABLED is forced to 0 below — approvals stay dry-run.)
set -euo pipefail

REPO_ROOT="${INTAKE_REVIEW_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
BACKEND_DIR="${REPO_ROOT}/apps/backend-rag"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
ENV_FILE="${INTAKE_REVIEW_ENV_FILE:-${HOME}/.cell-bridge-state/intake-review-reader.env}"
HOST="127.0.0.1"
PORT="18795"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[intake-review-reader] FATAL: env-file not found: ${ENV_FILE}" >&2
  echo "[intake-review-reader] create it 0600 with JWT_SECRET_KEY/API_KEYS/INTAKE_REVIEW_DATABASE_URL/INTAKE_REVIEW_BRIDGE_SECRET" >&2
  exit 78  # EX_CONFIG
fi

# Refuse a world-readable env-file (defence against the recurring plist-secret-644 class).
PERMS="$(stat -f '%Lp' "${ENV_FILE}" 2>/dev/null || echo '???')"
if [[ "${PERMS}" != "600" && "${PERMS}" != "400" ]]; then
  echo "[intake-review-reader] FATAL: ${ENV_FILE} is mode ${PERMS}, expected 600/400. chmod 600 it." >&2
  exit 78
fi

# Source the secrets, exporting every assignment.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# P2: approvals dry-run regardless of what the env-file says.
export INTAKE_WRITER_ENABLED=0

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}"

exec "${VENV_PY}" -m uvicorn backend.app.intake_review_reader:app \
  --host "${HOST}" --port "${PORT}" --no-access-log
