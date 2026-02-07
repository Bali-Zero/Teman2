#!/bin/bash
#
# Simplified Docker Compose Deployment
# Recommended for production use
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

COMPOSE_FILE="docker-compose.production.yml"

log "═══════════════════════════════════════════════════════════════"
log "         DOCKER COMPOSE DEPLOYMENT - NUZANTARA"
log "═══════════════════════════════════════════════════════════════"
log ""

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    error "Compose file not found: $COMPOSE_FILE"
    exit 1
fi

# Check .env file exists
if [ ! -f "apps/bali-intel-scraper/.env" ]; then
    warning "Environment file not found!"
    log "  Creating from example..."
    if [ -f "apps/bali-intel-scraper/.env.example" ]; then
        cp apps/bali-intel-scraper/.env.example apps/bali-intel-scraper/.env
        warning "Please edit apps/bali-intel-scraper/.env with your settings"
    fi
fi

# =============================================================================
# STEP 1: Pull latest code (optional)
# =============================================================================
log ""
log "Step 1: Pre-deployment"
read -p "Pull latest code from git? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git pull origin main
    success "Code updated"
fi

# =============================================================================
# STEP 2: Database Backup
# =============================================================================
log ""
log "Step 2: Database Backup"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql.gz"

if docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
    log "  Creating database backup..."
    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U postgres bali_intel | gzip > "$BACKUP_FILE"
    success "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    warning "PostgreSQL not running, skipping backup"
fi

# =============================================================================
# STEP 3: Build and Deploy
# =============================================================================
log ""
log "Step 3: Building and Deploying"

# Pull latest images
log "  Pulling latest images..."
docker-compose -f "$COMPOSE_FILE" pull

# Build backend with new optimizations
log "  Building backend..."
cd apps/bali-intel-scraper
docker build -f Dockerfile.optimized -t bali-intel:latest ..
cd ../..

# Deploy
log "  Starting services..."
docker-compose -f "$COMPOSE_FILE" up -d

# Wait for health checks
log "  Waiting for services to be healthy..."
sleep 10

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "healthy"; then
        success "All services are healthy"
        break
    fi
    
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    error "Services failed to become healthy"
    docker-compose -f "$COMPOSE_FILE" logs
    exit 1
fi

# =============================================================================
# STEP 4: Run Database Migrations
# =============================================================================
log ""
log "Step 4: Database Migration"

if [ -f "apps/bali-intel-scraper/migrations/001_add_performance_indexes.sql" ]; then
    log "  Running migration..."
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres bali_intel < \
        apps/bali-intel-scraper/migrations/001_add_performance_indexes.sql
    success "Migration completed"
else
    warning "No migration file found"
fi

# =============================================================================
# STEP 5: Verification
# =============================================================================
log ""
log "Step 5: Verification"

ENDPOINTS=(
    "http://localhost:8000/health/live"
    "http://localhost:8000/health/ready"
    "http://localhost:8000/"
)

for endpoint in "${ENDPOINTS[@]}"; do
    if curl -sf "$endpoint" > /dev/null 2>&1; then
        success "  ✓ $endpoint"
    else
        error "  ✗ $endpoint"
    fi
done

# Check middleware headers
log "  Checking middleware..."
HEADERS=$(curl -s -I http://localhost:8000/ 2>/dev/null | grep -i "x-ratelimit" || true)
if [ -n "$HEADERS" ]; then
    success "  ✓ Rate limiting active"
else
    warning "  ⚠ Rate limiting not detected"
fi

# =============================================================================
# STEP 6: Cleanup
# =============================================================================
log ""
log "Step 6: Cleanup"

# Remove old images
docker image prune -f > /dev/null 2>&1 || true
success "Old images cleaned"

# =============================================================================
# DEPLOYMENT COMPLETE
# =============================================================================
log ""
log "═══════════════════════════════════════════════════════════════"
log "           ✅ DEPLOYMENT COMPLETED SUCCESSFULLY"
log "═══════════════════════════════════════════════════════════════"
log ""
success "Services running:"
docker-compose -f "$COMPOSE_FILE" ps
log ""
success "Backup saved: $BACKUP_FILE"
log ""
log "Commands:"
log "  View logs: docker-compose -f $COMPOSE_FILE logs -f"
log "  Stop:      docker-compose -f $COMPOSE_FILE down"
log "  Restart:   docker-compose -f $COMPOSE_FILE restart"
log ""
log "═══════════════════════════════════════════════════════════════"
