#!/usr/bin/env bash
# nuz_db_refresh.sh — pull-only snapshot of Fly prod Postgres → local nuzantara_dev (M5).
#
# Design: research/operations/2026-06-12-m5-postgres-architecture.md
# Spec:   research/operations/specs/2026-06-12-M5-postgres-local-spec.md  (Phase 2, step 5)
#
# ONE-WAY pull. Never writes to Fly. Uses the read-only role nuzantara_readonly
# (Keychain `nuzantara-postgres-readonly`, T3.2 — 255 SELECT grants, zero write).
# Pro local PG is never touched (SYMBIOSIS Law 2). PII boundary: the dump contains
# client PII (UU PDP) → stays on M5 only (Law 6, FileVault), dumps dir 700 / files 600.
#
# Panel fixes folded in (2026-06-12, §0-bis): F2 (-h 127.0.0.1, NOT localhost→::1),
# F3 (keychain read to a shell var, never on argv / never echoed). §7 gotchas:
# mkdir -p, port-based proxy teardown, export PGPASSWORD, dropdb+createdb (atomic) over --clean.
#
# Exclusions (churn / unbounded tables — keep the dump lean; revisit if size grows):
#   events_outbox, olympus_heartbeats* (data only; schema still restored).
#
# Usage:  bash scripts/nuz_db_refresh.sh
# Env:    PG17_BIN (default /opt/homebrew/opt/postgresql@17/bin), PROXY_PORT (default 15432),
#         FLY_PG_APP (default nuzantara-postgres), DUMP_DIR (default ~/.nuzantara-db-snapshots),
#         KEEP_DUMPS (default 3).

set -euo pipefail

PG17_BIN="${PG17_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
PROXY_PORT="${PROXY_PORT:-15432}"
FLY_PG_APP="${FLY_PG_APP:-nuzantara-postgres}"
DUMP_DIR="${DUMP_DIR:-$HOME/.nuzantara-db-snapshots}"
KEEP_DUMPS="${KEEP_DUMPS:-3}"
DEV_DB="nuzantara_dev"
RO_ROLE="nuzantara_readonly"
KEYCHAIN_SERVICE="nuzantara-postgres-readonly"

export PATH="$PG17_BIN:$PATH"

log() { printf '[nuz-db-refresh] %s\n' "$*"; }
die() { printf '[nuz-db-refresh] ERROR: %s\n' "$*" >&2; exit 1; }

# --- preflight -------------------------------------------------------------
command -v fly >/dev/null 2>&1 || die "flyctl not found on PATH"
command -v pg_dump >/dev/null 2>&1 || die "pg_dump not found ($PG17_BIN) — is postgresql@17 installed?"
command -v pg_isready >/dev/null 2>&1 || die "pg_isready not found ($PG17_BIN)"
fly auth whoami >/dev/null 2>&1 || die "flyctl not authenticated — run: fly auth login"
pg_isready -h 127.0.0.1 -p 5432 -q || die "local postgres not accepting on 127.0.0.1:5432 — brew services start postgresql@17"

mkdir -p "$DUMP_DIR"
chmod 700 "$DUMP_DIR"

# free space guard (need at least ~2GB headroom; dump size is measured on first run)
avail_kb="$(df -k "$DUMP_DIR" | awk 'NR==2 {print $4}')"
[ "${avail_kb:-0}" -gt 2000000 ] || die "less than ~2GB free at $DUMP_DIR — free space before refreshing"

# port-already-bound guard (orphan proxy from a prior run, §7)
if lsof -ti:"$PROXY_PORT" >/dev/null 2>&1; then
    die "port $PROXY_PORT already bound (orphan fly proxy?). Kill it: kill \$(lsof -ti:$PROXY_PORT)"
fi

# --- keychain: read RO password into a var, NEVER on argv (F3) --------------
# `security ... -w` prints the secret to STDOUT; capture it, export for libpq, never echo.
RO_PASS="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)" \
    || die "Keychain entry '$KEYCHAIN_SERVICE' not found on M5 — import it first (spec step 4)"
[ -n "$RO_PASS" ] || die "Keychain entry '$KEYCHAIN_SERVICE' is empty"
export PGPASSWORD="$RO_PASS"
unset RO_PASS

# --- fly proxy (port-based teardown, §7) -----------------------------------
log "opening fly proxy $PROXY_PORT → $FLY_PG_APP:5432 ..."
fly proxy "$PROXY_PORT":5432 -a "$FLY_PG_APP" >/dev/null 2>&1 &
PROXY_PID=$!
# teardown by PORT, not just $! — covers child procs the trap on $! would miss
trap 'kill "$PROXY_PID" 2>/dev/null; kill $(lsof -ti:"$PROXY_PORT" 2>/dev/null) 2>/dev/null; unset PGPASSWORD' EXIT

