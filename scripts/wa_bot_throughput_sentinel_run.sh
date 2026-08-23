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
#    inbound_webhooks / wa_outbox rows live on Fly. Audited 2026-08-23: every
#    organ in this repo that sets INTAKE_DATABASE_URL points it at local
#    nuzantara_dev, whose copies of those two tables carry ZERO rows. So this
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

set -a
# shellcheck disable=SC1090
source "$SECRETS"
set +a

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

# The script's own resolution order is INTAKE_DATABASE_URL, LOCAL_DATABASE_URL,
# DATABASE_URL_LOCAL, then the dev default. Neither of the first two is set by
# anything on this path, so the export below is what it actually uses; it is
# exported rather than passed on argv so the DSN never appears in `ps`.
export DATABASE_URL_LOCAL
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
exec "$PYBIN" -u "$REPO_ROOT/scripts/wa_bot_throughput_sentinel.py" "$@"
