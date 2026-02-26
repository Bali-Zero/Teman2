#!/bin/bash
#
# Emergency Rollback Script for Nuzantara
# Restores previous version in case of deployment failure
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Configuration
DB_NAME="bali_intel"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5433"

log "═══════════════════════════════════════════════════════════════"
log "           🚨 EMERGENCY ROLLBACK - NUZANTARA"
log "═══════════════════════════════════════════════════════════════"
log ""

# Check for backup file
BACKUP_FILE=$(ls -t backup_*.sql.gz 2>/dev/null | head -1 || true)

if [ -z "$BACKUP_FILE" ]; then
    error "No backup file found!"
    log "  Looking for: backup_*.sql.gz"
    exit 1
fi

log "Found backup: $BACKUP_FILE"
read -p "Are you sure you want to rollback? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Rollback cancelled"
    exit 0
fi

# =============================================================================
# STEP 1: Stop Current Backend
# =============================================================================
log ""
log "Step 1: Stopping current backend..."

CURRENT_CONTAINER=$(docker ps -q --filter "name=bali-intel" 2>/dev/null || true)
if [ -n "$CURRENT_CONTAINER" ]; then
    docker stop "$CURRENT_CONTAINER" > /dev/null 2>&1 || true
    success "Current container stopped"
else
    warning "No running container found"
fi

# =============================================================================
# STEP 2: Restore Database
# =============================================================================
log ""
log "Step 2: Restoring database from backup..."

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    log "  Decompressing backup..."
    gunzip -k "$BACKUP_FILE"
    SQL_FILE="${BACKUP_FILE%.gz}"
else
    SQL_FILE="$BACKUP_FILE"
fi

# Restore
log "  Restoring database (this may take a while)..."
if PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$SQL_FILE"; then
    success "Database restored successfully"
else
    error "Database restore failed!"
    exit 1
fi

# Cleanup decompressed file
if [[ "$BACKUP_FILE" == *.gz ]]; then
    rm -f "$SQL_FILE"
fi

# =============================================================================
# STEP 3: Restore Previous Docker Image
# =============================================================================
log ""
log "Step 3: Restoring previous Docker image..."

# Get previous image (second most recent)
PREVIOUS_IMAGE=$(docker images bali-intel --format "{{.Repository}}:{{.Tag}}" | grep -v "latest" | head -1)

if [ -n "$PREVIOUS_IMAGE" ]; then
    log "  Found previous image: $PREVIOUS_IMAGE"
    
    # Start with previous image
    docker run -d \
        --name bali-intel \
        --network host \
        -e DB_HOST="$DB_HOST" \
        -e DB_PORT="$DB_PORT" \
        -e DB_NAME="$DB_NAME" \
        -e DB_USER="$DB_USER" \
        -e DB_PASSWORD="${DB_PASSWORD:-}" \
        -e REDIS_HOST="${REDIS_HOST:-localhost}" \
        -e REDIS_PORT="${REDIS_PORT:-6380}" \
        -p 8000:8000 \
        "$PREVIOUS_IMAGE"
    
    # Wait for health check
    log "  Waiting for container to be healthy..."
    sleep 5
    
    if curl -sf http://localhost:8000/health/live > /dev/null; then
        success "Previous version restored successfully"
    else
        error "Previous version failed to start"
        exit 1
    fi
else
    warning "No previous Docker image found"
    log "  Starting with 'latest' tag..."
    
    docker run -d \
        --name bali-intel \
        --network host \
        -p 8000:8000 \
        bali-intel:latest
fi

# =============================================================================
# ROLLBACK COMPLETE
# =============================================================================
log ""
log "═══════════════════════════════════════════════════════════════"
log "           ✅ ROLLBACK COMPLETED"
log "═══════════════════════════════════════════════════════════════"
log ""
success "System restored to: $BACKUP_FILE"
warning "Please investigate the deployment failure"
log ""
log "═══════════════════════════════════════════════════════════════"
