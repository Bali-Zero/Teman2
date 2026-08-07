#!/bin/bash
#
# mata_garuda_invalidation_sweep_wrapper.sh
#
# LaunchAgent wrapper for the mata-garuda TTL invalidation sweep.
# Sources DATABASE_URL from ~/.nuzantara-secrets.env (Pro-local secrets
# file, gitignored). Pro-only — the sweep targets the Pro-local
# PostgreSQL (Fly Postgres is reached via flycast from Pro, not from
# the api machines).
#
# Why a wrapper, not inline EnvironmentVariables in the plist:
#   plist files are world-readable mode 0644 by default. Inlining
#   DATABASE_URL would leak the postgres password into a file readable
#   by every Mac user (cf. cicatrix P0-3 secrets-leak incident
#   2026-04-29 where 5 plist files leaked GH_TOKEN/FIREWORKS_API_KEY
#   etc.). The wrapper sources from ~/.nuzantara-secrets.env (mode 0600)
#   and never writes it to the launchd config.
#
# Sprint 4 wiring (S4-7): bootstraps the daily sweep at 04:13 WITA on
# Pro. Bootstrap procedure:
#
#   chmod 0755 scripts/mata_garuda_invalidation_sweep_wrapper.sh
#   chmod 0444 infra/launchagents/com.matagaruda.invalidation-sweep.plist
#   install -m 0444 infra/launchagents/com.matagaruda.invalidation-sweep.plist \
#       ~/Library/LaunchAgents/
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.invalidation-sweep.plist
#   launchctl print gui/$(id -u)/com.matagaruda.invalidation-sweep | grep next
#
# Manual fire (verify):
#   launchctl kickstart gui/$(id -u)/com.matagaruda.invalidation-sweep
#   tail -f ~/logs/mata-garuda-invalidation-sweep.stdout.log
#

set -euo pipefail

# Source DATABASE_URL (and any other env the sweep script may need)
# from the Pro-local secrets file. The file MUST exist and contain
# DATABASE_URL=postgres://... — fail-fast if absent.
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [[ ! -f "${SECRETS_FILE}" ]]; then
    echo "ERROR: secrets file ${SECRETS_FILE} not found — sweep aborted" >&2
    exit 2
fi

# shellcheck disable=SC1090
source "${SECRETS_FILE}"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL not exported by ${SECRETS_FILE} — sweep aborted" >&2
    exit 3
fi

# Pro-only routing: prefer DATABASE_URL_LOCAL (127.0.0.1:15432 → fly proxy
# to nuzantara-postgres.flycast). The flycast hostname only resolves
# through wireguard, which we don't run as a daemon — instead we keep a
# `fly proxy 15432:5432 -a nuzantara-postgres` process up on Pro. Hitting
# the proxy port avoids the DNS dependency. Falls back to DATABASE_URL
# (flycast direct) if DATABASE_URL_LOCAL is not exported, in which case
# wireguard must be active.
if [[ -n "${DATABASE_URL_LOCAL:-}" ]]; then
    export DATABASE_URL="${DATABASE_URL_LOCAL}"
fi

# Find the venv python — sweep imports asyncpg lazily; fall back to
# system python3 if venv is missing (asyncpg import will then fail
# loud at runtime, captured in the launchd stderr log).
#
# Pro-local copy: resolve script directory via BASH_SOURCE so this works
# regardless of which branch is checked out at ${HOME}/nuzantara.
# REPO_ROOT used only for venv lookup + cwd.
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="${HOME}/nuzantara"
VENV_PY="${REPO_ROOT}/apps/backend-rag/.venv/bin/python3"
if [[ -x "${VENV_PY}" ]]; then
    PYTHON="${VENV_PY}"
else
    PYTHON="/usr/bin/python3"
fi

cd "${REPO_ROOT}"
exec "${PYTHON}" "${SCRIPT_DIR}/mata_garuda_invalidation_sweep.py" "$@"
