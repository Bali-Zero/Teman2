#!/usr/bin/env bash
# nuz_db_refresh.sh — pull-only snapshot of Fly prod Postgres → local nuzantara_dev (M5).
#
# Design: research/operations/2026-06-12-m5-postgres-architecture.md
# Spec:   research/operations/specs/2026-06-12-M5-postgres-local-spec.md  (Phase 2, step 5)
#
# ONE-WAY pull. Never writes to Fly. Uses the read-only role nuzantara_readonly
# (Keychain `nuzantara-postgres-readonly`, T3.2 — 255 SELECT grants, zero write).
# Pro local PG is never touched (SYMBIOSIS Law 2). PII boundary: the dump contains
# client PII (UU PDP) → stays on Zero's machines only (Law 6, FileVault); on M5 the
# dumps dir is 700 / files 600. In Pro-side mode the dump transits the Pro (also a
# Zero machine, Law 6 OK) and is removed from the Pro after scp.
#
# TWO DUMP MODES (the `fly proxy` wireguard tunnel from M5 to Fly `sin` is unreliable —
# 40s timeouts — while from the Pro it comes up in ~5s; empirically verified 2026-06-12):
#   - local  : open `fly proxy` on THIS machine, pg_dump locally. Needs a working M5→Fly
#              wireguard tunnel. Fast when it works.
#   - pro     : ssh to the Pro, open the proxy + pg_dump THERE (stable Fly net, Pro keychain,
#              Pro pg_dump@17), then scp the .dump back to M5. The restore is ALWAYS local.
#   - auto    : try `local` first; if the proxy doesn't come up within PROXY_WAIT s, fall
#              back to `pro`. (default)
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
#         KEEP_DUMPS (default 3), DUMP_MODE (auto|local|pro, default auto),
#         PRO_SSH (default pro), PRO_PG17_BIN (default /opt/homebrew/opt/postgresql@17/bin),
#         PROXY_WAIT (default 25 — seconds to wait for a local proxy before pro fallback).

set -euo pipefail

PG17_BIN="${PG17_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
PROXY_PORT="${PROXY_PORT:-15432}"
FLY_PG_APP="${FLY_PG_APP:-nuzantara-postgres}"
DUMP_DIR="${DUMP_DIR:-$HOME/.nuzantara-db-snapshots}"
KEEP_DUMPS="${KEEP_DUMPS:-3}"
DUMP_MODE="${DUMP_MODE:-auto}"
PRO_SSH="${PRO_SSH:-pro}"
PRO_PG17_BIN="${PRO_PG17_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
PROXY_WAIT="${PROXY_WAIT:-25}"
DEV_DB="nuzantara_dev"
RO_ROLE="nuzantara_readonly"
KEYCHAIN_SERVICE="nuzantara-postgres-readonly"
DUMP_EXCLUDES=(--exclude-table-data='events_outbox' --exclude-table-data='olympus_heartbeats*')

export PATH="$PG17_BIN:$PATH"

log() { printf '[nuz-db-refresh] %s\n' "$*"; }
die() { printf '[nuz-db-refresh] ERROR: %s\n' "$*" >&2; exit 1; }

# --- preflight (local restore side — always needed) ------------------------
command -v pg_dump >/dev/null 2>&1 || die "pg_dump not found ($PG17_BIN) — is postgresql@17 installed?"
command -v pg_isready >/dev/null 2>&1 || die "pg_isready not found ($PG17_BIN)"
pg_isready -h 127.0.0.1 -p 5432 -q || die "local postgres not accepting on 127.0.0.1:5432 — brew services start postgresql@17"

mkdir -p "$DUMP_DIR"
chmod 700 "$DUMP_DIR"

# free space guard (need at least ~2GB headroom)
avail_kb="$(df -k "$DUMP_DIR" | awk 'NR==2 {print $4}')"
[ "${avail_kb:-0}" -gt 2000000 ] || die "less than ~2GB free at $DUMP_DIR — free space before refreshing"

