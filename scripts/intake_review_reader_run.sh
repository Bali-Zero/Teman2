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
# (INTAKE_WRITER_ENABLED defaults to 0 — dry-run. FASE 5C go-live: set
#  INTAKE_WRITER_ENABLED=1 in this env-file + kickstart the LaunchAgent.)
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

# Writer flag: SAFE-OFF unless the operator explicitly enables it in the
# 0600 env-file (FASE 5C go-live = add INTAKE_WRITER_ENABLED=1 there + restart;
# no code change). Anything other than an explicit truthy value stays dry-run.
export INTAKE_WRITER_ENABLED="${INTAKE_WRITER_ENABLED:-0}"
if [[ "${INTAKE_WRITER_ENABLED}" == "1" ]]; then
  echo "[intake-review-reader] WARNING: INTAKE_WRITER_ENABLED=1 — approvals COMMIT to the local CRM (FASE 5C live)" >&2
fi

cd "${BACKEND_DIR}"
export PYTHONPATH="${BACKEND_DIR}"

# Venv auto-heal (scar #1546 follow-up / superscar #1 HOME-fork + W81 deploy-worktree
# evaporation): the deploy worktree this wrapper runs from can lose its .venv (re-add,
# sibling-race, GC). PR #1546 healed the WR2 html venv but this reader was left bare:
# a missing-or-dep-incomplete venv made `exec uvicorn` die with
# `ModuleNotFoundError: No module named 'uvicorn'` and KeepAlive crash-looped every
# ThrottleInterval (10s), taking down kita/review (2026-06-17).
#
# Heal BEFORE exec so the FIRST boot after evaporation self-recovers instead of looping:
#   1. venv shell gone   -> recreate it (python3 -m venv).
#   2. deps unimportable  -> pip install -r requirements.txt. CRITICAL: cwd MUST be
#      BACKEND_DIR — requirements.txt has `-e ../../packages/cell-core`, a path-relative
#      editable that only resolves from apps/backend-rag/. We are already cd'd here.
# Idempotent + cheap on the happy path: the import probe short-circuits when deps exist,
# so a healthy boot adds one ~0.1s python invocation and never touches pip.
if [[ ! -x "${VENV_PY}" ]]; then
  echo "[intake-review-reader] WARN: venv python missing at ${VENV_PY} — recreating (scar #1546)" >&2
  if ! python3 -m venv "${BACKEND_DIR}/.venv" >&2; then
    echo "[intake-review-reader] FATAL: venv shell creation failed" >&2
    exit 75  # EX_OSERR
  fi
fi
if ! "${VENV_PY}" -c 'import uvicorn' 2>/dev/null; then
  echo "[intake-review-reader] WARN: uvicorn unimportable — pip install -r requirements.txt (cwd=${BACKEND_DIR}; scar #1546)" >&2
  if ! "${VENV_PY}" -m pip install -r requirements.txt >&2; then
    echo "[intake-review-reader] FATAL: dependency install failed" >&2
    exit 75  # EX_OSERR
  fi
fi

exec "${VENV_PY}" -m uvicorn backend.app.intake_review_reader:app \
  --host "${HOST}" --port "${PORT}" --no-access-log
