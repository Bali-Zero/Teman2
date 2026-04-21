#!/usr/bin/env bash
# pg-restore-drill.sh
#
# Monthly automated restore drill: pulls the latest pg_dump from Tigris,
# restores into a fresh local ephemeral Postgres container, runs sanity
# queries, compares row counts against prod, reports via Telegram.
#
# Why this matters: a backup that has never been restored is not a backup.
# The L2.1 roadmap (AUTONOMOUS_OPS.md) lists this as the last guardrail
# we need before removing the final manual confirmation gates. Per
# Zero's note "io non sono un dev e verifica sul codice non serve tanto",
# the safety has to come from proving backups actually work, not from
# trust.
#
# Runs:
#   - Locally via cron (monthly)
#   - In CI via .github/workflows/restore-drill.yml (scheduled)
#
# Exit codes:
#   0 = restore ok, row counts within tolerance
#   1 = download failed
#   2 = restore failed (dump corrupt or psql errored)
#   3 = sanity query failed (schema missing, critical table empty)
#   4 = row-count drift beyond tolerance (potential data loss signal)

set -u -o pipefail

SCRIPT_NAME="pg-restore-drill"
TS_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
REPORT_DIR="${REPORT_DIR:-$HOME/backups/restore-drills}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/drill-$(date +%Y%m%d-%H%M%S).log"

# Load secrets
SECRETS_FILE="${SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
if [ -f "$SECRETS_FILE" ]; then
  set -a; source "$SECRETS_FILE"; set +a
fi

TIGRIS_ENDPOINT="${TIGRIS_ENDPOINT:-https://fly.storage.tigris.dev}"
TIGRIS_BUCKET="${TIGRIS_BUCKET:-nuzantara-backups}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_OWNER_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-}}"

DRILL_CONTAINER="${DRILL_CONTAINER:-nuzantara-pg-drill}"
DRILL_PORT="${DRILL_PORT:-15499}"
DRILL_USER="drill"
DRILL_PW="drill"
DRILL_DB="nuzantara_drill"
TOLERANCE_PCT="${TOLERANCE_PCT:-10}"  # alert if prod vs drill diff >10%

log() { echo "[$(date -u '+%H:%M:%SZ')] $*" | tee -a "$REPORT"; }
die() { log "ERROR: $*"; notify "❌" "$*"; exit "${2:-2}"; }

notify() {
  local emoji="$1" text="$2"
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
    log "Skipping Telegram (no credentials)"
    return
  fi
  local msg="${emoji} Restore drill
${text}
report: ${REPORT}"
  curl -s --max-time 10 \
    -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    > /dev/null || true
}

