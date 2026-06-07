#!/usr/bin/env bash
# Launch wrapper for ~/scripts/claude-max-usage-watcher.py.
#
# The watcher imports Playwright. Prefer the backend venv because it is already
# maintained for browser-backed backend tooling on Pro; fall back only when that
# venv is unavailable.
set -euo pipefail

SECRETS="${HOME}/.nuzantara-secrets.env"
if [ -f "${SECRETS}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "${SECRETS}"
    set +a
fi

PY="${CLAUDE_USAGE_WATCHER_PY:-${HOME}/Desktop/nuzantara/apps/backend-rag/.venv/bin/python}"
if [ ! -x "${PY}" ]; then
    PY="${HOME}/.pyenv/versions/3.11.11/bin/python3"
fi
if [ ! -x "${PY}" ]; then
    PY="/usr/bin/python3"
fi

exec "${PY}" "${HOME}/scripts/claude-max-usage-watcher.py" "$@"
