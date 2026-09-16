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
# Scoped to ONE key, and the file is READ, never sourced: it holds unrelated
# credentials and `set -a; source` would hand every one of them to a
# long-running daemon that needs exactly this one.
#
# The parse lives in read_secret_key.py, not in a pipeline here. Two review
# rounds on a bash version found four separate ways for it to abort the
# launcher or export a silently wrong value, all properties of the instrument
# — SIGPIPE, `pipefail` propagation, quote and escape ambiguity, byte-safety.
# A credential file must never be able to stop CELL from starting; that would
# be worse than the fail-open being cured.
#
# Hence the guarded `if`: a failing command inside an `if` condition does NOT
# trip `set -e`, so EVERY failure path below warns and carries on. Nothing
# here is fatal, by design — an unauthenticated Redis is a valid configuration
# on a machine without `requirepass`, CELL's documented policy is to fail open
# when Redis is unreachable, and the /tmp/cell.disabled switch is unaffected
# either way.
#
# An explicit REDIS_PASSWORD — from the environment or from .env, which is the
# authoritative place for it — always wins and is never overwritten. The value
# never reaches stderr and never appears in argv.
if [ -z "${REDIS_PASSWORD:-}" ]; then
    SECRETS_FILE="${NUZANTARA_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
    SECRET_READER="$CELL_DIR/scripts/read_secret_key.py"
    if [ ! -f "$SECRETS_FILE" ]; then
        echo "WARN: $SECRETS_FILE not present — CELL starts without its Redis stop switches" >&2
    elif [ ! -x "$CELL_DIR/.venv/bin/python" ]; then
        echo "WARN: no venv interpreter to read $SECRETS_FILE with — CELL starts without its Redis stop switches" >&2
    elif _cell_redis_pw="$("$CELL_DIR/.venv/bin/python" "$SECRET_READER" "$SECRETS_FILE" REDIS_PASSWORD)"; then
        REDIS_PASSWORD="$_cell_redis_pw"
        export REDIS_PASSWORD
        unset _cell_redis_pw
    else
        # read_secret_key.py has already said why, on stderr, without the value.
        echo "WARN: could not obtain REDIS_PASSWORD — CELL starts without its Redis stop switches" >&2
    fi
fi

export PYTHONPATH="$CELL_DIR"
exec "$CELL_DIR/.venv/bin/python" -m cell.main
