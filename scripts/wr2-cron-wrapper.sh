#!/bin/bash
# wr2-cron-wrapper.sh — common entry point for every War Room 2.0 LaunchAgent.
#
# Usage:
#   wr2-cron-wrapper.sh <python module>
#
# Example (from a plist):
#   <array>
#     <string>/Users/nuzantara/nuzantara/scripts/wr2-cron-wrapper.sh</string>
#     <string>backend.services.intel.trend_hunter.cli</string>
#   </array>
#
# Responsibilities:
#   1. Source ~/.nuzantara-secrets.env for Telegram + misc creds.
#   2. Resolve DATABASE_URL from Fly (nuzantara-rag) once per invocation.
#   3. cd into apps/backend-rag, activate venv, run python -m <module>, and
#      exit with the module's own code (it used to `exec`; see "Voice" below).
#
# Exception: newsletter_cli.py runs entirely INSIDE Fly (see step 1.5) —
# DATABASE_URL, NOTIFICATIONS_API_KEY, and the notifications endpoint only
# exist there; Pro is just the scheduler.
#
# Designed for macOS launchd (Pro). Exits non-zero if any required piece is
# missing, AND says so through the Telegram gateway — see "Alert on failure".
#
# That second half is new (2026-08-06) and the sentence it replaces is why:
# this header used to read "so missed-runs alerter can pick it up", and that
# claim excused the silence of 14 launchd jobs for months. Measured on the
# live database this turn: `war_room_missed_runs` holds 0 rows and always
# has (max(created_at) is NULL), because `record_missed_run` — the only
# writer — has no callers anywhere outside its own definition. The alerter
# itself is healthy and runs every 6h inside the hardening chain, reporting
# `pending_count: 0` since April; it is reading a table nobody writes. A
# guardian pointed at an empty population is not coverage, and naming one in
# a comment is how a whole cohort ends up with no voice at all (superscar #2).
# Found by asking whether the named guardian was armed, not by a failure.

set -euo pipefail

# ── Voice: alert on ANY non-zero exit (2026-08-06) ──────────────────────────
# A TRAP rather than a call at the one failing site, deliberately. This wrapper
# has FIVE ways to exit non-zero — usage 64, missing fly CLI 74, unresolvable
# fly credential 74, DATABASE_URL_LOCAL unset 74, pg-proxy unreachable 74 —
# plus the module's own code, and every one of them was mute. W107 is exactly
# the mistake of curing the exit you happened to look at: it does not cut the
# risk, it only moves which failure dies quietly. A trap covers the five that
# exist today and the sixth someone adds next year.
#
# Same gateway, tier and `cron-fail:` key family as cron-runner.sh /
# cron-state.sh / cron-wrapper.sh, so this joins the family instead of coining
# a fifth dialect: a flapping job collapses to ONE alert per ladder window
# (6/24/72/168h), the reserved p0 lane applies, and with no credentials the
# alert lands in the digest spool instead of vanishing. A permanently broken
# module costs ~4 messages a week, not 4 a day.
#
# The interpreter is ABSOLUTE and system, never "$VENV_PY", never a bare
# `python3`. W108: by the time the module runs this script has activated a
# venv, so a PATH-resolved python3 IS the venv's — the alarm would run on the
# very interpreter whose breakage is a leading reason the module it must report
# on failed. An alarm that shares the failure mode of what it reports is not an
# alarm. (This is the one line that is NOT a copy of cron-runner.sh, which
# sources no venv and can afford PATH.)
#
# Fail-open by construction: the exit code is the contract this wrapper exists
# to preserve. Every step below is `|| true`-equivalent and the trap re-exits
# with the code it was handed, never its own.
WR2_STAGE="startup"
MODULE="${1:-<none>}"
_wr2_alerted=0

