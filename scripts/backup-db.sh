#!/bin/bash
#
# DATABASE BACKUP SCRIPT - Nuzantara Platform
#
# This script creates a backup of the PostgreSQL database using Fly.io proxy.
# Can be run standalone or called by safe-deploy.sh
#
# Usage:
#   ./scripts/backup-db.sh [options]
#
# Options:
#   --output-dir DIR    Custom output directory (default: backups/postgres)
#   --app-name NAME     Fly.io app name (default: nuzantara-rag)
#   --keep N            Keep only last N backups (default: 10)
#   -h, --help          Show this help message
#
# Author: Nuzantara Team
# Version: 1.0.0
# Date: 2026-01-13
#

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME="nuzantara-rag"
BACKUP_DIR="backups/postgres"
KEEP_BACKUPS=10

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse command line options
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --app-name)
            APP_NAME="$2"
            shift 2
            ;;
        --keep)
            KEEP_BACKUPS="$2"
            shift 2
            ;;
        -h|--help)
            head -n 18 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
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

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ============================================================================
# BACKUP FUNCTION
# ============================================================================

backup_database() {
    log_info "Creating database backup..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Generate filename with timestamp
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/nuzantara-db-$TIMESTAMP.sql"
    BACKUP_FILE_GZ="${BACKUP_FILE}.gz"
    
    # Check if flyctl is installed
    if ! command -v flyctl &> /dev/null; then
        log_error "flyctl is not installed!"
        exit 1
    fi
    
    # Get DATABASE_URL from Fly.io secrets
    log_info "Retrieving database connection details..."
    
    # Use fly postgres proxy to create backup
    # This is safer than exposing DATABASE_URL
    if flyctl postgres db list -a "$APP_NAME" &> /dev/null; then
        log_info "Using Fly Postgres proxy for backup..."
        
        # Note: This requires the Postgres app name, which might be different
        # For now, we'll use a simpler approach with fly ssh
        log_info "Creating backup via SSH..."
        
        if flyctl ssh console -a "$APP_NAME" -C "pg_dump \$DATABASE_URL" > "$BACKUP_FILE" 2>/dev/null; then
            # Compress the backup
            gzip "$BACKUP_FILE"
            
            # Get file size
            SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
            
            log_success "Backup created: $BACKUP_FILE_GZ ($SIZE)"
        else
            log_error "Backup failed via SSH"
            
            # Fallback: try to get DATABASE_URL from secrets
            log_info "Trying alternative method..."
            
            DATABASE_URL=$(flyctl secrets list -a "$APP_NAME" 2>/dev/null | grep DATABASE_URL | awk '{print $2}')
            
            if [ -z "$DATABASE_URL" ]; then
                log_error "Could not retrieve DATABASE_URL"
                log_info "Manual backup recommended:"
                echo "  flyctl ssh console -a $APP_NAME -C 'pg_dump \$DATABASE_URL' > backup.sql"
                exit 1
            fi
            
            # Use pg_dump if available locally
            if command -v pg_dump &> /dev/null; then
                log_info "Using local pg_dump..."
                if pg_dump "$DATABASE_URL" > "$BACKUP_FILE" 2>/dev/null; then
                    gzip "$BACKUP_FILE"
                    SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
                    log_success "Backup created: $BACKUP_FILE_GZ ($SIZE)"
                else
                    log_error "pg_dump failed"
                    exit 1
                fi
            else
                log_error "pg_dump not installed locally"
                log_info "Install PostgreSQL client tools or use SSH method"
                exit 1
            fi
        fi
    else
        log_error "Could not access Postgres on Fly.io"
        exit 1
    fi
}

# ============================================================================
# CLEANUP OLD BACKUPS
# ============================================================================

cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last $KEEP_BACKUPS)..."
    
    # Count existing backups
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/nuzantara-db-*.sql.gz 2>/dev/null | wc -l)
    
    if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
        # Remove oldest backups
        ls -1t "$BACKUP_DIR"/nuzantara-db-*.sql.gz | tail -n +$((KEEP_BACKUPS + 1)) | xargs rm -f
        REMOVED=$((BACKUP_COUNT - KEEP_BACKUPS))
        log_success "Removed $REMOVED old backup(s)"
    else
        log_info "No cleanup needed ($BACKUP_COUNT backups)"
    fi
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  DATABASE BACKUP - Nuzantara Platform${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    backup_database
    cleanup_old_backups
    
    echo ""
    log_success "Backup process completed"
    log_info "Restore command: gunzip -c $BACKUP_FILE_GZ | psql \$DATABASE_URL"
    echo ""
}

main
