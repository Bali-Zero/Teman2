#!/bin/bash
#
# Production Deployment Script for Nuzantara
# Includes: backup, migration, build, deploy, verification
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="apps/bali-intel-scraper"
FRONTEND_DIR="apps/mouth"
DB_NAME="bali_intel"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5433"
REDIS_HOST="localhost"
REDIS_PORT="6380"
DEPLOY_LOG="deploy_$(date +%Y%m%d_%H%M%S).log"

# Logging
exec 1> >(tee -a "$DEPLOY_LOG")
exec 2>&1

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

# =============================================================================
# STEP 0: Pre-deployment Checks
# =============================================================================
log "═══════════════════════════════════════════════════════════════"
log "           PRODUCTION DEPLOYMENT - NUZANTARA"
log "═══════════════════════════════════════════════════════════════"
log ""

# Check if we're in the right directory
if [ ! -f "package.json" ] || [ ! -d "$BACKEND_DIR" ]; then
    error "Must run from project root directory"
    exit 1
fi

# Check environment
log "Step 0: Pre-deployment Checks"
log "  Checking environment..."

# Check database connectivity
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
    error "PostgreSQL not available at $DB_HOST:$DB_PORT"
    exit 1
fi
success "PostgreSQL connection OK"

# Check Redis connectivity
if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
    error "Redis not available at $REDIS_HOST:$REDIS_PORT"
    exit 1
fi
success "Redis connection OK"

# Check disk space
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    warning "Disk usage is at ${DISK_USAGE}%. Consider cleaning up."
else
    success "Disk usage: ${DISK_USAGE}%"
fi

# =============================================================================
# STEP 1: Backup Database
# =============================================================================
log ""
log "Step 1: Database Backup"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"

log "  Creating database backup: $BACKUP_FILE"
if PGPASSWORD="${DB_PASSWORD:-}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"; then
    success "Database backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    error "Database backup failed!"
    exit 1
fi

# =============================================================================
# STEP 2: Database Migration
# =============================================================================
log ""
log "Step 2: Database Migration"

if [ -f "$BACKEND_DIR/migrations/001_add_performance_indexes.sql" ]; then
    log "  Running migration: 001_add_performance_indexes.sql"
    if PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$BACKEND_DIR/migrations/001_add_performance_indexes.sql"; then
        success "Migration completed successfully"
    else
        error "Migration failed! Check $DEPLOY_LOG"
        log "  Rolling back backup..."
        PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
        exit 1
    fi
else
    warning "Migration file not found, skipping"
fi

# =============================================================================
# STEP 3: Backend Deploy
# =============================================================================
log ""
log "Step 3: Backend Deployment"

cd "$BACKEND_DIR"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker not installed"
    exit 1
fi

# Build Docker image
log "  Building Docker image..."
DOCKER_TAG="bali-intel:$(date +%Y%m%d_%H%M%S)"
if docker build -f Dockerfile.optimized -t "$DOCKER_TAG" -t bali-intel:latest .; then
    success "Docker image built: $DOCKER_TAG"
else
    error "Docker build failed!"
    cd ../..
    exit 1
fi

# Get current running container
CURRENT_CONTAINER=$(docker ps -q --filter "name=bali-intel" 2>/dev/null || true)

# Start new container
log "  Starting new container..."
NEW_CONTAINER=$(docker run -d \
    --name bali-intel-new \
    --network host \
    -e DB_HOST="$DB_HOST" \
    -e DB_PORT="$DB_PORT" \
    -e DB_NAME="$DB_NAME" \
    -e DB_USER="$DB_USER" \
    -e DB_PASSWORD="${DB_PASSWORD:-}" \
    -e REDIS_HOST="$REDIS_HOST" \
    -e REDIS_PORT="$REDIS_PORT" \
    -p 8000:8000 \
    bali-intel:latest)

# Wait for container to be healthy
log "  Waiting for container to be healthy..."
HEALTH_CHECK_COUNT=0
MAX_HEALTH_CHECKS=30

while [ $HEALTH_CHECK_COUNT -lt $MAX_HEALTH_CHECKS ]; do
    if docker inspect --format='{{.State.Health.Status}}' "$NEW_CONTAINER" 2>/dev/null | grep -q "healthy"; then
        success "Container is healthy"
        break
    fi
    
    # Check if container exited
    if [ "$(docker inspect --format='{{.State.Status}}' "$NEW_CONTAINER" 2>/dev/null)" == "exited" ]; then
        error "Container exited unexpectedly"
        docker logs "$NEW_CONTAINER"
        docker rm "$NEW_CONTAINER"
        cd ../..
        exit 1
    fi
    
    sleep 2
    HEALTH_CHECK_COUNT=$((HEALTH_CHECK_COUNT + 1))
    echo -n "."
