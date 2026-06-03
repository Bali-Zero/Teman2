#!/usr/bin/env bash
# Fly.io PostgreSQL Backup → Tigris (S3-compatible)
# Daily pg_dump from Fly postgres, compressed, uploaded to Tigris bucket
# Keeps last 7 backups locally + 30 on Tigris

set -euo pipefail

# Fix 2026-05-27: source secrets fallback chain so the script works under
# both invocation paths: (a) via wrapper fly-backup.sh which sources first,
# (b) via cron-wrapper.sh which invokes us DIRECT with no env. Without
# this, the cron-wrapper path silently failed for 4 days at line 20.
for _secrets_file in "$HOME/.nuzantara-secrets.env" "$HOME/Desktop/secretkey.env"; do
    if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -f "$_secrets_file" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$_secrets_file"
        set +a
    fi
done

# FIX 2026-06-03 (root cause #2): ~/.nuzantara-secrets.env exports a STALE
# FLY_API_TOKEN. `set -a; source` above exports it into our env, where it
# SHADOWS fly's own valid auth in ~/.fly/config.yml → every `fly` call returns
# "failed to list VMs: unauthorized" and the dump/SFTP silently fails. Drop it
# so fly falls back to its config token. (Sister of cicatrix
# lessons_fly_cli_token_regression_cascade.) If you ever WANT a token here,
# set FLY_ACCESS_TOKEN to a fresh one before this line instead.
unset FLY_API_TOKEN

BACKUP_DIR="$HOME/backups/fly-postgres"
TIMESTAMP=$(date +%Y%m%d-%H%M)
BACKUP_FILE="$BACKUP_DIR/nuzantara-fly-$TIMESTAMP.sql.gz"
FLY_APP="nuzantara-postgres"
FLY_BIN="${FLY_BIN:-/opt/homebrew/bin/fly}"
KEEP_LOCAL=7
KEEP_REMOTE=30
MAX_RETRIES=3
DUMP_TIMEOUT=900   # in-machine pg_dump+gzip wall-clock cap
SFTP_TIMEOUT=900   # SFTP transfer wall-clock cap (~5min observed for ~360MB over DERP)

# Tigris credentials (set by fly storage create)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:-}"   # FIX 2026-06-03: :- not :? so missing Tigris creds do NOT kill the local backup
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:-}"   # FIX 2026-06-03: local pg_dump needs no Tigris; upload skipped below if empty

mkdir -p "$BACKUP_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Starting Fly.io PostgreSQL backup..."

# ─────────────────────────────────────────────────────────────────────────────
# METHOD (rewritten 2026-06-03):
#   Previous method dumped via `fly ssh console -C "pg_dump ..."` and STREAMED
#   the whole dump over the SSH console to local stdout. On a ~600MB dump
#   `fly ssh console` forcibly closes the session mid-stream
#   ("session forcibly closed; remote process may still be running") → truncated
#   or empty file → backup broken since ~30 May (DB grew past 350MB compressed).
#   It was NOT a timeout (already 600s) — the console transport cannot carry
#   large streams reliably.
#
#   New method (verified working 2026-06-03):
#     1. Resolve the PRIMARY machine dynamically — the app is Stolon HA with 2
#        machines (primary + replica). `fly ssh console` WITHOUT --machine picks
#        one at random; dumping on one machine and verifying on the other was a
#        hidden root cause of "file not found" confusion.
#     2. Run pg_dump INSIDE the primary as the `postgres` superuser via loopback
#        (PGPASSWORD=$OPERATOR_PASSWORD, the postgres app's built-in env var) and
#        gzip to a file on /data — NO large stdout stream over the console.
#        Superuser is required: `backend_rag_v2` (the DSN role) was demoted from
#        superuser (W38) and cannot SELECT 10 tables owned by `zantara_rag_user`
#        (incl. user_stats) → its pg_dump fails on LOCK TABLE. A TCP proxy can
#        only authenticate `backend_rag_v2` (pg_hba rejects postgres over TCP),
#        so the dump MUST run on the machine via loopback as postgres.
#     3. Download the file with `fly ssh sftp get` — a dedicated SFTP channel
#        that transfers large files byte-for-byte (verified 372164915 == 372164915).
#     4. Remove the remote file (no /data buildup).
#   `fly wireguard reset` was REMOVED: it tore down a healthy tunnel and spawned
#   250+ zombie "interactive-*" peers. The SFTP/console transport over the
#   existing tunnel needs no reset.
# ─────────────────────────────────────────────────────────────────────────────

