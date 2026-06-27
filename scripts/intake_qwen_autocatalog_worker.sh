#!/bin/bash
# Run the WhatsApp intake Qwen autocatalog worker from the Pro.
#
# This launcher is intentionally proposal-only: it can drain OCR/classify/route
# backlog into review proposals, but it cannot write to CRM/Kita. Auto-attach is
# a separate, explicitly gated step after the proposal counts have been checked.
set -euo pipefail

if [[ "$(hostname)" != "Nuzantara" ]]; then
    echo "[intake-qwen] run this on the Pro (hostname=Nuzantara); from Air-M5 use: ssh pro '...'" >&2
    exit 2
fi

REPO_ROOT="${INTAKE_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
BACKEND="${REPO_ROOT}/apps/backend-rag"
VENV="${INTAKE_BACKEND_VENV:-${BACKEND}/.venv}"
if [[ ! -d "${VENV}" ]]; then
    VENV="/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv"
fi

MINI_ALIAS="${INTAKE_QWEN_MINI_ALIAS:-mini}"
MINI_TUNNEL_PORT="${INTAKE_QWEN_MINI_TUNNEL_PORT:-11435}"
USE_MINI_TUNNEL="${INTAKE_QWEN_USE_MINI_TUNNEL:-1}"
OLLAMA_URL="${INTAKE_OLLAMA_URL:-http://127.0.0.1:${MINI_TUNNEL_PORT}}"

if [[ "${USE_MINI_TUNNEL}" == "1" ]]; then
    if ! curl -fsS --max-time 3 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
        echo "[intake-qwen] opening Pro->Mini Ollama tunnel on 127.0.0.1:${MINI_TUNNEL_PORT}" >&2
        ssh -fN -o ExitOnForwardFailure=yes \
            -L "127.0.0.1:${MINI_TUNNEL_PORT}:127.0.0.1:11434" \
            "${MINI_ALIAS}"
    fi
    curl -fsS --max-time 5 "${OLLAMA_URL}/api/tags" >/dev/null
fi

cd "${BACKEND}"
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

if [[ -f .env ]]; then
    for _k in QDRANT_URL QDRANT_API_KEY; do
        _line="$(grep -E "^${_k}=" .env | tail -1 || true)"
        [[ -n "${_line}" ]] && export "${_line?}"
    done
    unset _k _line
fi

export INTAKE_DATABASE_URL="${INTAKE_DATABASE_URL:-postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev}"
export INTAKE_OLLAMA_URL="${OLLAMA_URL}"
export INTAKE_TEXT_LLM_CLASSIFY_ENABLED="${INTAKE_TEXT_LLM_CLASSIFY_ENABLED:-1}"
export INTAKE_TEXT_LLM_MODEL="${INTAKE_TEXT_LLM_MODEL:-qwen3.5:9b}"
export INTAKE_TEXT_LLM_MIN_CHARS="${INTAKE_TEXT_LLM_MIN_CHARS:-100}"
export INTAKE_TEXT_LLM_TIMEOUT_SECONDS="${INTAKE_TEXT_LLM_TIMEOUT_SECONDS:-60}"
export INTAKE_PROPOSAL_ONLY_SKIP_EXTRACT="${INTAKE_PROPOSAL_ONLY_SKIP_EXTRACT:-1}"
export INTAKE_SOURCE_FILTER="${INTAKE_SOURCE_FILTER:-whatsapp}"
export INTAKE_PIPELINE_VERSION_FILTER="${INTAKE_PIPELINE_VERSION_FILTER:-v2.2-qwen-text-autocatalog}"
export INTAKE_AUTO_ATTACH_ENABLED=0
export INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=0
export INTAKE_WRITER_ENABLED=0
export INTAKE_CONCURRENCY="${INTAKE_CONCURRENCY:-1}"
export INTAKE_POLL_INTERVAL_SECONDS="${INTAKE_POLL_INTERVAL_SECONDS:-1}"
export INTAKE_LEASE_TTL_SECONDS="${INTAKE_LEASE_TTL_SECONDS:-300}"
export INTAKE_TRANSIENT_BACKOFF_SECONDS="${INTAKE_TRANSIENT_BACKOFF_SECONDS:-3}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${BACKEND}"

echo "[intake-qwen] repo=${REPO_ROOT} ollama=${INTAKE_OLLAMA_URL} pipeline=${INTAKE_PIPELINE_VERSION_FILTER} writer=off auto_attach=off" >&2

if [[ -n "${INTAKE_QWEN_RUN_SECONDS:-}" ]]; then
    TIMEOUT_BIN="${INTAKE_QWEN_TIMEOUT_BIN:-gtimeout}"
    if ! command -v "${TIMEOUT_BIN}" >/dev/null 2>&1; then
        echo "[intake-qwen] ${TIMEOUT_BIN} not found; unset INTAKE_QWEN_RUN_SECONDS or install coreutils on Pro" >&2
        exit 2
    fi
    exec "${TIMEOUT_BIN}" "${INTAKE_QWEN_RUN_SECONDS}" python -m backend.services.intake.worker
fi

exec python -m backend.services.intake.worker
