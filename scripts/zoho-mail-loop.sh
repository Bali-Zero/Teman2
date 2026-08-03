#!/bin/bash
# =============================================================================
# zoho-mail-loop.sh — daily wrapper for the Zoho mail loop.
#
# Shape dictated by the scars this repo already paid for:
#
#   * errexit is DISARMED around the job and the rc is CAPTURED (W101/W107/W108).
#     A bare `job | tee` under `set -e` aborts on the pipeline itself, so the
#     alert branch and the `exit $rc` below it become dead code on the only path
#     they exist for. There is no pipeline here for the same reason: a pipe
#     masks the exit code (W97).
#
#   * the alarm does NOT depend on a token being present. It goes through
#     scripts/tg_notify.py, which owns the token chain and spools what it cannot
#     deliver. An `if [ -n "$TELEGRAM_BOT_TOKEN" ]` guard would make the alarm
#     silent in exactly the launchd environment that produces the failures.
#
#   * the gateway is invoked with an ABSOLUTE interpreter, never a `python3`
#     resolved via PATH after sourcing a venv (W108): the reporter must not share
#     the failure mode of the thing it reports.
#
#   * a missing gateway is the LOUD branch. "Could not send" must never read
#     like "sent".
#
# Exit codes come from the CLI: 0 clean, 1 degraded, 2 could not run.
# =============================================================================

set -uo pipefail

# The repo root directly under $HOME, never the Desktop symlink that also points
# at it. Both "work" from a shell, and that is the trap: launchd's access to the
# Desktop directory is a TCC-protected surface it can lose WITHOUT any change to
# code, plist or permissions — that is W84, where two LaunchAgents reported
# LastExitStatus=0 while their logs said "Operation not permitted". The repo's
# own antidote (`scripts/lint_tcc_desktop_paths.py`) lints for it, and it caught
# this file. The literal path is deliberately not written out here: the lint is a
# text scan, so spelling it even in a comment re-trips the gate.
REPO_ROOT="${MAIL_LOOP_REPO_ROOT:-$HOME/nuzantara}"
APP_DIR="$REPO_ROOT/apps/backend-rag"
VENV_PY="$APP_DIR/.venv/bin/python"
GATEWAY="$REPO_ROOT/scripts/tg_notify.py"
SYSTEM_PY="/usr/bin/python3"
LOG_DIR="${MAIL_LOOP_LOG_DIR:-$HOME/logs}"
LOG="$LOG_DIR/zoho-mail-loop.log"

ORGAN_ID="pro.zoho_mail_loop"
HB="${HEARTBEAT_BIN:-$REPO_ROOT/scripts/lib/heartbeat.sh}"
LOCK_DIR="${MAIL_LOOP_LOCK_DIR:-/tmp/zoho-mail-loop.lock}"

mkdir -p "$LOG_DIR"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

# G2 heartbeat. Like `alert`, it reports and never decides: a heartbeat that can
# change the exit code turns the organ's own proof-of-life into a way to lose
# the verdict.
heartbeat() {
    [ -x "$HB" ] && "$HB" "$ORGAN_ID" "$1" "${2:-}" >/dev/null 2>&1
    return 0
}

# G5 kill switch. An organ nobody can stop without editing its code is one that
# gets stopped by deleting the plist, and then nobody remembers it existed.
if [ "${MAIL_LOOP_ENABLED:-true}" = "false" ]; then
    log "disabled via MAIL_LOOP_ENABLED=false — intentional stop"
    heartbeat ok "disabled via MAIL_LOOP_ENABLED=false — intentional stop"
    exit 0
fi

# G10 single instance. Two overlapping runs would both draft into the same
# mailbox and both learn from the same Sent folder. `mkdir` is the atomic test,
# and a lock left by a dead process is RECLAIMED rather than obeyed — a stale
# lock that silences the organ forever is the failure this repo names most often.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    holder=$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        log "another run is live (pid=$holder) — exiting without touching the mailbox"
        heartbeat ok "skipped: run already in progress (pid=$holder)"
        exit 0
    fi
    if [ ! -d "$LOCK_DIR" ]; then
        # mkdir failed for a reason that is NOT "already exists" — a permission
        # problem, a full disk. Saying "stale lock, reclaiming" here would send
        # the reader hunting a lock that was never the problem.
        log "FATAL: cannot create the lock at $LOCK_DIR (not an existing lock)"
        heartbeat error "cannot create lock at $LOCK_DIR"
        exit 2
    fi
    log "stale lock at $LOCK_DIR (holder=${holder:-unknown} not alive) — reclaiming"
    rm -rf "$LOCK_DIR"
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        log "FATAL: cannot take the lock at $LOCK_DIR"
        heartbeat error "cannot take lock at $LOCK_DIR"
        exit 2
    fi
