#!/bin/bash
# Script 3: Verify database migration
# Usage: ./03-verify-database.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="$(pwd)/backups/postgres"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  DATABASE VERIFICATION                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Get URLs
echo -e "${YELLOW}Enter Fly.io DATABASE_URL:${NC}"
read -r FLY_DB_URL

echo -e "${YELLOW}Enter Railway DATABASE_URL:${NC}"
read -r RAILWAY_DB_URL

# Tables to verify
TABLES=(
    "users"
    "clients"
    "conversations"
    "messages"
    "rag_documents"
    "kg_nodes"
    "kg_edges"
    "team_members"
)

echo -e "\n${BLUE}━━━ Row Count Comparison ━━━${NC}\n"

ERRORS=0

for table in "${TABLES[@]}"; do
    echo -e "${YELLOW}Checking table: ${table}${NC}"

    # Get counts
    FLY_COUNT=$(psql "$FLY_DB_URL" -t -c "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")
    RAILWAY_COUNT=$(psql "$RAILWAY_DB_URL" -t -c "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")

    # Compare
    if [ "$FLY_COUNT" = "$RAILWAY_COUNT" ]; then
        echo -e "  ${GREEN}✓ Match: ${FLY_COUNT} rows${NC}"
    else
        echo -e "  ${RED}✗ Mismatch!${NC}"
        echo -e "    Fly.io:  ${FLY_COUNT} rows"
        echo -e "    Railway: ${RAILWAY_COUNT} rows"
        ERRORS=$((ERRORS + 1))
    fi
    echo
done

# Sample data verification
echo -e "${BLUE}━━━ Sample Data Verification ━━━${NC}\n"

echo -e "${YELLOW}Comparing first 5 user IDs...${NC}"
FLY_USERS=$(psql "$FLY_DB_URL" -t -c "SELECT id FROM users ORDER BY id LIMIT 5;" 2>/dev/null || echo "")
RAILWAY_USERS=$(psql "$RAILWAY_DB_URL" -t -c "SELECT id FROM users ORDER BY id LIMIT 5;" 2>/dev/null || echo "")

if [ "$FLY_USERS" = "$RAILWAY_USERS" ]; then
    echo -e "${GREEN}✓ User IDs match${NC}\n"
else
    echo -e "${RED}✗ User IDs differ${NC}"
    echo -e "Fly.io:"
    echo "$FLY_USERS"
    echo -e "Railway:"
    echo "$RAILWAY_USERS"
    ERRORS=$((ERRORS + 1))
    echo
fi

# Summary
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  VERIFICATION SUMMARY                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "${GREEN}✓ Data migration successful${NC}\n"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS error(s)${NC}"
    echo -e "${YELLOW}⚠ Review discrepancies before proceeding${NC}\n"
    exit 1
fi