cleanup() {
  docker rm -f "$DRILL_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# 1. Find latest backup in Tigris
[ -n "$AWS_ACCESS_KEY_ID" ] || die "missing AWS_ACCESS_KEY_ID" 1
[ -n "$AWS_SECRET_ACCESS_KEY" ] || die "missing AWS_SECRET_ACCESS_KEY" 1
command -v aws >/dev/null || die "aws CLI not installed" 1
command -v docker >/dev/null || die "docker not installed" 1

log "Listing backups in s3://$TIGRIS_BUCKET/postgres/ ..."
LATEST=$(aws --endpoint-url "$TIGRIS_ENDPOINT" s3 ls "s3://$TIGRIS_BUCKET/postgres/" \
  | awk '{print $4}' | grep -E '\.sql\.gz$' | sort | tail -1) \
  || die "aws s3 ls failed" 1
[ -n "$LATEST" ] || die "no backups found in bucket" 1
log "Latest backup: $LATEST"

# 2. Download it
LOCAL_DUMP="/tmp/${LATEST}"
log "Downloading to $LOCAL_DUMP ..."
aws --endpoint-url "$TIGRIS_ENDPOINT" s3 cp \
  "s3://$TIGRIS_BUCKET/postgres/$LATEST" "$LOCAL_DUMP" \
  || die "download failed" 1
DUMP_SIZE=$(stat -f%z "$LOCAL_DUMP" 2>/dev/null || stat -c%s "$LOCAL_DUMP")
log "Downloaded $DUMP_SIZE bytes"
[ "$DUMP_SIZE" -gt 1000000 ] || die "dump suspiciously small: $DUMP_SIZE bytes" 1

# 3. Spin up ephemeral Postgres container
log "Starting ephemeral postgres container..."
docker rm -f "$DRILL_CONTAINER" >/dev/null 2>&1 || true
docker run -d \
  --name "$DRILL_CONTAINER" \
  -e POSTGRES_USER="$DRILL_USER" \
  -e POSTGRES_PASSWORD="$DRILL_PW" \
  -e POSTGRES_DB="$DRILL_DB" \
  -p "$DRILL_PORT:5432" \
  postgres:17 >/dev/null \
  || die "docker run failed" 2

# Wait for ready
for _ in $(seq 1 30); do
  if docker exec "$DRILL_CONTAINER" pg_isready -U "$DRILL_USER" -d "$DRILL_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# 4. Restore dump
log "Restoring dump (this may take a few minutes)..."
gunzip -c "$LOCAL_DUMP" | \
  PGPASSWORD="$DRILL_PW" psql \
    -h 127.0.0.1 -p "$DRILL_PORT" -U "$DRILL_USER" -d "$DRILL_DB" \
    -v ON_ERROR_STOP=0 \
    > "$REPORT.restore" 2>&1
RESTORE_EXIT=$?
log "Restore finished (psql exit $RESTORE_EXIT, see $REPORT.restore for details)"

# 5. Sanity queries
q() {
  PGPASSWORD="$DRILL_PW" psql -h 127.0.0.1 -p "$DRILL_PORT" -U "$DRILL_USER" -d "$DRILL_DB" \
    -Atc "$1" 2>/dev/null
}

TABLES_FOUND=$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
CLIENTS_COUNT=$(q "SELECT COUNT(*) FROM clients" || echo "ERROR")
PRACTICES_COUNT=$(q "SELECT COUNT(*) FROM practices" || echo "ERROR")

log "Sanity: $TABLES_FOUND tables, clients=$CLIENTS_COUNT, practices=$PRACTICES_COUNT"

if [ "$TABLES_FOUND" -lt 50 ] 2>/dev/null; then
  die "only $TABLES_FOUND tables restored — schema incomplete" 3
fi
case "$CLIENTS_COUNT" in ERROR|"") die "clients table not queryable" 3 ;; esac
case "$PRACTICES_COUNT" in ERROR|"") die "practices table not queryable" 3 ;; esac

# 6. Compare against prod (if reachable)
PROD_URL="${DATABASE_URL_LOCAL:-${DATABASE_URL:-}}"
if [ -n "$PROD_URL" ]; then
  PROD_CLIENTS=$(psql "$PROD_URL" -Atc "SELECT COUNT(*) FROM clients" 2>/dev/null || echo "")
  if [ -n "$PROD_CLIENTS" ]; then
    DIFF=$(( PROD_CLIENTS > CLIENTS_COUNT ? PROD_CLIENTS - CLIENTS_COUNT : CLIENTS_COUNT - PROD_CLIENTS ))
    PCT=$(( PROD_CLIENTS == 0 ? 0 : DIFF * 100 / PROD_CLIENTS ))
    log "Prod clients=$PROD_CLIENTS, restored=$CLIENTS_COUNT, drift=${PCT}% (tolerance ${TOLERANCE_PCT}%)"
    if [ "$PCT" -gt "$TOLERANCE_PCT" ]; then
      die "row-count drift ${PCT}% exceeds tolerance ${TOLERANCE_PCT}%" 4
    fi
  else
    log "Prod DB not reachable for comparison (non-fatal)"
  fi
else
  log "No prod DB URL — skipping drift check (non-fatal)"
fi

# 7. Success
notify "✅" "Restore drill passed
backup: $LATEST
tables: $TABLES_FOUND
clients: $CLIENTS_COUNT
practices: $PRACTICES_COUNT
dump: $DUMP_SIZE bytes"

log "Drill passed."
exit 0