fi
echo $$ > "$LOCK_DIR/pid" 2>/dev/null
# Read back what is actually in the lock before trusting it.
#
# `mkdir` is atomic but writing the pid is not, so there is a window in which a
# second process finds the directory present and the pid file empty, reads
# holder="" — which its liveness test treats as "nobody" — and reclaims a lock a
# live process just took. Both would then run, both would draft into the same
# mailbox. This does not close the race, it makes the LOSER notice: whoever does
# not own the pid file stands down instead of proceeding.
if [ "$(cat "$LOCK_DIR/pid" 2>/dev/null)" != "$$" ]; then
    log "lost the lock race at $LOCK_DIR — standing down without touching the mailbox"
    heartbeat ok "skipped: lost the lock race"
    exit 0
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

# alert NEVER returns non-zero. It reports, it does not decide.
#
# An earlier version of this function returned 1 when the gateway was missing.
# That looked harmless and was not: a caller inside the `case` below would then
# propagate that 1, and the script exited 1 while the job had actually exited 2 —
# the real exit code masked by the reporting path. Measured, not reasoned:
# cli rc=2 with the gateway removed produced wrapper exit=1.
#
# Which is the W101/W97 family reappearing INSIDE the cure written against it.
# So: the messenger is not allowed to change the verdict. Undeliverable is loud
# in the log and invisible to the control flow.
alert() {
    # $1 = tier (p0|digest|log), $2 = dedup key, $3 = message
    local tier="$1" key="$2" msg="$3" rc=0
    if [ ! -f "$GATEWAY" ]; then
        log "ALARM UNDELIVERABLE: gateway missing at $GATEWAY -- msg: $msg"
        return 0
    fi
    "$SYSTEM_PY" "$GATEWAY" --tier "$tier" --source zoho-mail-loop \
        --dedup-key "$key" "$msg" >>"$LOG" 2>&1 || rc=$?
    log "tg[$tier] rc=$rc"
    return 0
}

# --- environment -----------------------------------------------------------
#
# launchd hands a job almost nothing: the plist's PATH and HOME, and that is it.
# Everything this loop needs — the database DSN, the Zoho client credentials,
# the Claude token — lives in files an interactive shell reads and a cron does
# not. Without them the loop exits 2 on the first call, every morning.
#
# Order is load-bearing: ~/.nuzantara-secrets.env is sourced LAST because its
# DATABASE_URL is the one that authenticates against the live proxy. The DSN in
# apps/backend-rag/.env is stale (role backend_rag_v2, password refused), and a
# reversed order silently hands the loop the broken one.
#
# `[ -f X ] && . X`, never `. X || true`: bash treats a failed `source` as a
# special-builtin failure and exits before the `||` can run (W108).
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
ENV_MASTER="$HOME/.openclaw/workspace/.env.master"

set -a
[ -f "$SECRETS_FILE" ] && . "$SECRETS_FILE"
set +a

# The Zoho client pair is pulled key-by-key rather than by sourcing .env.master
# wholesale: that file holds credentials for unrelated systems, and none of them
# belong in the environment of a process that shells out to another program.
# Read with sed, never eval'd — an eval here would execute whatever a secrets
# file happens to contain.
zoho_value() {
    [ -f "$ENV_MASTER" ] || return 0
    sed -n "s/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}$1=//p" "$ENV_MASTER" 2>/dev/null \
        | head -1 \
        | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}
[ -z "${ZOHO_CLIENT_ID:-}" ] && export ZOHO_CLIENT_ID="$(zoho_value ZOHO_CLIENT_ID)"
[ -z "${ZOHO_CLIENT_SECRET:-}" ] && export ZOHO_CLIENT_SECRET="$(zoho_value ZOHO_CLIENT_SECRET)"

# The drafting step shells out to the `claude` CLI. Interactively the CLI uses
# its own OAuth session and needs no variable; under launchd that session may
# not be reachable, so the token slot is mapped in when the plain name is unset.
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_1:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_1"
fi

