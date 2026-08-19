#!/bin/sh
# wa-codex-broker-wrapper.sh — launchd payload for com.balizero.wa-codex-broker.
#
# Runs as the login-less user `zantara-codex` on Pro (spec §4.1,
# research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md). The
# LIVE copy is /Users/zantara-codex/bin/wa-codex-broker-wrapper.sh, placed
# there by scripts/provision_zantara_codex.sh; the pair is declared in
# infra/home-fork/declared-pairs.json (superscar #1 — re-run provisioning
# after changing this file, the merge alone leaves the live copy stale).
#
# Shape notes (scar-family antidotes, load-bearing):
# - `exec` into the daemon's REAL blocking loop under KeepAlive (family #7:
#   launchd monitors the python process itself, no restart cycling).
# - Guarded env-file source — never a bare `. file || true` under errexit
#   (W108: sh treats a failed `.` as a special-builtin exit; the guard
#   must come BEFORE the source, as an if).
# - Absolute interpreter path (W108: a PATH-resolved python is the failure
#   mode the daemon would then have to report on).
# - The env file carries WA_BROKER_KEY: 0600, never echoed, never on argv
#   (family #4 / W115).

set -u

HOME_DIR="/Users/zantara-codex"
ENV_FILE="$HOME_DIR/.wa-codex-broker.env"
VENV_PY="$HOME_DIR/wa-broker/.venv/bin/python3"
TAG="wa-codex-broker-wrapper"

if [ ! -f "$ENV_FILE" ]; then
    echo "$TAG: env file missing: $ENV_FILE - refusing to start (run provisioning)" >&2
    exit 78 # EX_CONFIG
fi
if grep -q "__FILL_ME__" "$ENV_FILE"; then
    echo "$TAG: env file still carries __FILL_ME__ placeholders - refusing to start" >&2
    exit 78
fi

set -a
. "$ENV_FILE"
set +a

if [ ! -x "$VENV_PY" ]; then
    echo "$TAG: venv python missing or not executable: $VENV_PY - run provisioning" >&2
    exit 78
fi

cd "$HOME_DIR/wa-broker" || exit 78
export PYTHONPATH="$HOME_DIR/wa-broker"

exec "$VENV_PY" -m backend.services.integrations.wa_codex_daemon