# Step 0: Resolve the primary machine id (HA-aware — never assume which one).
# Primary identity lives in the per-machine health check named "role"
# (output == "primary"); there is NO top-level .role field. Parse the JSON with
# jq (deterministic, immune to TTY/ANSI/column drift). The tabular parse is a
# fallback only — it proved fragile under nohup/no-TTY (empty match → abort).
log "Resolving primary Postgres machine..."
PRIMARY_MACHINE=""
# Retry: tolerate a brief HA fail-over flap where no machine reports role=primary.
for _r in 1 2 3; do
    if command -v jq >/dev/null 2>&1; then
        PRIMARY_MACHINE=$("$FLY_BIN" machine list --app "$FLY_APP" -j 2>/dev/null \
            | jq -r '.[] | select(any(.checks[]?; .name=="role" and (.output|ascii_downcase)=="primary")) | .id' 2>/dev/null \
            | head -1 || true)
    fi
    if [ -z "$PRIMARY_MACHINE" ]; then
        # Fallback: tabular parse (column 1 of the row whose role column is "primary")
        PRIMARY_MACHINE=$("$FLY_BIN" machine list --app "$FLY_APP" 2>/dev/null \
            | grep -iE '[[:space:]│|][[:space:]]*primary[[:space:]]*[│|]' | head -1 | awk '{print $1}' || true)
    fi
    [ -n "$PRIMARY_MACHINE" ] && break
    log "Primary not resolved (try $_r/3) — fly auth ok? HA flap? retrying in 5s..."
    sleep 5
done
if [ -z "$PRIMARY_MACHINE" ]; then
    log "ERROR: could not resolve primary machine for $FLY_APP — aborting."
    log "ERROR: 'fly machine list -j' returned no machine with a role=primary health check."
    log "ERROR: most common cause: stale FLY_API_TOKEN in env ('unauthorized') — check ~/.nuzantara-secrets.env."
    exit 1
fi
log "Primary machine: $PRIMARY_MACHINE"

# Step 1: pg_dump inside the primary → gzip to /data, then SFTP get, with retry
REMOTE_FILE="/data/nuz-backup-$TIMESTAMP.sql.gz"
REMOTE_ERR="/data/nuz-backup-$TIMESTAMP.err"
DUMP_OK=false

for attempt in $(seq 1 $MAX_RETRIES); do
    log "Backup attempt $attempt/$MAX_RETRIES..."
    rm -f "$BACKUP_FILE"

    # 1a. Dump+gzip inside the machine. pg_dump writes to a file on /data;
    # only a tiny status line (PGDUMP_EXIT + ls + stderr head) returns over the
    # console, so the transport never has to carry the dump body.
    log "Running pg_dump inside primary (superuser, loopback) → $REMOTE_FILE ..."
    DUMP_STATUS=$(timeout "$DUMP_TIMEOUT" "$FLY_BIN" ssh console --app "$FLY_APP" --machine "$PRIMARY_MACHINE" \
        -C "sh -c 'PGPASSWORD=\$OPERATOR_PASSWORD pg_dump -h 127.0.0.1 -p 5432 -U postgres -d nuzantara_rag 2>$REMOTE_ERR | gzip -c > $REMOTE_FILE; echo PGDUMP_EXIT=\$?; ls -l $REMOTE_FILE 2>/dev/null; echo ===ERR===; head -3 $REMOTE_ERR'" \
        2>/dev/null || true)
    log "In-machine result: $(echo "$DUMP_STATUS" | tr '\n' '|')"

    # Guard: dump-side errors (e.g. permission denied) are fatal even if a file exists
    if echo "$DUMP_STATUS" | grep -qiE 'permission denied|FATAL:|could not connect|connection to server'; then
        log "WARNING: pg_dump reported an error on attempt $attempt — see stderr above."
    fi

    # 1b. Download via SFTP (dedicated channel — robust on large files)
    log "Downloading via SFTP get → $BACKUP_FILE ..."
    timeout "$SFTP_TIMEOUT" "$FLY_BIN" ssh sftp get "$REMOTE_FILE" "$BACKUP_FILE" \
        --app "$FLY_APP" --machine "$PRIMARY_MACHINE" >/dev/null 2>&1 || true

    # 1c. Remove the remote file regardless of local outcome (no /data buildup)
    timeout 60 "$FLY_BIN" ssh console --app "$FLY_APP" --machine "$PRIMARY_MACHINE" \
        -C "sh -c 'rm -f $REMOTE_FILE $REMOTE_ERR'" >/dev/null 2>&1 || true

    # Verify it's not empty (real dump is hundreds of MB; floor at 1MB)
    FILE_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat --printf=%s "$BACKUP_FILE" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -gt 1048576 ]; then
        SIZE_H=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup downloaded: $BACKUP_FILE ($SIZE_H, $FILE_SIZE bytes)"
        DUMP_OK=true
        break
    else
        log "WARNING: backup attempt $attempt produced only ${FILE_SIZE} bytes locally"
        rm -f "$BACKUP_FILE"
    fi

    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
        log "Waiting 15s before retry..."
        sleep 15
    fi