done

if [ $HEALTH_CHECK_COUNT -eq $MAX_HEALTH_CHECKS ]; then
    error "Container health check timeout"
    docker logs "$NEW_CONTAINER"
    docker rm "$NEW_CONTAINER"
    cd ../..
    exit 1
fi

# Verify API is responding
log "  Verifying API..."
if curl -sf http://localhost:8000/health/live > /dev/null; then
    success "API is responding"
else
    error "API health check failed"
    docker logs "$NEW_CONTAINER"
    docker rm "$NEW_CONTAINER"
    cd ../..
    exit 1
fi

# Switch traffic (stop old, rename new)
if [ -n "$CURRENT_CONTAINER" ]; then
    log "  Stopping old container..."
    docker stop "$CURRENT_CONTAINER" > /dev/null 2>&1 || true
    docker rm "$CURRENT_CONTAINER" > /dev/null 2>&1 || true
fi

docker rename bali-intel-new bali-intel > /dev/null 2>&1 || true
success "Backend deployed successfully"

cd ../..

# =============================================================================
# STEP 4: Frontend Build & Deploy
# =============================================================================
log ""
log "Step 4: Frontend Deployment"

cd "$FRONTEND_DIR"

# Install dependencies
log "  Installing dependencies..."
npm ci > /dev/null 2>&1 || npm install

# Build
log "  Building frontend..."
if npm run build; then
    success "Frontend build successful"
else
    error "Frontend build failed!"
    cd ../..
    exit 1
fi

# Deploy (copy to web server directory or restart service)
# This depends on your hosting setup
if [ -d "/var/www/html" ]; then
    log "  Deploying to /var/www/html..."
    rsync -av --delete .next/static /var/www/html/
    rsync -av --delete public /var/www/html/
    success "Frontend deployed to /var/www/html"
else
    warning "Web server directory not found. Skipping frontend deploy."
    warning "Build output is in: $(pwd)/.next"
fi

cd ../..

# =============================================================================
# STEP 5: Post-deployment Verification
# =============================================================================
log ""
log "Step 5: Post-deployment Verification"

# Test API endpoints
log "  Testing API endpoints..."

ENDPOINTS=(
    "http://localhost:8000/health/live"
    "http://localhost:8000/health/ready"
    "http://localhost:8000/"
)

for endpoint in "${ENDPOINTS[@]}"; do
    if curl -sf "$endpoint" > /dev/null; then
        success "  ✓ $endpoint"
    else
        error "  ✗ $endpoint"
    fi
done

# Test middleware (rate limiting headers)
log "  Testing middleware..."
RESPONSE=$(curl -s -I http://localhost:8000/ 2>/dev/null | grep -i "X-RateLimit" || true)
if [ -n "$RESPONSE" ]; then
    success "  ✓ Rate limiting headers present"
else
    warning "  ⚠ Rate limiting headers not detected"
fi

# Test Brotli compression
log "  Testing Brotli compression..."
if curl -s -H "Accept-Encoding: br" -I http://localhost:8000/ 2>/dev/null | grep -qi "content-encoding: br"; then
    success "  ✓ Brotli compression enabled"
else
    warning "  ⚠ Brotli compression not detected (may require HTTPS)"
fi

# =============================================================================
# STEP 6: Cleanup
# =============================================================================
log ""
log "Step 6: Cleanup"

# Remove old Docker images (keep last 3)
log "  Cleaning old Docker images..."
docker images bali-intel --format "{{.Repository}}:{{.Tag}} {{.ID}}" | \
    grep -v "latest" | \
    tail -n +4 | \
    awk '{print $2}' | \
    xargs -r docker rmi > /dev/null 2>&1 || true
success "Old images cleaned"

# Compress backup
log "  Compressing backup..."
gzip "$BACKUP_FILE"
success "Backup compressed: ${BACKUP_FILE}.gz"

# =============================================================================
# DEPLOYMENT COMPLETE
# =============================================================================
log ""
log "═══════════════════════════════════════════════════════════════"
log "           ✅ DEPLOYMENT COMPLETED SUCCESSFULLY"
log "═══════════════════════════════════════════════════════════════"
log ""
success "Version deployed: $DOCKER_TAG"
success "Database backup: ${BACKUP_FILE}.gz"
success "Deploy log: $DEPLOY_LOG"
log ""
log "═══════════════════════════════════════════════════════════════"

exit 0
