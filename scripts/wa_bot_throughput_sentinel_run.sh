#!/usr/bin/env bash
# wa_bot_throughput_sentinel_run.sh — venv-python launcher for
# scripts/wa_bot_throughput_sentinel.py.
#
# Same shape as scripts/wa_mirror_freshness_liveness_run.sh (see that file's
# header for the HOME-fork / kill-switch / heartbeat design note). Two things
# differ, and both are load-bearing:
#
# 1. THIS ORGAN READS PRODUCTION, ITS SIBLING READS LOCAL DEV.
#    The wa-mirror table lives on Pro's local Postgres; the bot's own
#    inbound_webhooks / wa_outbox rows live on Fly. Audited ONCE, 2026-08-23:
#    every organ in this repo that sets INTAKE_DATABASE_URL points it at local
#    nuzantara_dev, whose copies of those two tables carried ZERO rows THAT DAY.
#    Read that as a dated observation, not a standing property — it is live
#    database state and nothing re-checks it. Nothing here depends on it any
#    more either: since the override guard below, the DSN is enforced rather
#    than inferred from what another database happens to contain. So this
#    wrapper sources ~/.nuzantara-secrets.env and exports DATABASE_URL_LOCAL —
#    the one name with a proven live path to production, through the
#    `flyctl proxy 15432:5432 -a nuzantara-postgres` tunnel that
#    com.balizero.wr2.pg-proxy already keeps alive on this machine.
#    CAUTION: DATABASE_URL_LOCAL (production, via tunnel) and
#    LOCAL_DATABASE_URL (dev override) are one word-swap apart and mean
#    opposite things. Do not "tidy" one into the other.
#
# 2. IT REFUSES TO RUN BLIND RATHER THAN RUNNING AGAINST THE WRONG DATABASE.
#    If the secrets file or the tunnel is missing, this exits non-zero WITHOUT
#    spawning python. That is deliberate: the sentinel's own wrong-database
#    branch would otherwise fire a p0 every 15 minutes describing a config
#    fault the operator can already see here, and an alarm that always fires
#    is an alarm nobody reads. A missing precondition is a wrapper-level
#    failure with a heartbeat, not a paging storm.
#
# Pro-only: the tunnel it depends on is launchd-supervised HERE
# (com.balizero.wr2.pg-proxy). On Mini the equivalent flyctl proxy is a bare
# unsupervised process (measured 2026-08-23: PID 8883, PPID 1, launchd knows
# nothing about it) — installing there would hang this organ off a leg nobody
# restarts. superscar #10: do NOT install on Mini/M5.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORGAN_ID="pro.wa_bot_throughput_sentinel"
SECRETS="${HOME}/.nuzantara-secrets.env"
TUNNEL_HOST="127.0.0.1"
TUNNEL_PORT="15432"

# shellcheck source=scripts/lib/heartbeat.sh
source "$REPO_ROOT/scripts/lib/heartbeat.sh"

# Kill switch — same superset the Python side honours (0|false|no), matched
# case-insensitively so the wrapper and the script it launches can never
# disagree about what "disabled" means.
_enabled_lc="$(printf '%s' "${WA_BOT_THROUGHPUT_SENTINEL_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
case "$_enabled_lc" in
  false|0|no)
    organism_heartbeat "$ORGAN_ID" "disabled" "WA_BOT_THROUGHPUT_SENTINEL_ENABLED=${WA_BOT_THROUGHPUT_SENTINEL_ENABLED:-}"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WA_BOT_THROUGHPUT_SENTINEL_ENABLED=${WA_BOT_THROUGHPUT_SENTINEL_ENABLED:-} — skipping run"
    exit 0
    ;;
esac

if [[ ! -r "$SECRETS" ]]; then
  organism_heartbeat "$ORGAN_ID" "error" "secrets file unreadable: $SECRETS"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FATAL: $SECRETS unreadable — refusing to run against a fallback DB" >&2
  exit 78  # EX_CONFIG
fi

