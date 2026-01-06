#!/bin/bash
# Script 1: Export all data from Fly.io
# Usage: ./01-export-flyio-data.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="$(pwd)/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  FLY.IO DATA EXPORT SCRIPT             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Check if Fly.io is accessible
echo -e "${YELLOW}→ Checking Fly.io connectivity...${NC}"
if ! fly status -a nuzantara-rag &>/dev/null; then
    echo -e "${RED}✗ Cannot connect to Fly.io. Is it still down?${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Fly.io accessible${NC}\n"

# =============================================================================
# POSTGRESQL EXPORT
# =============================================================================

echo -e "${BLUE}━━━ PostgreSQL Export ━━━${NC}"

# Get Fly.io Postgres app name
echo -e "${YELLOW}→ Finding PostgreSQL app...${NC}"
FLY_PG_APP=$(fly postgres list --json 2>/dev/null | jq -r '.[0].Name' || echo "")

if [ -z "$FLY_PG_APP" ]; then
    echo -e "${YELLOW}⚠ No Fly Postgres found. Enter app name manually:${NC}"
    read -r FLY_PG_APP
fi

echo -e "${GREEN}✓ Using Postgres app: ${FLY_PG_APP}${NC}"

# Get database connection URL
echo -e "${YELLOW}→ Getting database URL...${NC}"
FLY_DB_URL=$(fly postgres connect -a "$FLY_PG_APP" -c "SELECT current_database();" 2>&1 | grep -o "postgresql://.*" || echo "")

if [ -z "$FLY_DB_URL" ]; then
    echo -e "${RED}✗ Could not get database URL automatically${NC}"
    echo -e "${YELLOW}Enter DATABASE_URL manually:${NC}"
    read -r FLY_DB_URL
fi

# Export using pg_dump
echo -e "${YELLOW}→ Creating PostgreSQL backup...${NC}"

PG_BACKUP_FILE="$BACKUP_DIR/postgres/postgres_backup_${TIMESTAMP}.sql"
PG_DUMP_FILE="$BACKUP_DIR/postgres/postgres_backup_${TIMESTAMP}.dump"

# SQL format (readable)
echo -e "  ${YELLOW}Creating SQL backup...${NC}"
pg_dump "$FLY_DB_URL" > "$PG_BACKUP_FILE"
gzip "$PG_BACKUP_FILE"

# Custom format (faster restore)
echo -e "  ${YELLOW}Creating binary dump...${NC}"
pg_dump -Fc "$FLY_DB_URL" > "$PG_DUMP_FILE"

# Get row counts
echo -e "${YELLOW}→ Getting row counts...${NC}"
psql "$FLY_DB_URL" -t -c "
SELECT
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_tup_ins AS rows
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC;
" > "$BACKUP_DIR/postgres/table_stats_${TIMESTAMP}.txt"

echo -e "${GREEN}✓ PostgreSQL backup complete${NC}"
echo -e "  ${GREEN}SQL: ${PG_BACKUP_FILE}.gz${NC}"
echo -e "  ${GREEN}Dump: ${PG_DUMP_FILE}${NC}"
echo -e "  ${GREEN}Stats: $BACKUP_DIR/postgres/table_stats_${TIMESTAMP}.txt${NC}\n"

# =============================================================================
# ENVIRONMENT VARIABLES EXPORT
# =============================================================================

echo -e "${BLUE}━━━ Environment Variables Export ━━━${NC}"

echo -e "${YELLOW}→ Exporting secrets from nuzantara-rag...${NC}"
fly secrets list -a nuzantara-rag > "$BACKUP_DIR/secrets_backend_${TIMESTAMP}.txt"

echo -e "${YELLOW}→ Exporting secrets from nuzantara-mouth...${NC}"
fly secrets list -a nuzantara-mouth > "$BACKUP_DIR/secrets_frontend_${TIMESTAMP}.txt" 2>/dev/null || echo "N/A"

echo -e "${YELLOW}→ Exporting secrets from bali-intel-scraper...${NC}"
fly secrets list -a bali-intel-scraper > "$BACKUP_DIR/secrets_scraper_${TIMESTAMP}.txt" 2>/dev/null || echo "N/A"

echo -e "${GREEN}✓ Secrets exported${NC}\n"

# =============================================================================
# SUMMARY
# =============================================================================

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  EXPORT SUMMARY                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

echo -e "${GREEN}✓ PostgreSQL backup:${NC}"
ls -lh "$BACKUP_DIR/postgres/" | tail -n +2

echo -e "\n${GREEN}✓ Secrets:${NC}"
ls -lh "$BACKUP_DIR/" | grep secrets

echo -e "\n${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Export complete!${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"

echo -e "\n${BLUE}Next step:${NC} Run ${YELLOW}./04-export-qdrant.sh${NC} to export Qdrant data\n"
