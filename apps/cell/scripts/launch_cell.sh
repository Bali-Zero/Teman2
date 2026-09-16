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
# is never echoed. Every failure to obtain one is REPORTED: a silent skip here
# is indistinguishable from the outage this block exists to end.
if [ -z "${REDIS_PASSWORD:-}" ]; then
    SECRETS_FILE="${NUZANTARA_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
    if [ -f "$SECRETS_FILE" ]; then
        secrets_mode="$(stat -f '%OLp' "$SECRETS_FILE" 2>/dev/null || echo unknown)"
        if [ "$secrets_mode" = "600" ]; then
            # `tail -n 1`, never `head -n 1`. head closes the pipe after one
            # line; on a file carrying more than one match sed then takes
            # SIGPIPE, and under `set -euo pipefail` that failing substitution
            # ABORTS THE LAUNCHER — a malformed credential file would stop CELL
            # from starting at all. Measured, not reasoned: the head form exits
            # 141 and never reaches its own next line. tail drains the stream,
            # and it also picks the assignment `set -a; source` would have used
            # (the LAST one), so this reader and every other reader of that file
            # agree about what it says.
            #
            # `tr -d` and the trailing-blank strip run before the quotes come
            # off: a CRLF `\r` or a trailing space would ride into the password
            # and turn a valid credential into an auth failure — which lands
            # back in exactly the fail-open this block exists to end, silently.
            # Blanks INSIDE quotes survive, because there they are deliberate.
            REDIS_PASSWORD="$(
                sed -n 's/^REDIS_PASSWORD=//p' "$SECRETS_FILE" \
                  | tr -d '\r' \
                  | tail -n 1 \
                  | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
            )"
            export REDIS_PASSWORD
            if [ -z "$REDIS_PASSWORD" ]; then
                echo "WARN: $SECRETS_FILE is 0600 but carries no usable REDIS_PASSWORD — CELL starts without its Redis stop switches" >&2
            fi
        else
            echo "WARN: $SECRETS_FILE mode $secrets_mode != 600 — refusing to read REDIS_PASSWORD from it" >&2
        fi
    fi
fi

export PYTHONPATH="$CELL_DIR"
exec "$CELL_DIR/.venv/bin/python" -m cell.main