# `source` is ITSELF a silent-exit path, and it sat one block above the
# interpreter guard below — same defect, cured later. A malformed secrets file
# aborts the script mid-source with NO heartbeat, and bash echoes the OFFENDING
# LINE to stderr, which in this file is plausibly a credential landing in the
# organ's .err.log (superscar #4). So: bash's stderr discarded deliberately,
# and the failure reported by NAME and return code only.
#
# BOTH -e AND -u are lifted across the source, and the second one is not
# decoration. The first version of this guard lifted only errexit; the
# cross-family seat then showed that `set -u` kills the whole wrapper just as
# silently on the realistic idiom `DATABASE_URL_LOCAL=postgres://u:$PGPASS@h/db`
# once someone removes the PGPASS line — and with stderr now suppressed, that
# path had been made MORE silent by the fix, not less. With nounset lifted, a
# missing interpolation expands empty and the failure surfaces downstream in the
# payload's own auth error: degraded, never silent.
#
# HONEST LIMIT, because the comment above it used to overstate: $? is the rc of
# the LAST command in the file, so garbage in the middle of a file that ends on
# a valid line still returns 0. That is not fully detectable here — the
# DATABASE_URL_LOCAL, tunnel and interpreter guards below are what actually gate
# the run in that case. Both findings in this block came from the cross-family
# gate seat, neither from the author.
set -a
set +e
set +u
# shellcheck disable=SC1090
source "$SECRETS" 2>/dev/null
_src_rc=$?
set -u
set -e
set +a
if [[ "$_src_rc" -ne 0 ]]; then
  organism_heartbeat "$ORGAN_ID" "error" "secrets file failed to parse (rc=$_src_rc): $SECRETS"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FATAL: $SECRETS failed to parse (rc=$_src_rc) — bash stderr suppressed on purpose, it quotes the offending line" >&2
  exit 78
fi

if [[ -z "${DATABASE_URL_LOCAL:-}" ]]; then
  organism_heartbeat "$ORGAN_ID" "error" "DATABASE_URL_LOCAL unset in $SECRETS"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FATAL: DATABASE_URL_LOCAL unset — refusing to run against a fallback DB" >&2
  exit 78
fi

# Tunnel guard, same shape as the wr2 organs': without it the run would fail
# on connect and page. A down tunnel is a known, separately-supervised
# condition (com.balizero.wr2.pg-proxy) — report it, do not page for it.
if ! nc -z "$TUNNEL_HOST" "$TUNNEL_PORT" >/dev/null 2>&1; then
  organism_heartbeat "$ORGAN_ID" "error" "prod tunnel down: ${TUNNEL_HOST}:${TUNNEL_PORT} (com.balizero.wr2.pg-proxy)"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FATAL: no listener on ${TUNNEL_HOST}:${TUNNEL_PORT} — is com.balizero.wr2.pg-proxy alive?" >&2
  exit 75  # EX_TEMPFAIL — transient by nature, the proxy LaunchAgent restarts itself
fi

# The payload resolves INTAKE_DATABASE_URL, then LOCAL_DATABASE_URL, then
# DATABASE_URL_LOCAL, then a dev default — so either of the first two, arriving
# from the sourced secrets file, would SILENTLY outrank the export below and
# repoint this organ at the wrong database.
#
# An earlier version of this comment said the wrapper "cannot prove they are
# unset" and settled for verifying the property BY EFFECT. That was wrong, and
# the cross-family gate seat said so: the file has just been sourced into THIS
# process, so testing the names costs one line and reads nothing. Detection by
# effect would also have routed the config fault through the payload's
# wrong-database p0 — exactly the paging storm §2 of this header says the
# wrapper exists to prevent.
#
# They are UNSET rather than treated as fatal, deliberately: this wrapper's
# intent is unambiguous, and turning an unrelated addition to a shared secrets
# file into an outage of the outage-detector is the wrong trade. The override is
# logged so it is visible rather than silent.
for _override in INTAKE_DATABASE_URL LOCAL_DATABASE_URL; do
  if [[ -n "${!_override:-}" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) WARN: $_override is set and outranks DATABASE_URL_LOCAL — unsetting it for this run" >&2
    unset "$_override"
  fi
done
# Exported rather than passed on argv so the DSN never appears in `ps`.
export DATABASE_URL_LOCAL
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python"

# The interpreter is a precondition like any other, and it was the one this
# wrapper did NOT check: with the venv missing, the exec below failed and bash
# exited WITHOUT a heartbeat, leaving staleness as the only signal — slower
# than the paths above and carrying no cause. Measured 2026-08-23 by repointing
# PYBIN at a nonexistent path with ORGANISM_LAST_SEEN_DIR isolated: zero files
# written. In an organ built against superscar #2, a failure path that emits no
# signal is exactly the wrong one to leave open.
if [[ ! -x "$PYBIN" ]]; then
  organism_heartbeat "$ORGAN_ID" "error" "venv interpreter missing: $PYBIN"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FATAL: $PYBIN not executable — the backend venv is missing or moved" >&2
  exit 78  # EX_CONFIG — same class as the other unmet preconditions
fi
exec "$PYBIN" -u "$REPO_ROOT/scripts/wa_bot_throughput_sentinel.py" "$@"