_wr2_alert_exit() {
    local rc="$1"
    [[ "$rc" -eq 0 ]] && return 0
    [[ "${WR2_CRON_ALERT:-true}" == "false" ]] && return 0
    [[ "$_wr2_alerted" -eq 1 ]] && return 0   # a trap must not re-enter itself
    _wr2_alerted=1
    local gateway py key
    gateway="$(dirname "$0")/tg_notify.py"
    [[ -f "$gateway" ]] || gateway="${REPO_ROOT:-$HOME/nuzantara}/scripts/tg_notify.py"
    [[ -f "$gateway" ]] || return 0
    # Key names the CONDITION (module + stage), never a measurement: a message
    # carrying the exit code or a duration would mint a new key per failure and
    # defeat every window — the defect #3677 cured at the sentinel.
    key="cron-fail:wr2.${MODULE##*.}.${WR2_STAGE}"
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        [[ -x "$py" ]] || continue
        "$py" "$gateway" \
            --tier p0 \
            --source "wr2:${MODULE##*.}" \
            --dedup-key "$key" \
            -- "CRON FAIL $(hostname -s 2>/dev/null || echo '?')
Job: wr2 ${MODULE}
Stage: ${WR2_STAGE}
Exit: ${rc}
Log: ${LOG_DIR:-<unset>}" >/dev/null 2>&1 || true
        return 0
    done
    return 0
}
trap '_wr2_alert_exit $?' EXIT

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <python module>" >&2
    exit 64
fi

MODULE="$1"
shift