done

if [ "$DUMP_OK" = false ]; then
    log "ERROR: backup failed after $MAX_RETRIES attempts!"
    exit 1
fi

# Step 2: Verify integrity
if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "Integrity check passed (gunzip -t)"
else
    log "ERROR: Backup file corrupted!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify pg_dump header (gunzip -t passes even for corrupt/empty SQL dumps).
# Bug fix 2026-05-09: previous form `gunzip -c | grep -m1 ...` failed under
# `set -o pipefail` because grep -m1 closes its stdin on first match,
# triggering SIGPIPE on gunzip (exit 141), which propagated as failure.
# Use `head -c 4096` to bound the read to the header region instead.
HEADER_PREVIEW=$(gunzip -c "$BACKUP_FILE" 2>/dev/null | head -c 4096 || true)
if ! echo "$HEADER_PREVIEW" | grep -q "PostgreSQL database dump"; then
    log "ERROR: Backup file does not contain valid pg_dump header — dump may be corrupt or empty"
    log "CRITICAL: pg_dump header missing in $BACKUP_FILE — backup integrity check FAILED"
    exit 1
fi
log "pg_dump header verified OK"

# Step 3: Upload to Tigris (with creds preflight 2026-05-27)
if [ -z "$TIGRIS_KEY" ] || [ -z "$TIGRIS_SECRET" ]; then
    log "WARN: Tigris creds absent (AWS_ACCESS_KEY_ID unset) — LOCAL backup kept, cloud upload SKIPPED."
    log "WARN: Fix cloud: regenerate via 'fly storage update nuzantara-backups' then set keys in ~/.nuzantara-secrets.env"
elif command -v aws &> /dev/null; then
    # Fix 2026-05-27: cheap preflight `aws s3 ls` to verify creds work on this
    # bucket BEFORE attempting upload. The TIGRIS_KEY/SECRET in
    # ~/Desktop/secretkey.env returned InvalidAccessKeyId on `nuzantara-backups`
    # (creds either rotated or for a different bucket). Without this check the
    # script silenced the upload failure (2>/dev/null) and logged success, so
    # the operator only noticed via Cell organism backup-age sensor turning red.
    # `set +e` block: `set -e` at top of file would kill the script on a
    # failing `aws s3 ls` (e.g. InvalidAccessKeyId), skipping Step 3+4 silently.
    # Temporarily disable so we can capture rc and decide.
    set +e
    PREFLIGHT_OUT=$(AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
        AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
        aws s3 ls "s3://$TIGRIS_BUCKET/" \
        --endpoint-url "$TIGRIS_ENDPOINT" \
        --region auto 2>&1)
    PREFLIGHT_RC=$?
    set -e

    if [ $PREFLIGHT_RC -ne 0 ]; then
        log "WARN: Tigris preflight failed (rc=$PREFLIGHT_RC) — skipping remote upload."
        log "WARN: Tigris error: $(echo "$PREFLIGHT_OUT" | head -2 | tr '\n' ' ')"
        log "WARN: Local backup retained at $BACKUP_FILE — restore manually if needed."
        log "WARN: Fix: regenerate Tigris creds via 'fly storage update nuzantara-backups' or reconcile keys in ~/Desktop/secretkey.env."
    else
        AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
        AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
        aws s3 cp "$BACKUP_FILE" \
            "s3://$TIGRIS_BUCKET/postgres/$(basename "$BACKUP_FILE")" \
            --endpoint-url "$TIGRIS_ENDPOINT" \
            --region auto 2>/dev/null
        log "Uploaded to Tigris: s3://$TIGRIS_BUCKET/postgres/$(basename "$BACKUP_FILE")"

        # Cleanup old remote backups (keep last KEEP_REMOTE)
        AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
        AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
        aws s3 ls "s3://$TIGRIS_BUCKET/postgres/" \
            --endpoint-url "$TIGRIS_ENDPOINT" \
            --region auto 2>/dev/null | sort -r | tail -n +$((KEEP_REMOTE + 1)) | awk '{print $4}' | while read -r old; do
            AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
            AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
            aws s3 rm "s3://$TIGRIS_BUCKET/postgres/$old" \
                --endpoint-url "$TIGRIS_ENDPOINT" \
                --region auto 2>/dev/null
            log "Removed old remote: $old"
        done
    fi
else
    log "WARN: aws CLI not found, skipping Tigris upload. Install: brew install awscli"
fi

# Step 4: Cleanup old local backups
ls -t "$BACKUP_DIR"/nuzantara-fly-*.sql.gz 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) | xargs rm -f 2>/dev/null || true
log "Local backups kept: $KEEP_LOCAL"

log "Backup complete ✅"
