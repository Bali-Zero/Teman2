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
# DUMP MODES (the `fly proxy` wireguard tunnel from M5 to Fly `sin` is unreliable —
# 40s timeouts, drops mid-dump — while from the Pro it comes up in ~5s; verified 2026-06-12):
#   - fly-ssh : run pg_dump INSIDE the Fly PG machine and stream the -Fc dump over the
#               `fly ssh console` stdout pipe. The tunnel only has to survive ONE stdout
#               stream (pg_dump's work is server-side), so it does NOT drop mid-dump like
#               `local`. No Pro dependency. Retries the stream (tunnel handshake is flaky).
#               PG listens TCP 127.0.0.1:5433 in-container (no unix socket); readonly role.
#   - local   : open `fly proxy` on THIS machine, pg_dump locally. Needs a working M5→Fly
#               wireguard tunnel. Drops mid-dump on large DBs (the original AC4 blocker).
#   - pro     : ssh to the Pro, open the proxy + pg_dump THERE (stable Fly net, Pro keychain,
#               Pro pg_dump@17), then scp the .dump back to M5. The restore is ALWAYS local.
#   - auto    : try `fly-ssh` → `local` → `pro` in order. (default)
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
#         KEEP_DUMPS (default 3), DUMP_MODE (auto|local|pro|fly-ssh, default auto),
#         PRO_SSH (default pro), PRO_PG17_BIN (default /opt/homebrew/opt/postgresql@17/bin),
#         PROXY_WAIT (default 25 — seconds to wait for a local proxy before pro fallback),
#         NUZ_APP_DB (override the clients-table DB probe), FLY_PG_PORT (default 5433 —
#         in-container postgres TCP port), FLY_PGDUMP/FLY_PSQL (default /usr/lib/postgresql/17/bin/*),
#         FLY_SSH_RETRIES (default 4 — stream retries for the flaky tunnel),
#         FLY_SSH_TIMEOUT (default 300 — per-attempt wall-clock watchdog; the tunnel can HANG a
#         single fly-ssh attempt for ~19min, so each attempt is SIGKILLed past this).

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

# POSIX single-quote shell-escape: wrap in '...' and replace each ' with '\''.
# Used to pass the multi-line remote script as ONE safe arg to `bash -c` over `fly ssh`
# (so stdin stays free for the password — see dump_fly_ssh W65 note). Contains no secret.
_shq() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

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