STAMP="$(date +%Y%m%d-%H%M)"
DUMP_FILE="$DUMP_DIR/prod-$STAMP.dump"

# ===========================================================================
# DUMP — local or Pro-side. Sets $DUMP_FILE on success.
# ===========================================================================

# Discover the prod APP DB behind the readonly role, via an already-open proxy on $1:$2.
# CRITICAL (2026-06-12): the prod cluster has MULTIPLE non-template DBs —
#   nuzantara_backend (empty), nuzantara_memory (no clients), nuzantara_rag (11733 clients).
# A naive `ORDER BY datname LIMIT 1` picks `nuzantara_backend` (alphabetically first) → a 4K
# empty dump. We must pick the DB that ACTUALLY contains `public.clients`. We probe each
# candidate DB for the clients table (the app's anchor table) and return the first that has it.
# $NUZ_APP_DB env overrides the probe entirely if ever needed.
discover_db() {
    local host="$1" port="$2" db
    if [ -n "${NUZ_APP_DB:-}" ]; then printf '%s' "$NUZ_APP_DB"; return; fi
    for db in $(psql -h "$host" -p "$port" -U "$RO_ROLE" -d postgres -tAc \
        "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres','repmgr') ORDER BY datname;" \
        2>/dev/null); do
        if [ "$(psql -h "$host" -p "$port" -U "$RO_ROLE" -d "$db" -tAc \
            "SELECT to_regclass('public.clients') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')" = "t" ]; then
            printf '%s' "$db"; return
        fi
    done
    return 0
}

dump_local() {
    # Returns 0 on success (dump written to $DUMP_FILE), 1 on any failure (so auto can fall back).
    command -v fly >/dev/null 2>&1 || { log "local mode: flyctl not on PATH"; return 1; }
    fly auth whoami >/dev/null 2>&1 || { log "local mode: flyctl not authenticated"; return 1; }
    if lsof -ti:"$PROXY_PORT" >/dev/null 2>&1; then
        log "local mode: port $PROXY_PORT already bound (orphan proxy) — kill: kill \$(lsof -ti:$PROXY_PORT)"; return 1
    fi

    local RO_PASS
    RO_PASS="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)" || {
        log "local mode: Keychain entry '$KEYCHAIN_SERVICE' not found on M5"; return 1; }
    [ -n "$RO_PASS" ] || { log "local mode: Keychain entry empty"; return 1; }
    export PGPASSWORD="$RO_PASS"; RO_PASS=""

    log "local mode: opening fly proxy $PROXY_PORT → $FLY_PG_APP:5432 (wait ${PROXY_WAIT}s) ..."
    fly proxy "$PROXY_PORT":5432 -a "$FLY_PG_APP" >/tmp/nuz-db-localproxy.log 2>&1 &
    local PROXY_PID=$!
    # local teardown for this function only
    local up=0 i
    for i in $(seq 1 "$PROXY_WAIT"); do
        if pg_isready -h 127.0.0.1 -p "$PROXY_PORT" -q 2>/dev/null; then up=1; break; fi
        sleep 1
    done
    if [ "$up" -ne 1 ]; then
        log "local mode: proxy did not come up within ${PROXY_WAIT}s (M5→Fly wireguard tunnel issue)"
        kill "$PROXY_PID" 2>/dev/null; kill "$(lsof -ti:"$PROXY_PORT" 2>/dev/null)" 2>/dev/null
        unset PGPASSWORD; return 1
    fi
    log "local mode: proxy up on 127.0.0.1:$PROXY_PORT"

    local db; db="$(discover_db 127.0.0.1 "$PROXY_PORT")"
    if [ -z "$db" ]; then
        log "local mode: could not determine prod DB name via readonly role"
        kill "$PROXY_PID" 2>/dev/null; kill "$(lsof -ti:"$PROXY_PORT" 2>/dev/null)" 2>/dev/null
        unset PGPASSWORD; return 1
    fi
    log "local mode: prod DB to dump: $db"

    log "local mode: dumping (this can take a while) ..."
    if ! pg_dump -h 127.0.0.1 -p "$PROXY_PORT" -U "$RO_ROLE" -d "$db" \
            -Fc --no-owner --no-acl "${DUMP_EXCLUDES[@]}" \
            -f "$DUMP_FILE" 2>/tmp/nuz-db-dump.err; then
        log "local mode: pg_dump stderr:"; sed 's/^/    /' /tmp/nuz-db-dump.err >&2
        kill "$PROXY_PID" 2>/dev/null; kill "$(lsof -ti:"$PROXY_PORT" 2>/dev/null)" 2>/dev/null
        unset PGPASSWORD
        grep -qiE 'permission denied|must be (owner|superuser)' /tmp/nuz-db-dump.err \
            && die "readonly role hit a permission error mid-dump — STOP, surface to Antonello (do NOT escalate role)"
        return 1
    fi
    kill "$PROXY_PID" 2>/dev/null; kill "$(lsof -ti:"$PROXY_PORT" 2>/dev/null)" 2>/dev/null
    unset PGPASSWORD
    return 0
}

dump_pro() {
    # Run proxy + pg_dump ON THE PRO (stable Fly net + Pro keychain + Pro pg_dump@17),
    # then scp the .dump back to M5. The dump file is removed from the Pro afterwards.
    #
    # The remote pipeline is sent via a HEREDOC to `ssh … bash -lc 'cat | bash -s'` so the
    # SQL/quoting is NOT double-escaped (the prior attempt's chr()-cast hack is gone). The
    # remote script reads the Pro keychain into PGPASSWORD ON THE PRO (value never crosses the
    # wire, never printed), opens a Pro-local proxy on port 15498, discovers the prod DB name,
    # dumps to /tmp on the Pro. We pass config via positional args ($1..$5) to the remote bash.
    log "pro mode: dumping on $PRO_SSH (stable Fly net) then scp → M5 ..."
    local remote_dump="/tmp/nuz-prod-$STAMP.dump"

    ssh "$PRO_SSH" "bash -lc 'bash -s -- \"$PRO_PG17_BIN\" \"$KEYCHAIN_SERVICE\" \"$RO_ROLE\" \"$FLY_PG_APP\" \"$remote_dump\"'" <<'REMOTE' 2>&1 | sed 's/^/    [pro] /' >&2
set -uo pipefail
PG_BIN="$1"; KC_SERVICE="$2"; RO_ROLE="$3"; FLY_APP="$4"; OUT="$5"
RPORT=15498
export PATH="$PG_BIN:$PATH"
PSQL="$PG_BIN/psql"; PGDUMP="$PG_BIN/pg_dump"; PGREADY="$PG_BIN/pg_isready"

kill "$(lsof -ti:$RPORT 2>/dev/null)" 2>/dev/null || true
PGPASSWORD="$(security find-generic-password -s "$KC_SERVICE" -a "$RO_ROLE" -w 2>/dev/null)"
[ -n "$PGPASSWORD" ] || { echo "PRO-ERR: keychain '$KC_SERVICE' empty/missing on Pro"; exit 3; }
export PGPASSWORD

fly proxy "$RPORT":5432 -a "$FLY_APP" >/tmp/nuz-pro-proxy.log 2>&1 &
PP=$!
trap 'kill "$PP" 2>/dev/null; kill "$(lsof -ti:$RPORT 2>/dev/null)" 2>/dev/null' EXIT
up=0
for i in $(seq 1 30); do "$PGREADY" -h 127.0.0.1 -p "$RPORT" -q 2>/dev/null && { up=1; break; }; sleep 1; done
[ "$up" -eq 1 ] || { echo "PRO-ERR: proxy did not come up on $RPORT"; head -4 /tmp/nuz-pro-proxy.log; exit 4; }
echo "PRO: proxy up on $RPORT"

# Pick the DB that ACTUALLY has public.clients (NOT just the alphabetically-first non-template
# DB — that's nuzantara_backend, which is EMPTY; the real app DB is nuzantara_rag, 11733 clients).
DB=""
if [ -n "${NUZ_APP_DB:-}" ]; then
  DB="$NUZ_APP_DB"
else
  for cand in $("$PSQL" -h 127.0.0.1 -p "$RPORT" -U "$RO_ROLE" -d postgres -tAc \
      "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres','repmgr') ORDER BY datname;" 2>/dev/null); do
    has="$("$PSQL" -h 127.0.0.1 -p "$RPORT" -U "$RO_ROLE" -d "$cand" -tAc \
      "SELECT to_regclass('public.clients') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')"
    [ "$has" = "t" ] && { DB="$cand"; break; }
  done
fi
[ -n "$DB" ] || { echo "PRO-ERR: no non-template DB contains public.clients via readonly role"; exit 5; }
echo "PRO: prod DB = $DB"

"$PGDUMP" -h 127.0.0.1 -p "$RPORT" -U "$RO_ROLE" -d "$DB" -Fc --no-owner --no-acl \
  --exclude-table-data='events_outbox' --exclude-table-data='olympus_heartbeats*' \
  -f "$OUT" 2>/tmp/nuz-pro-dump.err || {
    echo "PRO-ERR: pg_dump failed"; sed 's/^/      /' /tmp/nuz-pro-dump.err
    grep -qiE 'permission denied|must be (owner|superuser)' /tmp/nuz-pro-dump.err && echo "PRO-ERR: permission error — do NOT escalate role (W38)"
    exit 6; }
chmod 600 "$OUT"
echo "PRO-DUMP-OK $(du -h "$OUT" | cut -f1)"
REMOTE
    # PIPESTATUS[0] is ssh's exit; sed is [1]. A non-zero remote bash propagates through ssh.
    local rc=${PIPESTATUS[0]}
    [ "$rc" -eq 0 ] || die "pro-side dump failed (rc=$rc; see [pro] lines above)"

    log "pro mode: scp $PRO_SSH:$remote_dump → $DUMP_FILE ..."
    scp -q "$PRO_SSH:$remote_dump" "$DUMP_FILE" || die "scp of the dump from the Pro failed"
    chmod 600 "$DUMP_FILE"
    # remove the PII-bearing dump from the Pro (keep it only on M5)
    ssh "$PRO_SSH" "rm -f $remote_dump" 2>/dev/null || log "warn: could not remove remote dump $remote_dump on the Pro"
    [ -s "$DUMP_FILE" ] || die "scp produced an empty dump file"
    return 0
}

case "$DUMP_MODE" in
    local) dump_local || die "local dump failed (DUMP_MODE=local)";;
    pro)   dump_pro;;
    auto)
        if dump_local; then :; else
            log "auto: local dump unavailable → falling back to Pro-side dump"
            dump_pro
        fi
        ;;
    *) die "unknown DUMP_MODE='$DUMP_MODE' (use auto|local|pro)";;
esac

[ -s "$DUMP_FILE" ] || die "no dump produced"
chmod 600 "$DUMP_FILE"
DUMP_SZ="$(du -h "$DUMP_FILE" | awk '{print $1}')"
log "dump OK: $DUMP_FILE ($DUMP_SZ)"

# ===========================================================================
# RESTORE — always local on M5 (PG17), into nuzantara_dev.
# ===========================================================================
log "recreating $DEV_DB ..."
dropdb -h 127.0.0.1 -p 5432 --if-exists "$DEV_DB"
createdb -h 127.0.0.1 -p 5432 "$DEV_DB"
log "restoring ..."
# Atomic recreate (dropdb+createdb) gives a clean target, so we do NOT use --single-transaction
# (it would abort on the first benign --no-owner notice). --exit-on-error (Codex panel MAJOR)
# surfaces a REAL restore error; benign "role does not exist" notices under --no-owner/--no-acl
# are warnings, not errors. Verified by the anchor-count check below.
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
