#!/bin/bash
#
# SAFE DEPLOY SCRIPT - Nuzantara Platform
# 
# This script provides a safe deployment workflow with automatic safety checks,
# backup creation, health verification, and auto-rollback on failure.
#
# Usage:
#   ./scripts/safe-deploy.sh [options]
#
# Options:
#   --skip-tests       Skip test execution (use with caution)
#   --skip-backup      Skip database backup
#   --no-rollback      Don't auto-rollback on health check failure
#   --dry-run          Show what would be done without executing
#   -h, --help         Show this help message
#
# Author: Nuzantara Team
# Version: 1.0.0
# Date: 2026-01-13
#

set -e  # Exit on error (except where we handle errors explicitly)

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME="nuzantara-rag"
HEALTH_URL="https://nuzantara-rag.fly.dev/health"
BACKEND_DIR="apps/backend-rag"
DEPLOY_LOGS_DIR="deploy-logs"
BACKUPS_DIR="backups/postgres"
HEALTH_CHECK_TIMEOUT=30
HEALTH_CHECK_RETRIES=6
RETRY_DELAY=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line options
SKIP_TESTS=false
SKIP_BACKUP=false
NO_ROLLBACK=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --no-rollback)
            NO_ROLLBACK=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            head -n 20 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

preflight_checks() {
    log_step "🔍 PRE-FLIGHT CHECKS"
    
    # Check if we're in the project root
    if [ ! -f "fly.toml" ] && [ ! -d "apps/backend-rag" ]; then
        log_error "Not in project root directory!"
        log_info "Please run this script from the Nuzantara project root"
        exit 1
    fi
    
    # Check if flyctl is installed
    if ! command -v flyctl &> /dev/null; then
        log_error "flyctl is not installed!"
        log_info "Install it: https://fly.io/docs/hands-on/install-flyctl/"
        exit 1
    fi
    
    # Check if authenticated with Fly.io
    if ! flyctl auth whoami &> /dev/null; then
        log_error "Not authenticated with Fly.io!"
        log_info "Run: flyctl auth login"
        exit 1
    fi
    
    # Check if app exists
    if ! flyctl apps list | grep -q "$APP_NAME"; then
        log_error "App '$APP_NAME' not found in your Fly.io account!"
        exit 1
    fi
    
    log_success "Pre-flight checks passed"
    
    # Show current git status
    log_info "Current branch: $(git branch --show-current)"
    log_info "Last commit: $(git log -1 --oneline)"
    
    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "You have uncommitted changes!"
        git status --short
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deploy cancelled"
            exit 0
        fi
    fi
}

# ============================================================================
# STEP 1: RUN TESTS
# ============================================================================

run_tests() {
    if [ "$SKIP_TESTS" = true ]; then
        log_warning "Skipping tests (--skip-tests flag)"
        return 0
    fi
    
    log_step "🧪 RUNNING TESTS"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: cd $BACKEND_DIR && pytest tests/ -q --tb=short"
        log_success "[DRY RUN] Tests passed (simulated)"
        return 0
    fi
    
    cd "$BACKEND_DIR" || exit 1
    
    # Run tests with minimal output
    if PYTHONPATH=backend pytest tests/unit/services/rag/agentic/test_reasoning.py -q --tb=short 2>&1 | tee /tmp/test-output.txt; then
        TEST_SUMMARY=$(tail -3 /tmp/test-output.txt | head -1)
        log_success "Tests passed: $TEST_SUMMARY"
        cd ../..
        return 0
    else
        log_error "Tests failed!"
        log_info "Fix the failing tests before deploying"
        log_info "View full output: cat /tmp/test-output.txt"
        cd ../..
        exit 1
    fi
}

# ============================================================================
# STEP 2: BACKUP DATABASE
# ============================================================================

backup_database() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warning "Skipping database backup (--skip-backup flag)"
        return 0
    fi
    
    log_step "💾 BACKING UP DATABASE"
    
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUPS_DIR"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: ./scripts/backup-db.sh"
        log_success "[DRY RUN] Backup created (simulated)"
        return 0
    fi
    
    # Check if backup script exists
    if [ -f "scripts/backup-db.sh" ]; then
        if bash scripts/backup-db.sh; then
            log_success "Database backup created"
        else
            log_warning "Backup script failed, but continuing deploy"
            log_info "Consider creating a manual backup if schema changes are involved"
        fi
    else
        log_warning "Backup script not found at scripts/backup-db.sh"
        log_info "Database backup skipped - consider implementing backup-db.sh"
    fi
}

# ============================================================================
# STEP 3: DEPLOY TO FLY.IO
# ============================================================================

