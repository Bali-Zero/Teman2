#!/bin/bash
# Script 2: Import PostgreSQL to Railway
# Usage: ./02-import-railway-postgres.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="$(pwd)/backups/postgres"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RAILWAY POSTGRESQL IMPORT             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Find latest backup
echo -e "${YELLOW}→ Finding latest backup...${NC}"
LATEST_DUMP=$(ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | head -1)

if [ -z "$LATEST_DUMP" ]; then
    echo -e "${RED}✗ No backup file found in $BACKUP_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Using backup: $(basename "$LATEST_DUMP")${NC}\n"

# Get Railway database URL
echo -e "${YELLOW}→ Getting Railway database URL...${NC}"
echo -e "${BLUE}Options:${NC}"
echo -e "  ${YELLOW}1)${NC} Auto-detect from Railway CLI"
echo -e "  ${YELLOW}2)${NC} Enter manually"
read -p "Choose option [1]: " OPTION
OPTION=${OPTION:-1}

if [ "$OPTION" = "1" ]; then
    # Try to get from Railway CLI
    RAILWAY_DB_URL=$(railway variables get DATABASE_URL 2>/dev/null || echo "")

    if [ -z "$RAILWAY_DB_URL" ]; then
        echo -e "${YELLOW}⚠ Could not auto-detect. Please enter manually:${NC}"
        read -r RAILWAY_DB_URL
    fi
else
    echo -e "${YELLOW}Enter Railway DATABASE_URL:${NC}"
    read -r RAILWAY_DB_URL
fi

# Validate connection
echo -e "${YELLOW}→ Testing Railway connection...${NC}"
if ! psql "$RAILWAY_DB_URL" -c "SELECT version();" &>/dev/null; then
    echo -e "${RED}✗ Cannot connect to Railway database${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Connection successful${NC}\n"

# Confirm before import
echo -e "${RED}⚠ WARNING: This will REPLACE all data in Railway database${NC}"
echo -e "${YELLOW}Database: ${RAILWAY_DB_URL%%@*}@***${NC}"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

# Import
echo -e "\n${YELLOW}→ Importing database (this may take 5-15 minutes)...${NC}"

# Drop existing schema (optional)
read -p "Drop existing tables first? (yes/no) [yes]: " DROP
DROP=${DROP:-yes}

if [ "$DROP" = "yes" ]; then
    echo -e "${YELLOW}  Dropping existing tables...${NC}"
    psql "$RAILWAY_DB_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
fi

# Restore from dump
echo -e "${YELLOW}  Restoring from backup...${NC}"
pg_restore -d "$RAILWAY_DB_URL" --no-owner --no-acl --verbose "$LATEST_DUMP" 2>&1 | grep -E "processing|creating|restoring" || true

echo -e "${GREEN}✓ Import complete${NC}\n"

# Verify
echo -e "${YELLOW}→ Verifying import...${NC}"

echo -e "\n${BLUE}Table counts:${NC}"
psql "$RAILWAY_DB_URL" -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"

echo -e "\n${BLUE}Sample data check:${NC}"
psql "$RAILWAY_DB_URL" -c "SELECT COUNT(*) as user_count FROM users;" 2>/dev/null || echo "No users table"

echo -e "\n${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Import complete!${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"

echo -e "\n${BLUE}Next step:${NC} Run ${YELLOW}./03-verify-database.sh${NC} to verify data integrity\n"
