#!/usr/bin/env bash
# Qdrant Cloud Backup → Tigris (S3-compatible)
# Creates snapshots for all collections, downloads them, uploads to Tigris
# Keeps last 7 backups locally + 30 on Tigris
# Run daily via cron (recommended: 03:30 WITA, after pg backup at 03:00)

set -euo pipefail

BACKUP_DIR="$HOME/backups/qdrant-snapshots"
TIMESTAMP=$(date +%Y%m%d-%H%M)
SESSION_DIR="$BACKUP_DIR/$TIMESTAMP"
KEEP_LOCAL=7
KEEP_REMOTE=30

# Qdrant Cloud credentials (from backend .env)
QDRANT_ENV="$HOME/Projects/nuzantara/apps/backend-rag/.env"
if [[ -f "$QDRANT_ENV" ]]; then
    QDRANT_URL=$(grep '^QDRANT_URL=' "$QDRANT_ENV" | cut -d= -f2-)
    QDRANT_API_KEY=$(grep '^QDRANT_API_KEY=' "$QDRANT_ENV" | cut -d= -f2-)
else
    echo "ERROR: $QDRANT_ENV not found"
    exit 1
fi

# Tigris credentials (same as pg backup)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:-tid_sZQYyrgouAXAdQDuvsfPlLIIUMMvEDNhfMWmzCdeouELsPMn_U}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:-tsec_5knItu7FoHkkv2P5qaEMSRdHxXDNb6ZD0+mgDfLsLF-lLntRwDUgrH4qmzhJX+3OI4XYTc}"

# Telegram alert (optional)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-413539912}"

mkdir -p "$SESSION_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
alert() {
    log "ALERT: $*"
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="⚠️ Qdrant Backup: $*" \
            -d parse_mode="Markdown" > /dev/null 2>&1 || true
    fi
}

log "Starting Qdrant Cloud backup..."
log "URL: $QDRANT_URL"

# Step 1: List all collections
COLLECTIONS=$(curl -sf -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/collections" \
    | python3 -c "import json,sys; [print(c['name']) for c in json.load(sys.stdin)['result']['collections']]" 2>/dev/null)

if [[ -z "$COLLECTIONS" ]]; then
    alert "Failed to list collections!"
    exit 1
fi

TOTAL_COLLECTIONS=$(echo "$COLLECTIONS" | wc -l | tr -d ' ')
log "Found $TOTAL_COLLECTIONS collections"

# Step 2: Create snapshot + download for each collection
TOTAL_SIZE=0
FAILED=0
SUCCEEDED=0

for COLLECTION in $COLLECTIONS; do
    log "Backing up: $COLLECTION"

    # Create snapshot
    SNAP_RESPONSE=$(curl -sf -X POST \
        -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots" 2>/dev/null) || {
        log "ERROR: Failed to create snapshot for $COLLECTION"
        FAILED=$((FAILED + 1))
        continue
    }

    SNAP_NAME=$(echo "$SNAP_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['name'])" 2>/dev/null)
    SNAP_SIZE=$(echo "$SNAP_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['size'])" 2>/dev/null)

    if [[ -z "$SNAP_NAME" ]]; then
        log "ERROR: Could not parse snapshot name for $COLLECTION"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Download snapshot
    OUTPUT_FILE="$SESSION_DIR/${COLLECTION}.snapshot"
    HTTP_CODE=$(curl -sf -o "$OUTPUT_FILE" -w "%{http_code}" \
        -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" 2>/dev/null) || HTTP_CODE="000"

    if [[ "$HTTP_CODE" != "200" ]] || [[ ! -f "$OUTPUT_FILE" ]]; then
        log "ERROR: Failed to download snapshot for $COLLECTION (HTTP $HTTP_CODE)"
        rm -f "$OUTPUT_FILE"
        FAILED=$((FAILED + 1))
        continue
    fi

    FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat --printf=%s "$OUTPUT_FILE" 2>/dev/null)
    FILE_SIZE_MB=$(echo "scale=1; $FILE_SIZE / 1048576" | bc)
    TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
    log "  Downloaded: ${FILE_SIZE_MB}MB"

    # Delete remote snapshot (cleanup server-side)
    curl -sf -X DELETE -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" > /dev/null 2>&1 || true

    SUCCEEDED=$((SUCCEEDED + 1))
done

TOTAL_SIZE_MB=$(echo "scale=1; $TOTAL_SIZE / 1048576" | bc)
log "Snapshots: $SUCCEEDED/$TOTAL_COLLECTIONS succeeded, $FAILED failed (${TOTAL_SIZE_MB}MB total)"

if [[ $SUCCEEDED -eq 0 ]]; then
    alert "ALL snapshots failed! 0/$TOTAL_COLLECTIONS succeeded."
    exit 1
fi

# Step 3: Compress session directory
ARCHIVE="$BACKUP_DIR/qdrant-$TIMESTAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$BACKUP_DIR" "$TIMESTAMP"
ARCHIVE_SIZE=$(du -h "$ARCHIVE" | cut -f1)
log "Archive created: $ARCHIVE ($ARCHIVE_SIZE)"

# Remove uncompressed session dir
rm -rf "$SESSION_DIR"

# Step 4: Upload to Tigris
if command -v aws &> /dev/null; then
    if AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
       AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
       aws s3 cp "$ARCHIVE" \
           "s3://$TIGRIS_BUCKET/qdrant/$(basename "$ARCHIVE")" \
           --endpoint-url "$TIGRIS_ENDPOINT" \
           --region auto 2>/dev/null; then
        log "Uploaded to Tigris: s3://$TIGRIS_BUCKET/qdrant/$(basename "$ARCHIVE")"

        # Cleanup old remote backups (keep last KEEP_REMOTE)
        AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
        AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
        aws s3 ls "s3://$TIGRIS_BUCKET/qdrant/" \
            --endpoint-url "$TIGRIS_ENDPOINT" \
            --region auto 2>/dev/null | sort -r | tail -n +$((KEEP_REMOTE + 1)) | awk '{print $4}' | while read -r old; do
            AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
            AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
            aws s3 rm "s3://$TIGRIS_BUCKET/qdrant/$old" \
                --endpoint-url "$TIGRIS_ENDPOINT" \
                --region auto 2>/dev/null
            log "Removed old remote: $old"
        done
    else
        log "WARN: Tigris upload failed"
    fi
else
    log "WARN: aws CLI not found, skipping Tigris upload. Install: brew install awscli"
fi

# Step 5: Cleanup old local backups
ls -t "$BACKUP_DIR"/qdrant-*.tar.gz 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) | xargs rm -f 2>/dev/null || true
log "Local backups kept: $KEEP_LOCAL"

# Step 6: Summary
if [[ $FAILED -gt 0 ]]; then
    alert "Completed with errors: $SUCCEEDED/$TOTAL_COLLECTIONS OK, $FAILED failed ($ARCHIVE_SIZE)"
else
    log "Backup complete: $SUCCEEDED/$TOTAL_COLLECTIONS collections, $ARCHIVE_SIZE compressed"
    # Success notification (only if Telegram configured)
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="✅ Qdrant backup OK: $SUCCEEDED/$TOTAL_COLLECTIONS collections, $ARCHIVE_SIZE" \
            > /dev/null 2>&1 || true
    fi
fi
