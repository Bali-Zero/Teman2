#!/bin/bash
#
# Multi-Agent KBLI Expansion Orchestrator
# ========================================
# Coordinates 3 agents in sequence for KBLI Knowledge Graph expansion.
#
# Usage:
#   ./run_multiagent_kbli_expansion.sh [--parallel] [--dry-run]
#
# Options:
#   --parallel   Run Agent 2 and Agent 3 in parallel (experimental)
#   --dry-run    Run Agent 3 in dry-run mode (no DB changes)
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
PARALLEL=false
DRY_RUN=""

for arg in "$@"; do
    case $arg in
        --parallel)
            PARALLEL=true
            shift
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
    esac
done

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend-rag"

echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  MULTI-AGENT KBLI EXPANSION - Orchestrator${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Project root:${NC} $PROJECT_ROOT"
echo -e "${GREEN}Backend dir:${NC} $BACKEND_DIR"
echo -e "${GREEN}Parallel mode:${NC} $PARALLEL"
echo -e "${GREEN}Dry run:${NC} ${DRY_RUN:-No}"
echo ""

# Activate virtualenv
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "${RED}❌ Virtualenv not found at $BACKEND_DIR/.venv${NC}"
    echo -e "${YELLOW}Run: cd $BACKEND_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

echo -e "${YELLOW}[SETUP]${NC} Activating virtualenv..."
source "$BACKEND_DIR/.venv/bin/activate"

# Verify environment
if [ -z "$QDRANT_URL" ]; then
    echo -e "${RED}❌ QDRANT_URL not set${NC}"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL not set${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment verified${NC}"
echo ""

# ============================================================
# AGENT 1: Extract KBLI from Qdrant
# ============================================================
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AGENT 1: Extract KBLI from Qdrant${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo ""

START_TIME=$(date +%s)

cd "$BACKEND_DIR"
PYTHONPATH=. python "$SCRIPT_DIR/agent1_extract_kbli_qdrant.py"

AGENT1_END=$(date +%s)
AGENT1_DURATION=$((AGENT1_END - START_TIME))
echo -e "${GREEN}✅ Agent 1 completed in ${AGENT1_DURATION}s${NC}"
echo ""

# Find latest extraction file
LATEST_EXTRACTION=$(ls -t "$PROJECT_ROOT/data/kbli_extraction_"*.json 2>/dev/null | head -1)
if [ -z "$LATEST_EXTRACTION" ]; then
    echo -e "${RED}❌ No extraction file found${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Extraction file: $LATEST_EXTRACTION${NC}"
echo ""

# ============================================================
# AGENT 2: Transform to KG Entities
# ============================================================
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AGENT 2: Transform to KG Entities${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo ""

AGENT2_START=$(date +%s)

python "$SCRIPT_DIR/agent2_transform_kg_entities.py" --input "$LATEST_EXTRACTION"

AGENT2_END=$(date +%s)
AGENT2_DURATION=$((AGENT2_END - AGENT2_START))
echo -e "${GREEN}✅ Agent 2 completed in ${AGENT2_DURATION}s${NC}"
echo ""

# Find latest entities file
LATEST_ENTITIES=$(ls -t "$PROJECT_ROOT/data/kg_entities_"*.json 2>/dev/null | head -1)
if [ -z "$LATEST_ENTITIES" ]; then
    echo -e "${RED}❌ No entities file found${NC}"
    exit 1
fi

echo -e "${GREEN}📦 Entities file: $LATEST_ENTITIES${NC}"
echo ""

# ============================================================
# AGENT 3: Insert to PostgreSQL
# ============================================================
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AGENT 3: Insert to PostgreSQL${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo ""

AGENT3_START=$(date +%s)

python "$SCRIPT_DIR/agent3_insert_postgresql.py" --input "$LATEST_ENTITIES" $DRY_RUN

AGENT3_END=$(date +%s)
AGENT3_DURATION=$((AGENT3_END - AGENT3_START))
echo -e "${GREEN}✅ Agent 3 completed in ${AGENT3_DURATION}s${NC}"
echo ""

# ============================================================
# FINAL SUMMARY
# ============================================================
TOTAL_DURATION=$((AGENT3_END - START_TIME))

echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  FINAL SUMMARY${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✅ All agents completed successfully${NC}"
echo ""
echo -e "Agent 1 (Extract):    ${AGENT1_DURATION}s"
echo -e "Agent 2 (Transform):  ${AGENT2_DURATION}s"
echo -e "Agent 3 (Insert):     ${AGENT3_DURATION}s"
echo -e "${GREEN}Total time:           ${TOTAL_DURATION}s ($(($TOTAL_DURATION / 60))m $(($TOTAL_DURATION % 60))s)${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Verify KG expansion: curl https://nuzantara-rag.fly.dev/health/kg-stats | jq '.summary'"
echo -e "  2. Test KBLI queries via nuzantara-mcp MCP server"
echo -e "  3. Proceed with FASE 2: KBLI Scale Explosion"
echo ""
echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}"
