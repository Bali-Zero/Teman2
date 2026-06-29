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

if [ "$TARGET" = "local" ]; then
  # M5 local PG17 (PR #1349) — dev role/db.
  PW="$(security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_dev_readonly -w 2>/dev/null || true)"
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
  PW="$(security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_readonly -w 2>/dev/null || true)"
  CONN="host=127.0.0.1 port=${PORT} user=nuzantara_readonly dbname=nuzantara_rag sslmode=disable"
fi

if [ -z "${PW:-}" ]; then
  echo "pg.sh: no Keychain password found for target=${TARGET}." >&2
  echo "  prod  -> security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_readonly -w" >&2
  echo "  local -> security find-generic-password -s nuzantara-postgres-readonly -a nuzantara_dev_readonly -w" >&2
  exit 2
fi

exec env PGPASSWORD="$PW" "$PSQL" "$CONN" "$@"
