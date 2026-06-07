#!/usr/bin/env bash
set -euo pipefail

SECRETS_FILE="${NUZANTARA_SECRETS:-${HOME}/.nuzantara-secrets.env}"
if [[ -f "${SECRETS_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${SECRETS_FILE}"
  set +a
fi

if [[ -z "${BRIDGE_SKILLS_API_KEY:-}" ]]; then
  echo "[skills_bridge_launcher] BRIDGE_SKILLS_API_KEY missing in ${SECRETS_FILE}" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CELL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${CELL_PYTHON:-${CELL_ROOT}/.venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

exec "${PYTHON_BIN}" -u "${SCRIPT_DIR}/skills_bridge_consumer.py"
