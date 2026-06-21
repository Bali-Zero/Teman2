#!/usr/bin/env bash
# qdrant-snapshot.sh — Qdrant Cloud Snapshot Backup → Tigris S3
# Creates per-collection snapshots, uploads individually to Tigris
# Retention: last 4 snapshots per collection on Tigris
# Cron: 0 4 * * 0 (Sunday 04:00 WITA, 1h after PG backup)

set -euo pipefail

BACKUP_DIR="$HOME/backups/qdrant-snapshots"
TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="$HOME/logs/qdrant-snapshots.log"
KEEP_LOCAL=4
KEEP_REMOTE=4

# ── Load secrets ────────────────────────────────────────────────────────────
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a; source "$SECRETS_FILE"; set +a
fi

# Qdrant Cloud credentials (from backend .env)
QDRANT_ENV="$HOME/Desktop/nuzantara/apps/backend-rag/.env"
if [[ -f "$QDRANT_ENV" ]]; then
    QDRANT_URL=$(grep '^QDRANT_URL=' "$QDRANT_ENV" | cut -d= -f2-)
    QDRANT_API_KEY=$(grep '^QDRANT_API_KEY=' "$QDRANT_ENV" | cut -d= -f2-)
else
    echo "ERROR: $QDRANT_ENV not found" | tee -a "$LOG_FILE"
    exit 1
fi

if [[ -z "${QDRANT_API_KEY:-}" ]]; then
    echo "ERROR: QDRANT_API_KEY not set" | tee -a "$LOG_FILE"
    exit 1
fi

# Tigris S3-compatible credentials (from secrets env)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:?Missing AWS_ACCESS_KEY_ID in secrets}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:?Missing AWS_SECRET_ACCESS_KEY in secrets}"

mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_FILE")"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# prune_server_snapshots COLLECTION
# Deletes ALL existing server-side snapshots for a collection BEFORE creating a
# new one. Rationale: server-side snapshots are ephemeral by design — the
# source-of-truth is the live collection + the dated history on Tigris. If the
# download/delete step ever fails (disk pressure, HTTP 000, --max-time burn),
# the old DELETE-on-failure path is skipped and snapshots pile up indefinitely
# (observed 2026-06-21: 134 stale snapshots / 16.45 GB across 11 collections,
# legal_unified_hybrid_hybrid alone 22 / 12.41 GB because it is skip-listed and
# never cleaned). The pileup eventually pressures disk until snapshot CREATE
# returns HTTP 000 and the whole backup TERMINAL-loops. Pruning first makes the
# steady state self-healing: at most 1 fresh server-side snapshot per collection
# at any time. Robust: continues even if an individual DELETE fails, logs each.
prune_server_snapshots() {
    local coll="$1"
    local existing
    existing=$(curl -sf --max-time 30 -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$coll/snapshots" 2>/dev/null \
        | python3 -c "import json,sys
try:
    [print(s['name']) for s in json.load(sys.stdin).get('result',[])]
except Exception:
    pass" 2>/dev/null)
    if [[ -z "$existing" ]]; then
        return 0
    fi
    local n
    n=$(echo "$existing" | wc -l | tr -d ' ')
    log "  Prune: $coll has $n existing server-side snapshot(s) — deleting before create"
    local old code
    while IFS= read -r old; do
        [[ -z "$old" ]] && continue
        code=$(curl -s --max-time 60 -o /dev/null -w "%{http_code}" -X DELETE \
            -H "api-key: $QDRANT_API_KEY" \
            "$QDRANT_URL/collections/$coll/snapshots/$old" 2>/dev/null) || code="000"
        if [[ "$code" == "200" ]]; then
            log "    pruned: $old"
        else
            log "    WARN: prune failed (HTTP $code): $old"
        fi
    done <<< "$existing"
}

log "=== qdrant-snapshot.sh START ==="
log "Target: $QDRANT_URL → s3://$TIGRIS_BUCKET/qdrant/"

# ── Step 1: List all collections ────────────────────────────────────────────
COLLECTIONS=$(curl -sf --max-time 30 \
    -H "api-key: $QDRANT_API_KEY" \
    "$QDRANT_URL/collections" \
    | python3 -c "import json,sys; [print(c['name']) for c in json.load(sys.stdin)['result']['collections']]" 2>/dev/null)

if [[ -z "$COLLECTIONS" ]]; then
    log "ERROR: Failed to list collections!"
    exit 1
fi

TOTAL_COLLECTIONS=$(echo "$COLLECTIONS" | wc -l | tr -d ' ')
log "Found $TOTAL_COLLECTIONS collections"

# ── Step 2: Snapshot + download + upload per collection ─────────────────────
TOTAL_SIZE=0
FAILED=0
SUCCEEDED=0

# Skiplist: collections known to stall on snapshot download.
# legal_unified_hybrid_hybrid: HTTP 000 timeout repeatedly (5min+) — likely a
# duplicate/abandoned mirror of legal_unified_2026, which downloads fine.
# Reviewed 2026-05-11. Remove from skiplist after Qdrant Cloud cleanup.
SKIP_COLLECTIONS="legal_unified_hybrid_hybrid"

for COLLECTION in $COLLECTIONS; do
    if echo " $SKIP_COLLECTIONS " | grep -q " $COLLECTION "; then
        # Skip create/download/upload — but STILL prune its stale server-side
        # snapshots. Skip-listed collections are the worst offenders for pileup
        # precisely because their download stalls, so the legacy cleanup never
        # ran (legal_unified_hybrid_hybrid held 12.41 GB on 2026-06-21).
        log "Skipping create/download: $COLLECTION (in SKIP_COLLECTIONS) — pruning stale snapshots only"
        prune_server_snapshots "$COLLECTION"
        continue
    fi
    log "Processing: $COLLECTION"

    # Prune-before-create: clear any pre-existing server-side snapshots so the
    # disk never accumulates effimeral snapshots across runs.
    prune_server_snapshots "$COLLECTION"

    # Create snapshot on Qdrant Cloud
    SNAP_RESPONSE=$(curl -sf --max-time 120 -X POST \
        -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots" 2>/dev/null) || {
        log "  ERROR: Failed to create snapshot for $COLLECTION"
        FAILED=$((FAILED + 1))
        continue
    }

    SNAP_NAME=$(echo "$SNAP_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['name'])" 2>/dev/null)

    if [[ -z "$SNAP_NAME" ]]; then
        log "  ERROR: Could not parse snapshot name for $COLLECTION"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Download snapshot locally
    OUTPUT_FILE="$BACKUP_DIR/${COLLECTION}_${TIMESTAMP}.snapshot"
    HTTP_CODE=$(curl -sf --max-time 300 -o "$OUTPUT_FILE" -w "%{http_code}" \
        -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" 2>/dev/null) || HTTP_CODE="000"

    if [[ "$HTTP_CODE" != "200" ]] || [[ ! -f "$OUTPUT_FILE" ]] || [[ ! -s "$OUTPUT_FILE" ]]; then
        log "  ERROR: Failed to download snapshot for $COLLECTION (HTTP $HTTP_CODE)"
        rm -f "$OUTPUT_FILE"
        FAILED=$((FAILED + 1))
        # Still try to delete server-side snapshot
        curl -sf --max-time 10 -X DELETE -H "api-key: $QDRANT_API_KEY" \
            "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" > /dev/null 2>&1 || true
        continue
    fi

    FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat --printf=%s "$OUTPUT_FILE" 2>/dev/null)
    FILE_SIZE_MB=$(echo "scale=1; $FILE_SIZE / 1048576" | bc)
    TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
    log "  Downloaded: ${FILE_SIZE_MB}MB → $OUTPUT_FILE"

    # Delete server-side snapshot to free Qdrant storage
    curl -sf --max-time 10 -X DELETE -H "api-key: $QDRANT_API_KEY" \
        "$QDRANT_URL/collections/$COLLECTION/snapshots/$SNAP_NAME" > /dev/null 2>&1 || true

    # Upload to Tigris: s3://nuzantara-backups/qdrant/{collection}_{date}.snapshot
    S3_KEY="qdrant/${COLLECTION}_${TIMESTAMP}.snapshot"
    if AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
       AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
       aws s3 cp "$OUTPUT_FILE" \
           "s3://$TIGRIS_BUCKET/$S3_KEY" \
           --endpoint-url "$TIGRIS_ENDPOINT" \
           --region auto 2>/dev/null; then
        log "  Uploaded: s3://$TIGRIS_BUCKET/$S3_KEY"

        # Retention: keep last KEEP_REMOTE per collection on Tigris
        # List all snapshots for this collection, delete old ones
        AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
        AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
        aws s3 ls "s3://$TIGRIS_BUCKET/qdrant/${COLLECTION}_" \
            --endpoint-url "$TIGRIS_ENDPOINT" \
            --region auto 2>/dev/null | sort -r | tail -n +$((KEEP_REMOTE + 1)) | awk '{print $4}' | while read -r old; do
            if [[ -n "$old" ]]; then
                AWS_ACCESS_KEY_ID="$TIGRIS_KEY" \
                AWS_SECRET_ACCESS_KEY="$TIGRIS_SECRET" \
                aws s3 rm "s3://$TIGRIS_BUCKET/qdrant/$old" \
                    --endpoint-url "$TIGRIS_ENDPOINT" \
                    --region auto 2>/dev/null
                log "  Removed old remote: $old"
            fi
        done
    else
        log "  WARN: Tigris upload failed for $COLLECTION"
    fi

    SUCCEEDED=$((SUCCEEDED + 1))
done

# ── Step 3: Cleanup old local snapshots (keep last KEEP_LOCAL per collection) ─
for COLLECTION in $COLLECTIONS; do
    ls -t "$BACKUP_DIR"/${COLLECTION}_*.snapshot 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) | xargs rm -f 2>/dev/null || true
done

TOTAL_SIZE_MB=$(echo "scale=1; $TOTAL_SIZE / 1048576" | bc)
log "=== COMPLETE: $SUCCEEDED/$TOTAL_COLLECTIONS OK, $FAILED failed, ${TOTAL_SIZE_MB}MB total ==="

# ── Rotate log if > 1MB ──────────────────────────────────────────────────────
if [[ -f "$LOG_FILE" ]] && [[ "$(wc -c < "$LOG_FILE")" -gt 1048576 ]]; then
    mv "$LOG_FILE" "$LOG_FILE.old"
fi

if [[ $SUCCEEDED -eq 0 ]]; then
    exit 1
fi

exit 0