# G5_kill_switch (organ-conformance gene) — operator stop without uninstall.
# Global: WR2_CRON_ENABLED=false stops every wr2-wrapped organ. Per-organ:
# set <MODULE_TAIL>_ENABLED=false in the plist EnvironmentVariables, where
# MODULE_TAIL is the last dotted segment uppercased (backend.scripts.
# cost_advisor_cli -> COST_ADVISOR_CLI_ENABLED). Default-true: no-op unless
# the operator sets it. Exit 0 so launchd/missed-runs read a deliberate
# stop, not a death.
ORGAN_VAR="$(printf '%s' "${MODULE##*.}" | tr '[:lower:]-' '[:upper:]_')_ENABLED"
if [[ "${WR2_CRON_ENABLED:-true}" == "false" || "${!ORGAN_VAR:-true}" == "false" ]]; then
    echo "[wr2-wrapper] kill switch (${ORGAN_VAR}=false or WR2_CRON_ENABLED=false) — deliberate stop, exit 0"
    exit 0
fi

WR2_STAGE="guard"
REPO_ROOT="${NUZANTARA_REPO_ROOT:-$HOME/nuzantara}"
# Resolved above for our own `cd` below, but never re-exported for the child
# python process — every module reading NUZANTARA_REPO_ROOT via os.environ
# always fell through to its own file-relative guess. Confirmed live 2026-07-27:
# m13_weekly.py's guess landed one directory too shallow (apps/ instead of
# repo root), writing its weekly report to apps/research/... instead of
# research/.... Export it so the resolved value actually reaches the module.
export NUZANTARA_REPO_ROOT="$REPO_ROOT"
SECRETS_FILE="${NUZANTARA_SECRETS:-$HOME/.nuzantara-secrets.env}"
LOG_DIR="${WR2_LOG_DIR:-$HOME/.openclaw/workspace/logs/war-room-v2}"
mkdir -p "$LOG_DIR"

# 1. Secrets
if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$SECRETS_FILE"
    set +a
fi

# 1.5 Newsletter only: dispatch the WHOLE run inside the Fly `api` process
# instead of requiring local Postgres + pg-proxy. DATABASE_URL,
# NOTIFICATIONS_API_KEY, and the /api/notifications/send-email endpoint all
# live only on Fly — Pro has none of them and per CLAUDE.md §Cost constraint
# a secret is never duplicated to a new machine "to make a cron simpler".
# `fly` (FLY_API_TOKEN) is already present on Pro for other ops, so this adds
# zero new secrets. `-g api` targets the process group by name (never a raw
# machine ID, which is not stable across deploys/restarts).
if [[ "$MODULE" == "backend.services.newsletter.newsletter_cli" ]]; then
    if ! command -v fly >/dev/null 2>&1; then
        echo "[wr2-wrapper] ERROR: fly CLI not found on PATH — cannot dispatch newsletter_cli into Fly (api process)." >&2
        exit 74
    fi
    # Which fly credential is alive? Ask fly — never assume.
    # Until 2026-07-26 this line was a bare `unset FLY_API_TOKEN`: a stale env
    # token used to shadow valid auth in ~/.fly/config.yml and kill the daily
    # newsletter run. Then the world inverted — the config token rotted while
    # the env token stayed valid — and the unset became the thing that broke it
    # (same day, same inversion, in fly-pg-backup.sh: prod PG had no backup).
    # Pinning either direction is the bug; scripts/lib/fly_credential.sh probes.
    _fly_cred_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/fly_credential.sh"
    if [[ ! -f "$_fly_cred_lib" ]]; then
        echo "[wr2-wrapper] ERROR: scripts/lib/fly_credential.sh not found — cannot resolve a fly credential." >&2
        exit 74
    fi
    # shellcheck source=lib/fly_credential.sh
    source "$_fly_cred_lib"
    # Probe against THIS app, not `auth whoami`. Pro's FLY_API_TOKEN is scoped
    # to nuzantara-postgres only (ledgered 2026-07-25), so whoami would accept a
    # credential that cannot see nuzantara-rag and the dispatch below would die
    # on 'Could not find App' — the same wrong answer, one stage later. Failing
    # here instead says WHICH credential and WHY, before spending the run.
    resolve_fly_credential "$(command -v fly)" machine list -a nuzantara-rag || exit 74
    remote_cmd="python -m $MODULE"
    for arg in "$@"; do
        remote_cmd+=" $(printf '%q' "$arg")"
    done
    if [[ -n "${NEWSLETTER_SUBJECT_PREFIX:-}" ]]; then
        remote_cmd="NEWSLETTER_SUBJECT_PREFIX=$(printf '%q' "$NEWSLETTER_SUBJECT_PREFIX") $remote_cmd"
    fi
    # Run-and-judge, not exec: the same one-way door as the module exec
    # below. This path dispatches the CLIENT-FACING newsletter, so it is the
    # last one that should fail silently. errexit disarmed per W101.
    WR2_STAGE="newsletter-dispatch"
    set +e
    fly ssh console -a nuzantara-rag -g api -C "$remote_cmd"
    _nl_rc=$?
    set -e
    exit $_nl_rc
fi

# 1.7 Heartbeat lib (best-effort; never blocks the wrapper — same idiom as
# scripts/outbox-prune.sh / scripts/agent_worktree_cleanup_cron.sh). Guard
# failures below used to die mute: an honest stderr line but NO sidecar, so a
# reconciler/monitor reading only ~/.organism/last_seen/*.json never learns the
# pre-flight guard tripped (cicatrix family #2 "esiste != armato" — green
# heartbeat/log mismatch). GUARD_ORGAN_ID is namespaced per invoked module so it
# never collides with that module's own success-path organ id.
if [[ -f "$REPO_ROOT/scripts/lib/heartbeat.sh" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/scripts/lib/heartbeat.sh"
fi
if ! declare -F organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat() { :; }
fi
GUARD_ORGAN_ID="pro.wr2_wrapper_guard.$MODULE"

# 2. DATABASE_URL resolution
# Force DATABASE_URL_LOCAL on Pro/Mini. The shared secrets file may define
# DATABASE_URL with a Fly 6PN hostname; that only resolves inside Fly and makes
# launchd jobs fail locally with socket.gaierror.
if [[ -z "${DATABASE_URL_LOCAL:-}" ]]; then
    echo "[wr2-wrapper] ERROR: DATABASE_URL_LOCAL not set in $SECRETS_FILE. Add it (e.g. postgres://backend_rag_v2:<password>@127.0.0.1:15432/nuzantara_rag?sslmode=disable) and load com.balizero.wr2.pg-proxy first." >&2
    organism_heartbeat "$GUARD_ORGAN_ID" "error" "DATABASE_URL_LOCAL not set in $SECRETS_FILE"
    exit 74
fi
DATABASE_URL="$DATABASE_URL_LOCAL"
export DATABASE_URL

# Sanity: fail fast if localhost:15432 is unreachable (pg-proxy down)
if ! nc -z 127.0.0.1 15432 2>/dev/null; then
    echo "[wr2-wrapper] ERROR: cannot reach 127.0.0.1:15432 — is com.balizero.wr2.pg-proxy loaded? (launchctl list | grep pg-proxy)" >&2
    organism_heartbeat "$GUARD_ORGAN_ID" "error" "pg-proxy 127.0.0.1:15432 unreachable"
    exit 74
fi

# 3. Repo + venv + exec
cd "$REPO_ROOT/apps/backend-rag"
VENV_PY="$PWD/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
    # Fall back to pyenv 3.11.11 shim so cron still runs if .venv is missing
    export PATH="$HOME/.pyenv/versions/3.11.11/bin:$PATH"
    VENV_PY="python"
fi

# 3.5 Measurer only: keep the IG long-lived token alive before the sweep
# (Task-30 watchdog, runbook docs/runbooks/ig-token-watchdog.md §Arming).
# Token-tolerant: with no token configured the watchdog exits 2 and the
# scheduler still runs (it degrades to "no samplers" on its own); the exit-2
# line below is the standing NEEDS-OPERATOR alarm until a token lands.
if [[ "$MODULE" == "backend.services.measurer.scheduler_cli" ]]; then
    set +e
    IG_TOKEN_ENV_FILE="$SECRETS_FILE" \
    IG_TOKEN_STATE_FILE="$HOME/.nuzantara-ig-token-state.json" \
    PYTHONPATH=. "$VENV_PY" -m backend.services.measurer.ig_token_watchdog
    wd_rc=$?
    set -e
    if [[ $wd_rc -eq 1 || $wd_rc -eq 2 ]]; then
        # exit 1 = no token in env at all; exit 2 = refresh needs the operator.
        # Both are the standing starvation alarm, proven live 2026-07-13.
        echo "[measurer] ig-token-watchdog NEEDS OPERATOR (exit $wd_rc — token missing or unrefreshable)" >&2
    elif [[ $wd_rc -ne 0 ]]; then
        echo "[measurer] ig-token-watchdog unexpected exit $wd_rc" >&2
    fi
    # Re-source so a just-refreshed token reaches scheduler_cli.
    if [[ -f "$SECRETS_FILE" ]]; then
        # shellcheck disable=SC1090
        set -a
        source "$SECRETS_FILE"
        set +a
    fi
fi

# `exec` was the structural reason this wrapper could never speak: it replaces
# the process, so there is no "after" in which to read the exit code. Running
# the module as a child and re-exiting with its code preserves exactly the
# contract launchd sees (LastExitStatus is still the module's) and buys the one
# thing exec cannot give — an observation point, here the EXIT trap installed
# at the top.
#
# On the errexit disarming, stated as measured rather than as folklore: with
# an EXIT trap installed, removing `set +e`/`set -e` here changes NOTHING —
# errexit aborts at the call, the trap fires anyway, and $? is still the
# module's code. Mutation-verified: that mutant survives the whole corpus, so
# it is declared equivalent and removed from the set rather than left as a
# fake red. W101 is a scar about captures written after a bare pipeline being
# dead code; the trap is what actually defuses it. The explicit capture stays
# because it makes `exit $MODULE_RC` the readable contract and because any
# line a future edit inserts between the call and the exit WOULD be dead code
# under errexit — which is exactly how W101 reached its fourth generation.
WR2_STAGE="module"
set +e
env PYTHONPATH=. "$VENV_PY" -m "$MODULE" "$@"
MODULE_RC=$?
set -e
exit $MODULE_RC
