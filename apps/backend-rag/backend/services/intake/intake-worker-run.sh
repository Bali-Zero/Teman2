#!/bin/bash
# com.nuzantara.intake-worker runner — FASE 2.
#
# Activates the backend-rag venv and runs the intake worker's OWN internal
# claim->process->sleep loop (backend.services.intake.worker:main). The worker
# loops forever on its own cadence; launchd KeepAlive is ONLY for respawn on a
# hard crash, NOT for driving the cycle (anti retry-storm). On DB-connection
# retry-exhaust the worker exits 0 so launchd respawns it slowly via
# ThrottleInterval instead of flapping.
#
# Single-instance via flock so two launchd ticks can never overlap workers
# (the queue is exactly-once via SKIP LOCKED regardless, but flock avoids
# pointless duplicate processes).
set -euo pipefail

REPO_ROOT="${INTAKE_REPO_ROOT:-/Users/nuzantara/Desktop/nuzantara}"
BACKEND="${REPO_ROOT}/apps/backend-rag"
LOCKFILE="/tmp/com.nuzantara.intake-worker.lock"

exec 9>"${LOCKFILE}"
if ! flock -n 9; then
    echo "[intake-worker] another instance holds the lock; exiting 0" >&2
    exit 0
fi

cd "${BACKEND}"

# Self-heal the venv before trusting it (scar W81b "venv-SKELETON", 2026-06-27).
# The deploy worktree's venv has been left unusable three distinct ways: a dead
# python symlink (pyenv target moved), a corrupt vendored pip, and a skeleton
# with zero deps after a venv recreate that never ran `pip install`. Each kills
# the worker silently with ModuleNotFoundError while launchctl shows green — the
# WhatsApp/Drive intake then stalls for hours with no alarm. One probe covers all
# three: if the venv python can't import asyncpg (the worker's first import), the
# venv is unusable → rebuild it from scratch + install from requirements.txt
# (NOT requirements.lock.txt: its editable cell-core + hashes are mutually
# exclusive in pip). Idempotent: a healthy venv skips straight past this.
VENV_PY=".venv/bin/python"
if ! "${VENV_PY}" -c "import asyncpg" >/dev/null 2>&1; then
    echo "[intake-worker] venv unusable (asyncpg import failed) — rebuilding (scar W81b)" >&2
    PYBASE="$(command -v python3.11 || echo /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3.11)"
    rm -rf .venv
    if ! "${PYBASE}" -m venv .venv; then
        echo "[intake-worker] FATAL: venv create failed with ${PYBASE}" >&2
        exit 78
    fi
    .venv/bin/python -m pip install --quiet --upgrade pip >&2 || true
    if ! .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt >&2; then
        echo "[intake-worker] FATAL: dependency install failed" >&2
        exit 78
    fi
    if ! "${VENV_PY}" -c "import asyncpg" >/dev/null 2>&1; then
        echo "[intake-worker] FATAL: venv still broken after rebuild — not starting" >&2
        exit 78
    fi
    echo "[intake-worker] venv rebuilt OK" >&2
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Import only the scoped WA Mirror delivery env needed for headless Kita upload.
# Do NOT source ~/.wa-mirror.env wholesale: it is not shell-safe and contains
# unrelated values (accounts, labels, DB URLs) that must not shadow the worker
# plist. This mirrors the Qdrant allowlist below and keeps the CRM write key out
# of logs while allowing the delivery leg to authenticate against Fly.
WA_MIRROR_ENV_FILE="${WA_MIRROR_ENV_FILE:-${HOME}/.wa-mirror.env}"
if [[ -f "${WA_MIRROR_ENV_FILE}" ]]; then
    _loaded_wa_delivery_env=()
    for _k in \
        WA_MIRROR_CRM_WRITE_KEY \
        INTAKE_CRM_PUSH_WRITE_KEY \
        INTAKE_CRM_PUSH_BASE_URL \
        INTAKE_CRM_PUSH_ENABLED \
        INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED \
        BZ_INTERNAL_PHONE_NUMBERS; do
        _line="$(grep -E "^${_k}=" "${WA_MIRROR_ENV_FILE}" | tail -1 || true)"
        if [[ -n "${_line}" ]]; then
            _value="${_line#*=}"
            if [[ "${_value}" == \"*\" && "${_value}" == *\" ]]; then
                _value="${_value:1:${#_value}-2}"
            elif [[ "${_value}" == \'*\' && "${_value}" == *\' ]]; then
                _value="${_value:1:${#_value}-2}"
            fi
            export "${_k}=${_value}"
            _loaded_wa_delivery_env+=("${_k}")
        fi
    done
    if [[ ${#_loaded_wa_delivery_env[@]} -gt 0 ]]; then
        echo "[intake-worker] imported scoped WA delivery env: ${_loaded_wa_delivery_env[*]}" >&2
    fi
    unset _k _line _value _loaded_wa_delivery_env
fi

# Inject ONLY the Qdrant credentials from backend-rag/.env. The `validate` stage
# resolves KBLI codes against the live Qdrant store (validate_rules.py), and a
# bare launchd env (no QDRANT_URL/KEY) made it raise
# `RuntimeError: QDRANT_URL / QDRANT_API_KEY not set; cannot validate KBLI` for
# company docs (akta/NIB/OSS/profil_perseroan) — those went to dead while
# non-KBLI docs (passport/ktp/kitas) passed (scar: 5 dead in the 319-adit reocr,
# 2026-06-21). We extract ONLY these two keys — NOT `source .env` wholesale —
# because .env also carries a divergent DATABASE_URL (Fly-proxy :15432) and
# unrelated secrets the worker must NOT inherit (the worker's DB is the plist's
# INTAKE_DATABASE_URL=…/nuzantara_dev; do not let .env shadow it).
if [[ -f .env ]]; then
    for _k in QDRANT_URL QDRANT_API_KEY; do
        _line="$(grep -E "^${_k}=" .env | tail -1 || true)"
        [[ -n "${_line}" ]] && export "${_line?}"
    done
    unset _k _line
fi
export PYTHONPATH="${BACKEND}"
exec python -m backend.services.intake.worker