# Say what was found, without printing any of it. A run that fails for a missing
# credential must be diagnosable from this log alone.
log "env: DATABASE_URL=$([ -n "${DATABASE_URL:-}" ] && echo yes || echo NO)" \
    "ZOHO_CLIENT_ID=$([ -n "${ZOHO_CLIENT_ID:-}" ] && echo yes || echo NO)" \
    "ZOHO_CLIENT_SECRET=$([ -n "${ZOHO_CLIENT_SECRET:-}" ] && echo yes || echo NO)" \
    "CLAUDE_CODE_OAUTH_TOKEN=$([ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && echo yes || echo no-env-session-only)"

if [ ! -x "$VENV_PY" ]; then
    log "FATAL: venv interpreter missing at $VENV_PY"
    heartbeat error "venv interpreter missing at $VENV_PY"
    alert p0 mail-loop-venv "zoho-mail-loop: venv missing at $VENV_PY, loop did not run"
    exit 2
fi

# The venv can exist as a skeleton: the interpreter is there, site-packages
# evaporated (W81b — a re-added worktree drops gitignored venvs). Probe a real
# import instead of trusting the binary's existence.
if ! "$VENV_PY" -c "import asyncpg" >/dev/null 2>&1; then
    log "FATAL: venv present but asyncpg missing (skeleton venv)"
    heartbeat error "venv at $VENV_PY cannot import asyncpg"
    alert p0 mail-loop-venv-broken \
        "zoho-mail-loop: venv at $VENV_PY cannot import asyncpg -- reinstall requirements"
    exit 2
fi

log "start (dry_run=${MAIL_LOOP_DRY_RUN:-0})"
heartbeat starting "mail loop starting (dry_run=${MAIL_LOOP_DRY_RUN:-0})"

ARGS=()
if [ "${MAIL_LOOP_DRY_RUN:-0}" = "1" ]; then
    ARGS+=("--dry-run")
fi

# --- the job. rc captured, no pipeline. ---
#
# This script opens with `set -uo pipefail` and deliberately WITHOUT `-e`, so
# there is no errexit to disarm here. An earlier draft wrapped this block in
# `set +e` / `set -e`, which does not restore the previous state — it ENABLES
# errexit for everything below, and the first non-zero return in the reporting
# path then aborted the script before `exit $RC`. Do not add it back.
#
# `${ARGS[@]+"${ARGS[@]}"}` and not `"${ARGS[@]}"`: in bash 3.2 — the ONLY bash
# on these Macs, and the interpreter this plist names explicitly — expanding an
# EMPTY array under `set -u` is an "unbound variable" fatal. The array is empty
# exactly when MAIL_LOOP_DRY_RUN is 0, i.e. the live configuration. Measured,
# not reasoned: with DRY_RUN=1 a job exiting 2 gave wrapper rc=2; with DRY_RUN
# unset the same job gave `line 97: ARGS[@]: unbound variable`, wrapper rc=1,
# the job NEVER STARTED and the `case` below — the whole alerting path — never
# ran. A cron that dies mute the day it goes live, which is superscar #2 with
# the trigger set to "the operator flipped the flag as documented".
cd "$APP_DIR" || { log "FATAL: cannot cd to $APP_DIR"; exit 2; }
PYTHONPATH=. "$VENV_PY" -m backend.services.mail_loop.cli ${ARGS[@]+"${ARGS[@]}"} >>"$LOG" 2>&1
RC=$?
# ------------------------------------------------------------

case "$RC" in
    0)
        log "clean (rc=0)"
        heartbeat ok "clean run (dry_run=${MAIL_LOOP_DRY_RUN:-0})"
        alert log mail-loop-ok "zoho-mail-loop: clean run"
        ;;
    1)
        log "DEGRADED (rc=1)"
        heartbeat degraded "ran but did half its job — see $LOG"
        alert p0 mail-loop-degraded \
            "zoho-mail-loop DEGRADED: ran but did half its job (missing folder, or drafted nothing). See $LOG"
        ;;
    *)
        log "FAILED (rc=$RC)"
        heartbeat error "could not run at all (rc=$RC) — see $LOG"
        alert p0 mail-loop-failed \
            "zoho-mail-loop FAILED rc=$RC: could not run at all. See $LOG"
        ;;
esac

exit "$RC"