# wait-for-port (timeout 30s)
for i in $(seq 1 30); do
    if pg_isready -h 127.0.0.1 -p "$PROXY_PORT" -q 2>/dev/null; then break; fi
    [ "$i" -eq 30 ] && die "fly proxy did not come up on 127.0.0.1:$PROXY_PORT within 30s"
    sleep 1
done
log "proxy up on 127.0.0.1:$PROXY_PORT"

# --- discover the target db name behind the readonly role ------------------
# The readonly role's default DB is what we dump. List non-template DBs it can see.
DB_NAME="$(psql -h 127.0.0.1 -p "$PROXY_PORT" -U "$RO_ROLE" -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres','repmgr') ORDER BY datname LIMIT 1;" \
    2>/dev/null || true)"
[ -n "$DB_NAME" ] || die "could not determine prod DB name via readonly role (permission? wrong role?). STOP — surface to Antonello (do NOT escalate role)."
log "prod DB to dump: $DB_NAME"

# --- dump (F2: -h 127.0.0.1) -----------------------------------------------
STAMP="$(date +%Y%m%d-%H%M)"
DUMP_FILE="$DUMP_DIR/prod-$STAMP.dump"
log "dumping (this can take a while) ..."
if ! pg_dump -h 127.0.0.1 -p "$PROXY_PORT" -U "$RO_ROLE" -d "$DB_NAME" \
        -Fc --no-owner --no-acl \
        --exclude-table-data='events_outbox' \
        --exclude-table-data='olympus_heartbeats*' \
        -f "$DUMP_FILE" 2>/tmp/nuz-db-dump.err; then
    log "pg_dump stderr:"; sed 's/^/    /' /tmp/nuz-db-dump.err >&2
    # permission error mid-dump (sequence/table outside the 255 SELECT grants) → STOP (W38 spirit)
    grep -qiE 'permission denied|must be (owner|superuser)' /tmp/nuz-db-dump.err \
        && die "readonly role hit a permission error mid-dump — STOP, surface to Antonello (do NOT escalate role)"
    die "pg_dump failed (see stderr above)"
fi
chmod 600 "$DUMP_FILE"
DUMP_SZ="$(du -h "$DUMP_FILE" | awk '{print $1}')"
log "dump OK: $DUMP_FILE ($DUMP_SZ)"

# --- restore into nuzantara_dev (atomic recreate, §7 — beats --clean) ------
log "recreating $DEV_DB ..."
dropdb -h 127.0.0.1 -p 5432 --if-exists "$DEV_DB"
createdb -h 127.0.0.1 -p 5432 "$DEV_DB"
log "restoring ..."
# Atomic recreate (dropdb+createdb above) already gives a clean target, so we do NOT
# need --single-transaction (which would conflict with the fresh-db approach and abort
# the whole restore on the first benign --no-owner notice). We DO add --exit-on-error
# (Codex panel MAJOR) so a REAL restore error is not silently swallowed; benign
# "role does not exist" notices under --no-owner/--no-acl are warnings, not errors,
# and do not trip --exit-on-error. Verified empirically by the anchor-count check below.
pg_restore -h 127.0.0.1 -p 5432 --no-owner --no-acl --exit-on-error -d "$DEV_DB" "$DUMP_FILE" 2>/tmp/nuz-db-restore.err || {
    log "pg_restore FAILED (--exit-on-error). stderr:"; sed 's/^/    /' /tmp/nuz-db-restore.err >&2
    die "restore into $DEV_DB failed — dev DB is incomplete"
}

# --- verify (anchor tables > 0) --------------------------------------------
verify_count() {
    psql -h 127.0.0.1 -p 5432 -d "$DEV_DB" -tAc "SELECT count(*) FROM $1;" 2>/dev/null || echo "ERR"
}
CLIENTS="$(verify_count clients)"
PRACTICES="$(verify_count practices)"
MIGRATIONS="$(verify_count schema_migrations)"
log "row counts — clients=$CLIENTS practices=$PRACTICES schema_migrations=$MIGRATIONS"
case "$CLIENTS" in
    ''|ERR|0) die "verify FAILED: clients table empty or unreadable in $DEV_DB — restore likely incomplete" ;;
esac

# --- rotate dumps (keep last N) --------------------------------------------
log "rotating dumps (keep $KEEP_DUMPS) ..."
ls -1t "$DUMP_DIR"/prod-*.dump 2>/dev/null | tail -n +"$((KEEP_DUMPS + 1))" | while read -r old; do
    rm -f "$old" && log "  removed old dump: $(basename "$old")"
done

log "DONE — $DEV_DB refreshed from prod ($DUMP_SZ, $STAMP). Prod untouched (pull-only)."
