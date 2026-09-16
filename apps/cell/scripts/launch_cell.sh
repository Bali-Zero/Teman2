#!/usr/bin/env bash
# launch_cell.sh — LaunchAgent wrapper that loads secrets from .env
# Called by com.cell.organism.plist instead of python directly
set -euo pipefail

# Default unchanged — launchd never sets CELL_DIR, so the Pro resolves to the
# same literal it always did. The override exists so the scoped-credential
# block below can be driven by a test instead of only by production.
CELL_DIR="${CELL_DIR:-/Users/nuzantara/nuzantara/apps/cell}"
ENV_FILE="$CELL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "FATAL: Missing $ENV_FILE — create it from .env.example" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# Redis on the Pro runs with `requirepass`, and REDIS_URL carries no userinfo.
# cell/main.py passes `password=os.environ.get("REDIS_PASSWORD") or None` to
# the client, so with the variable unset every safety cycle logged
#   cell.safety: Redis unavailable, proceeding without kill switch:
#   Authentication required.
# and cell/core/safety.py took its fail-open branch: `cell:disabled` and
# `cell:maintenance` — two of CELL's three stop switches — were never read.
#
# Scoped on purpose, ONE key and no sourcing. ~/.nuzantara-secrets.env holds
# unrelated credentials (Claude OAuth tokens among them) and `set -a; source`
# would pull every one of them into a long-running process that needs exactly
# this one. Same least-exposure posture as scripts/pg.sh, including its
# refuse-unless-0600 rule: a loosely permissioned credential file is reported
# and skipped, not trusted.
#
# An explicit REDIS_PASSWORD — from the environment or from .env, which is the
# authoritative place for it — always wins and is never overwritten. The value
# is never echoed.
if [ -z "${REDIS_PASSWORD:-}" ]; then
    SECRETS_FILE="${NUZANTARA_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
    if [ -f "$SECRETS_FILE" ]; then
        secrets_mode="$(stat -f '%OLp' "$SECRETS_FILE" 2>/dev/null || echo unknown)"
        if [ "$secrets_mode" = "600" ]; then
            REDIS_PASSWORD="$(sed -n 's/^REDIS_PASSWORD=//p' "$SECRETS_FILE" | head -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")"
            export REDIS_PASSWORD
        else
            echo "WARN: $SECRETS_FILE mode $secrets_mode != 600 — refusing to read REDIS_PASSWORD from it" >&2
        fi
    fi
fi

export PYTHONPATH="$CELL_DIR"
exec "$CELL_DIR/.venv/bin/python" -m cell.main
