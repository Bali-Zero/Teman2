#!/usr/bin/env bash
# pg.sh — one-true-way to reach the Nuzantara PROD Postgres (read-only) from any Mac.
#
# WHY THIS EXISTS (root cause, 2026-06-26):
#   Every "can't access Postgres on Fly/Pro" incident traced to ONE mismatch:
#   the Fly proxy `com.nuzantara.fly-pg-tunnel` exposes PROD nuzantara-postgres
#   on localhost:15432, but callers kept using the LOCAL-DEV identity
#   (role `nuzantara_dev_readonly`, db `nuzantara_dev`) against that PROD proxy.
#   PROD wants role `nuzantara_readonly`, db `nuzantara_rag`. Auth failed forever.
#
#   The WORKING combo (verified live):
#     host=127.0.0.1 port=15432 user=nuzantara_readonly dbname=nuzantara_rag sslmode=disable
#     password: Keychain  service=nuzantara-postgres-readonly  account=nuzantara_readonly
#
# CRON/LAUNCHD FALLBACK (2026-08-24, wa-codex-seat-sentinel W-class): `security
# find-generic-password` needs the caller's LOGIN KEYCHAIN unlocked in an
# interactive GUI session. `crontab`/launchd jobs run outside any such
# session, so the lookup returns EMPTY (not an error — `security` is wrapped
# in `|| true` on purpose, W104: judge output, never exit code alone) and
# every non-interactive caller got CANNOT-VERIFY forever, 68/68 runs measured
# on wa-codex-seat-sentinel. Same pattern this repo already trusts for
# `zantara-codex`'s own launchd daemon (`.wa-codex-broker.env`, scar family
# #4: 0600, never echoed, never on argv): a per-user 0600 credential file is
# the fallback, tried ONLY when the Keychain came back empty, so the
# interactive path (Zero, Claude Code sessions with the item's ACL already
# granted) is completely unchanged. Deliberately its OWN narrow-scope file —
# not `~/.nuzantara-secrets.env` (that file holds six Claude OAuth tokens;
# widening a cron job's file-read footprint to reach a Postgres RO password
# would violate least-exposure for no reason). File is refused outright
# unless its mode is EXACTLY 600 (owner rw, nothing else) — a loosely
# permissioned credential file is not trusted, it is reported and skipped,
# same posture as `security_permissions_audit.py --fix`.
#
# USAGE:
#   scripts/pg.sh -c "SELECT 1;"            # run SQL, read-only
#   scripts/pg.sh -A -F'|' -c "SELECT ..."  # any psql flags pass through
#   scripts/pg.sh                            # interactive psql shell
#   PG_TARGET=local scripts/pg.sh -c "..."   # M5 LOCAL dev DB instead (PG17 :5432)
#
# It auto-starts the Fly proxy if :15432 is dead, then runs psql.
set -euo pipefail

PSQL="${PSQL:-/opt/homebrew/bin/psql}"
FLY="${FLY:-$(command -v fly || command -v flyctl || echo /opt/homebrew/bin/fly)}"
TARGET="${PG_TARGET:-prod}"
CRED_FILE="${NUZANTARA_PG_RO_CRED_FILE:-$HOME/.nuzantara-pg-readonly.env}"

# _pg_ro_password KEYCHAIN_ACCOUNT FILE_VAR_NAME
#   Keychain first (silent, unchanged, for every interactive caller); if that
#   comes back empty, a 0600 credential file second. Never prints the value;
#   never puts it on argv.
_pg_ro_password() {
  local kc_account="$1" file_var="$2" pw mode
  pw="$(security find-generic-password -s nuzantara-postgres-readonly -a "$kc_account" -w 2>/dev/null || true)"
  if [ -n "$pw" ]; then
    printf '%s' "$pw"
    return 0
  fi
  [ -f "$CRED_FILE" ] || return 0
  mode="$(stat -f '%OLp' "$CRED_FILE" 2>/dev/null || echo '')"
  if [ "$mode" != "600" ]; then
    echo "pg.sh: refusing credential file $CRED_FILE — mode is ${mode:-unreadable}, must be exactly 600 (scar #4, not used)" >&2
    return 0
  fi
  pw="$(grep -m1 "^${file_var}=" "$CRED_FILE" | cut -d= -f2-)"
  printf '%s' "$pw"
}

if [ "$TARGET" = "local" ]; then
  # M5 local PG17 (PR #1349) — dev role/db.
  PW="$(_pg_ro_password nuzantara_dev_readonly NUZANTARA_PG_RO_PASSWORD_LOCAL)"
  CONN="host=127.0.0.1 port=5432 user=nuzantara_dev_readonly dbname=nuzantara_dev sslmode=disable"
else
  # PROD via Fly proxy on :15432.
  PORT=15432
  if ! /usr/sbin/lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
    echo "pg.sh: proxy on :${PORT} down — starting fly proxy ${PORT}:5432 -a nuzantara-postgres ..." >&2
    nohup "$FLY" proxy ${PORT}:5432 -a nuzantara-postgres >/tmp/fly-pg-proxy.log 2>&1 &
    for i in $(seq 1 20); do
      /usr/sbin/lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1 && break
      sleep 0.5
    done
  fi
  PW="$(_pg_ro_password nuzantara_readonly NUZANTARA_PG_RO_PASSWORD)"
  CONN="host=127.0.0.1 port=${PORT} user=nuzantara_readonly dbname=nuzantara_rag sslmode=disable"
fi

if [ -z "${PW:-}" ]; then
  echo "pg.sh: no Keychain password found for target=${TARGET}, and no usable fallback." >&2
  echo "  prod  -> security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_readonly -w" >&2
  echo "  local -> security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_dev_readonly -w" >&2
  echo "  cron/launchd fallback -> put NUZANTARA_PG_RO_PASSWORD(_LOCAL)=... in $CRED_FILE, chmod 600" >&2
  exit 2
fi

exec env PGPASSWORD="$PW" "$PSQL" "$CONN" "$@"