dump_fly_ssh() {
    # Container-side dump: run pg_dump INSIDE the Fly Postgres machine and stream the
    # custom-format dump over the `fly ssh console` stdout pipe to $DUMP_FILE on M5.
    #
    # Why this beats `local`/`pro`: the M5→Fly wireguard tunnel only has to survive ONE
    # long-lived stdout stream — pg_dump's actual work happens server-side, in-container,
    # never byte-by-byte across the tunnel (which is what made `local` drop mid-dump:
    # `server closed connection unexpectedly … EXECUTE dumpFunc`). Empirically the tunnel
    # is intermittent (~1-in-3 console handshakes), so we retry the whole stream.
    #
    # Constraints honored: readonly role nuzantara_readonly (NEVER the in-container
    # superuser `connect` helper — that's postgres:$OPERATOR_PASSWORD, a W38 escalation);
    # RO password read from the M5 Keychain into a var, piped to the remote `bash -c` via
    # stdin (NEVER on argv → never in the container's `ps`/argv, W65); pg_dump @ PG17 in the
    # container (/usr/lib/postgresql/17/bin) matches local PG17 → clean pg_restore.
    #
    # The Fly postgres-flex 17.2 image has NO unix socket (unix_socket_directories empty);
    # postgres listens on TCP 127.0.0.1:5433 (5432 is haproxy/flycast). So -h 127.0.0.1 -p 5433.
    command -v fly >/dev/null 2>&1 || { log "fly-ssh mode: flyctl not on PATH"; return 1; }
    fly auth whoami >/dev/null 2>&1 || { log "fly-ssh mode: flyctl not authenticated"; return 1; }

    local FLY_PG_PORT="${FLY_PG_PORT:-5433}"
    local FLY_PGDUMP="${FLY_PGDUMP:-/usr/lib/postgresql/17/bin/pg_dump}"
    local FLY_PSQL="${FLY_PSQL:-/usr/lib/postgresql/17/bin/psql}"
    local FLY_SSH_RETRIES="${FLY_SSH_RETRIES:-4}"

    local RO_PASS
    RO_PASS="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null)" || {
        log "fly-ssh mode: Keychain entry '$KEYCHAIN_SERVICE' not found on M5"; return 1; }
    [ -n "$RO_PASS" ] || { log "fly-ssh mode: Keychain entry empty"; return 1; }

    # Discover the PRIMARY machine id (repmgr primary). Machine ids change on redeploy, so
    # never hardcode. `fly status` lists machines; the role column marks the primary.
    local MACHINE
    MACHINE="$(fly status -a "$FLY_PG_APP" 2>/dev/null \
        | awk 'tolower($0) ~ /primary/ {print $1; exit}')"
    if [ -z "$MACHINE" ]; then
        log "fly-ssh mode: could not find primary machine id via 'fly status -a $FLY_PG_APP'"; RO_PASS=""; return 1
    fi
    log "fly-ssh mode: primary machine = $MACHINE (port $FLY_PG_PORT, role $RO_ROLE)"

    # Remote script: carried in the `-C` command arg (it holds NO secret — only the dump
    # logic). The RO password is the SOLE thing on stdin; the script's `read` consumes it.
    #
    # CRITICAL (W65 fix, 2026-06-12): do NOT pipe "password\n + script" into `bash -s`.
    # With `bash -s`, STDIN *is* the script source, so line 1 (the password) would be parsed
    # as a bash command → `command not found: <password>` → leak to remote stderr (observed
    # empirically on handshake-race rc=0 attempts). The fix: script goes in `-C`, stdin
    # carries ONLY the password → the script reads it, it never reaches a command position.
    # The script body is config-templated (unquoted heredoc) but contains no credential.
    local remote_script
    remote_script="$(cat <<REMOTE
set -uo pipefail
IFS= read -r RO_PASS_IN || { echo "FLYSSH-ERR: no password on stdin" >&2; exit 7; }
[ -n "\$RO_PASS_IN" ] || { echo "FLYSSH-ERR: empty password on stdin" >&2; exit 7; }
export PGPASSWORD="\$RO_PASS_IN"; RO_PASS_IN=""
H=127.0.0.1; P=$FLY_PG_PORT; RO='$RO_ROLE'
PGD='$FLY_PGDUMP'; PSQL='$FLY_PSQL'
DB="\${NUZ_APP_DB:-}"
if [ -z "\$DB" ]; then
  for cand in \$("\$PSQL" -h "\$H" -p "\$P" -U "\$RO" -d postgres -tAc \
      "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres','repmgr') ORDER BY datname;" 2>/dev/null); do
    has="\$("\$PSQL" -h "\$H" -p "\$P" -U "\$RO" -d "\$cand" -tAc "SELECT to_regclass('public.clients') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')"
    [ "\$has" = t ] && { DB="\$cand"; break; }
  done
fi
[ -n "\$DB" ] || { echo "FLYSSH-ERR: no non-template DB has public.clients via readonly role" >&2; exit 5; }
echo "FLYSSH: dumping DB=\$DB" >&2
"\$PGD" -h "\$H" -p "\$P" -U "\$RO" -d "\$DB" -Fc --no-owner --no-acl \
  --exclude-table-data='events_outbox' --exclude-table-data='olympus_heartbeats*' 2>/tmp/flyssh-dump.err
rc=\$?
if [ "\$rc" -ne 0 ]; then
  sed 's/^/FLYSSH-ERR: /' /tmp/flyssh-dump.err >&2
  grep -qiE 'permission denied|must be (owner|superuser)' /tmp/flyssh-dump.err && echo "FLYSSH-PERM: do NOT escalate role (W38)" >&2
  exit 6
fi
REMOTE
)"

    # Per-attempt wall-clock watchdog: the Fly tunnel can HANG an individual `fly ssh console`
    # mid-stream indefinitely (19-min hang observed 2026-06-12), not just fail fast — a single
    # stuck attempt would blow the whole retry budget. macOS /bin/bash has no `timeout(1)`, so we
    # run the console in the background and a watchdog SIGKILLs it after FLY_SSH_TIMEOUT seconds.
    local FLY_SSH_TIMEOUT="${FLY_SSH_TIMEOUT:-300}"  # 5 min — generous for a ~15M dump, < the 19m hang
    local attempt rc child wd
    for attempt in $(seq 1 "$FLY_SSH_RETRIES"); do
        log "fly-ssh mode: dump attempt $attempt/$FLY_SSH_RETRIES (streaming -Fc, ${FLY_SSH_TIMEOUT}s watchdog) ..."
        # stdin = ONLY the RO password (consumed by the script's `read`). The script runs via
        # `-C` (bash -c <script>), so a partial/raced handshake can't echo the password as a
        # command — stdin is data, not the script source. stdout = the -Fc dump → $DUMP_FILE.
        printf '%s\n' "$RO_PASS" \
            | fly ssh console -a "$FLY_PG_APP" --machine "$MACHINE" --pty=false \
                -C "/bin/bash -c $(_shq "$remote_script")" >"$DUMP_FILE" 2>/tmp/flyssh.err &
        child=$!
        # Watchdog: after the timeout, hard-kill the (likely-hung) console child.
        ( sleep "$FLY_SSH_TIMEOUT"; kill -9 "$child" 2>/dev/null ) &
        wd=$!
        if wait "$child"; then rc=0; else rc=$?; fi
        # Stop the watchdog if the attempt finished on its own.
        kill "$wd" 2>/dev/null; wait "$wd" 2>/dev/null || true
        # rc 137 = SIGKILL by the watchdog (timed-out hang) → treat as a retryable failure.
        if [ "$rc" -eq 137 ]; then
            log "fly-ssh mode: attempt $attempt HUNG > ${FLY_SSH_TIMEOUT}s — watchdog killed it (tunnel stall)"
        fi
        # Permission error = STOP (never retry into a role escalation, W38)
        if grep -q 'FLYSSH-PERM' /tmp/flyssh.err 2>/dev/null; then
            RO_PASS=""; unset PGPASSWORD 2>/dev/null || true
            sed 's/^/    /' /tmp/flyssh.err >&2
            die "readonly role hit a permission error mid-dump — STOP, surface to Antonello (do NOT escalate role)"
        fi
        # Success = rc 0 AND a non-trivial custom-format dump (header magic 'PGDMP', > 1KB)
        if [ "$rc" -eq 0 ] && [ -s "$DUMP_FILE" ] \
            && [ "$(wc -c <"$DUMP_FILE")" -gt 1024 ] \
            && head -c 5 "$DUMP_FILE" | grep -q 'PGDMP'; then
            RO_PASS=""; unset PGPASSWORD 2>/dev/null || true
            log "fly-ssh mode: dump streamed OK ($(du -h "$DUMP_FILE" | cut -f1))"
            return 0
        fi
        log "fly-ssh mode: attempt $attempt failed (rc=$rc, size=$(wc -c <"$DUMP_FILE" 2>/dev/null || echo 0)B). Remote stderr:"
        sed 's/^/    /' /tmp/flyssh.err >&2 2>/dev/null || true
        rm -f "$DUMP_FILE"
        [ "$attempt" -lt "$FLY_SSH_RETRIES" ] && sleep 5
    done
    RO_PASS=""; unset PGPASSWORD 2>/dev/null || true
    log "fly-ssh mode: all $FLY_SSH_RETRIES attempts failed (tunnel intermittent — retry later)"
    return 1
}

case "$DUMP_MODE" in
    local)   dump_local || die "local dump failed (DUMP_MODE=local)";;
    pro)     dump_pro;;
    fly-ssh) dump_fly_ssh || die "fly-ssh dump failed (DUMP_MODE=fly-ssh)";;
    auto)
        # Order: fly-ssh (most robust — tunnel survives one stream, no Pro dependency) →
        # local (M5 proxy, drops mid-dump) → pro (needs Pro reachable).
        if dump_fly_ssh; then :
        elif dump_local; then :
        else
            log "auto: fly-ssh + local both unavailable → falling back to Pro-side dump"
            dump_pro
        fi
        ;;
    *) die "unknown DUMP_MODE='$DUMP_MODE' (use auto|local|pro|fly-ssh)";;
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
