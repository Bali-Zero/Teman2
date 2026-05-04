#!/bin/bash
#
# events_outbox_prune_wrapper.sh
#
# LaunchAgent wrapper for the daily events_outbox prune.
# Sources DATABASE_URL_LOCAL from ~/.nuzantara-secrets.env (Pro-local
# secrets, gitignored). Pro-only — script targets Fly Postgres via the
# fly proxy at 127.0.0.1:15432 (kept up by an existing background
# `fly proxy 15432:5432 -a nuzantara-postgres` PID).
#
# Why a wrapper, not inline EnvironmentVariables in the plist:
#     plist files default to mode 0644 world-readable. Inlining
#     DATABASE_URL would leak the postgres password (cf. cicatrix P0-3
#     secrets-leak incident 2026-04-29). The wrapper sources from
#     ~/.nuzantara-secrets.env (mode 0600) and never writes secrets to
#     the launchd config.
#
# Sprint 6: bootstraps the daily prune at 04:30 WITA on Pro.
#
# Bootstrap procedure (run once):
#     chmod 0755 scripts/events_outbox_prune_wrapper.sh
#     install -m 0755 scripts/events_outbox_prune_wrapper.sh ~/scripts/mata_garuda/
#     install -m 0755 scripts/events_outbox_prune.py ~/scripts/mata_garuda/
#     chmod 0444 infra/launchagents/com.matagaruda.events-outbox-prune.plist
#     install -m 0444 infra/launchagents/com.matagaruda.events-outbox-prune.plist ~/Library/LaunchAgents/
#     launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist
#     launchctl print gui/$(id -u)/com.matagaruda.events-outbox-prune | grep -E "next|state"
#
# Manual fire (verify):
#     launchctl kickstart gui/$(id -u)/com.matagaruda.events-outbox-prune
#     tail -f ~/logs/events-outbox-prune.stdout.log
#
# Uninstall:
#     launchctl bootout gui/$(id -u)/com.matagaruda.events-outbox-prune
#     rm ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist

set -euo pipefail

SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [[ ! -f "${SECRETS_FILE}" ]]; then
    echo "ERROR: secrets file ${SECRETS_FILE} not found — prune aborted" >&2
    exit 2
fi

# shellcheck disable=SC1090
source "${SECRETS_FILE}"

# Prefer DATABASE_URL_LOCAL (fly proxy 127.0.0.1:15432). Fall back to
# DATABASE_URL (flycast) only if local proxy is missing — that path
# requires wireguard, not running by default on Pro.
if [[ -n "${DATABASE_URL_LOCAL:-}" ]]; then
    export DATABASE_URL="${DATABASE_URL_LOCAL}"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL/DATABASE_URL_LOCAL not exported — prune aborted" >&2
    exit 3
fi

# Resolve script dir via BASH_SOURCE so this works regardless of which
# worktree (or Pro-local copy) is checked out at ${HOME}/Desktop/nuzantara.
# This mirrors the pattern of mata_garuda_invalidation_sweep_wrapper.sh.
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="${HOME}/Desktop/nuzantara"
VENV_PY="${REPO_ROOT}/apps/backend-rag/.venv/bin/python3"
if [[ -x "${VENV_PY}" ]]; then
    PYTHON="${VENV_PY}"
else
    PYTHON="/usr/bin/python3"
fi

cd "${REPO_ROOT}"
exec "${PYTHON}" "${SCRIPT_DIR}/events_outbox_prune.py" "$@"
