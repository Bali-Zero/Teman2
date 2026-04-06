#!/usr/bin/env bash
# Fly.io PostgreSQL Backup → Tigris (S3-compatible)
# Daily pg_dump from Fly postgres, compressed, uploaded to Tigris bucket
# Keeps last 7 backups locally + 30 on Tigris

set -euo pipefail

BACKUP_DIR="$HOME/backups/fly-postgres"
TIMESTAMP=$(date +%Y%m%d-%H%M)
BACKUP_FILE="$BACKUP_DIR/nuzantara-fly-$TIMESTAMP.sql.gz"
FLY_APP="nuzantara-postgres"
KEEP_LOCAL=7
KEEP_REMOTE=30
MAX_RETRIES=3
DUMP_TIMEOUT=180  # seconds per attempt — pg_dump takes ~60s, tunnel setup ~30s

# Tigris credentials (set by fly storage create)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID not set — set in ~/.zshrc.secrets}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY not set — set in ~/.zshrc.secrets}"

mkdir -p "$BACKUP_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Starting Fly.io PostgreSQL backup..."

# Step 0: Re-init WireGuard tunnel + wake up the postgres machine
log "Re-initializing WireGuard tunnel..."
fly wireguard reset 2>/dev/null || true
sleep 3
log "Waking up postgres machine..."
timeout 30 fly ssh console --app "$FLY_APP" -C "echo 'awake'" >/dev/null 2>&1 || true
sleep 3

# Step 1: pg_dump via fly ssh with retry + per-attempt timeout
DUMP_OK=false
for attempt in $(seq 1 $MAX_RETRIES); do
    log "pg_dump attempt $attempt/$MAX_RETRIES (timeout ${DUMP_TIMEOUT}s)..."
    rm -f "$BACKUP_FILE"
    # Dump to temp SQL file first (fly ssh prints banner to stdout — must strip)
    DUMP_TMP="$BACKUP_DIR/.dump_tmp_${attempt}.sql"
    rm -f "$DUMP_TMP"

    # Use timeout to prevent indefinite hang on tunnel issues
    timeout "$DUMP_TIMEOUT" fly ssh console --app "$FLY_APP" \
        -C "sh -c \"PGPASSWORD=${FLY_PG_PASSWORD:?FLY_PG_PASSWORD not set} pg_dump -h 127.0.0.1 -p 5432 -U backend_rag_v2 -d nuzantara_rag\"" \
        > "$DUMP_TMP" 2>/dev/null || true

    # Find where the actual SQL starts (skip fly ssh banner lines before --)
    SQL_START=$(grep -n "^--$\|^-- PostgreSQL" "$DUMP_TMP" | head -1 | cut -d: -f1)
    if [ -n "$SQL_START" ] && [ "$SQL_START" -gt 1 ]; then
        tail -n +"$SQL_START" "$DUMP_TMP" | gzip > "$BACKUP_FILE" || true
    else
        gzip < "$DUMP_TMP" > "$BACKUP_FILE" || true
    fi
    rm -f "$DUMP_TMP"

    # Verify it's not empty (at least 10KB — real dump is several MB)
    FILE_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat --printf=%s "$BACKUP_FILE" 2>/dev/null || echo 0)
    if [ "$FILE_SIZE" -gt 10240 ]; then
        SIZE_H=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup created: $BACKUP_FILE ($SIZE_H)"
        DUMP_OK=true
        break
    else
        log "WARNING: pg_dump attempt $attempt failed (file ${FILE_SIZE} bytes)"
        rm -f "$BACKUP_FILE"
    fi
    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
        log "Resetting WireGuard and waiting 15s before retry..."
        fly wireguard reset 2>/dev/null || true
        sleep 15
    fi
done

if [ "$DUMP_OK" = false ]; then
    log "ERROR: pg_dump failed after $MAX_RETRIES attempts!"
    exit 1
fi

# Step 2: Verify integrity
if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "Integrity check passed"
else
    log "ERROR: Backup file corrupted!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify pg_dump header (gunzip -t passes even for corrupt/empty SQL dumps)
if ! gunzip -c "$BACKUP_FILE" 2>/dev/null | grep -m1 "PostgreSQL database dump" > /dev/null 2>&1; then
    log "ERROR: Backup file does not contain valid pg_dump header — dump may be corrupt or empty"
    log "CRITICAL: pg_dump header missing in $BACKUP_FILE — backup integrity check FAILED"
    exit 1
fi
log "pg_dump header verified OK"

# Step 3: Upload to Tigris
if command -v aws &> /dev/null; then
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
else
    log "WARN: aws CLI not found, skipping Tigris upload. Install: brew install awscli"
fi

# Step 4: Cleanup old local backups
ls -t "$BACKUP_DIR"/nuzantara-fly-*.sql.gz 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) | xargs rm -f 2>/dev/null || true
log "Local backups kept: $KEEP_LOCAL"

log "Backup complete ✅"
