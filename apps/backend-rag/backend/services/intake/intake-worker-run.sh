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
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="${BACKEND}"
exec python -m backend.services.intake.worker