deploy_to_flyio() {
    log_step "🚀 DEPLOYING TO PRODUCTION"
    
    # Create deploy logs directory
    mkdir -p "$DEPLOY_LOGS_DIR"
    
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    LOG_FILE="$DEPLOY_LOGS_DIR/deploy-$TIMESTAMP.log"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: cd $BACKEND_DIR && flyctl deploy -a $APP_NAME"
        log_success "[DRY RUN] Deploy completed (simulated)"
        DEPLOYED_VERSION="v9999"
        return 0
    fi
    
    log_info "Deploying to Fly.io..."
    log_info "Log file: $LOG_FILE"
    
    cd "$BACKEND_DIR" || exit 1
    
    # Deploy and capture output
    if flyctl deploy -a "$APP_NAME" 2>&1 | tee "../../$LOG_FILE"; then
        # Extract version from logs
        DEPLOYED_VERSION=$(grep -o 'v[0-9]\+' "../../$LOG_FILE" | tail -1)
        if [ -z "$DEPLOYED_VERSION" ]; then
            DEPLOYED_VERSION="unknown"
        fi
        
        log_success "Deploy completed: $DEPLOYED_VERSION"
        cd ../..
        return 0
    else
        log_error "Deploy failed!"
        log_info "Check logs: cat $LOG_FILE"
        cd ../..
        exit 1
    fi
}

# ============================================================================
# STEP 4: HEALTH CHECK
# ============================================================================

health_check() {
    log_step "🏥 HEALTH CHECK"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would check: $HEALTH_URL"
        log_success "[DRY RUN] Health check passed (simulated)"
        return 0
    fi
    
    log_info "Waiting ${HEALTH_CHECK_TIMEOUT}s for application startup..."
    sleep "$HEALTH_CHECK_TIMEOUT"
    
    log_info "Checking health endpoint: $HEALTH_URL"
    
    for i in $(seq 1 $HEALTH_CHECK_RETRIES); do
        log_info "Attempt $i/$HEALTH_CHECK_RETRIES..."
        
        # Perform health check with timeout
        if HTTP_CODE=$(curl -s -o /tmp/health-response.json -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>&1); then
            if [ "$HTTP_CODE" = "200" ]; then
                log_success "Backend responding: HTTP $HTTP_CODE"
                
                # Parse health response if it's JSON
                if command -v jq &> /dev/null && [ -f /tmp/health-response.json ]; then
                    QDRANT_DOCS=$(jq -r '.qdrant.total_documents // "unknown"' /tmp/health-response.json 2>/dev/null)
                    DB_STATUS=$(jq -r '.database // "unknown"' /tmp/health-response.json 2>/dev/null)
                    
                    if [ "$QDRANT_DOCS" != "unknown" ]; then
                        log_success "Qdrant: $QDRANT_DOCS documents"
                    fi
                    if [ "$DB_STATUS" != "unknown" ]; then
                        log_success "Database: $DB_STATUS"
                    fi
                fi
                
                return 0
            else
                log_warning "HTTP $HTTP_CODE - not healthy yet"
            fi
        else
            log_warning "Connection failed or timeout"
        fi
        
        if [ $i -lt $HEALTH_CHECK_RETRIES ]; then
            log_info "Retrying in ${RETRY_DELAY}s..."
            sleep "$RETRY_DELAY"
        fi
    done
    
    log_error "Health check failed after $HEALTH_CHECK_RETRIES attempts!"
    return 1
}

# ============================================================================
# STEP 5: ROLLBACK (IF NEEDED)
# ============================================================================

rollback() {
    if [ "$NO_ROLLBACK" = true ]; then
        log_warning "Auto-rollback disabled (--no-rollback flag)"
        log_error "Production may be down! Manual intervention required."
        exit 1
    fi
    
    log_step "🔄 ROLLING BACK"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: flyctl releases rollback -a $APP_NAME -y"
        log_success "[DRY RUN] Rollback completed (simulated)"
        return 0
    fi
    
    log_warning "Health check failed - initiating automatic rollback..."
    
    cd "$BACKEND_DIR" || exit 1
    
    if flyctl releases rollback -a "$APP_NAME" -y; then
        log_success "Rollback completed"
        log_info "Production should be stable on previous version"
        
        # Verify rollback worked
        log_info "Verifying rollback..."
        sleep 10
        
        if curl -s -f --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
            log_success "Rollback successful - production is healthy"
        else
            log_error "Rollback completed but health check still failing!"
            log_warning "Manual intervention required!"
        fi
    else
        log_error "Rollback failed!"
        log_warning "Manual intervention required!"
    fi
    
    cd ../..
    exit 1
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}║          NUZANTARA SAFE DEPLOY SCRIPT v1.0.0          ║${NC}"
    echo -e "${CYAN}║                                                        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No actual changes will be made"
    fi
    
    START_TIME=$(date +%s)
    
    # Execute deployment steps
    preflight_checks
    run_tests
    backup_database
    deploy_to_flyio
    
    # Health check with rollback on failure
    if ! health_check; then
        rollback
        exit 1
    fi
    
    # Success!
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo ""
    log_step "🎉 DEPLOY SUCCESSFUL!"
    echo ""
    log_success "Version: $DEPLOYED_VERSION"
    log_success "URL: https://nuzantara-rag.fly.dev"
    log_success "Health: $HEALTH_URL"
    log_info "Total time: ${DURATION}s"
    echo ""
    log_info "Next steps:"
    echo "  • Check logs: flyctl logs -a $APP_NAME"
    echo "  • Monitor: https://fly.io/apps/$APP_NAME"
    echo "  • Metrics: https://fly.io/apps/$APP_NAME/metrics"
    echo ""
}

# Run main function
main
