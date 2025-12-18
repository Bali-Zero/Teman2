#!/bin/bash
#
# Test Master - Complete Test Automation Orchestration
#
# Runs all test automation tools in sequence:
# 1. Test Quality Check
# 2. Coverage Analysis
# 3. Auto-Generate Missing Tests
# 4. Run Complete Test Suite
#
# Usage:
#   ./test_master.sh [target_coverage] [dry_run]
#
# Examples:
#   ./test_master.sh              # Target 90%, real run
#   ./test_master.sh 85           # Target 85%, real run
#   ./test_master.sh 90 true      # Target 90%, dry run
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parameters
TARGET_COVERAGE=${1:-90}
DRY_RUN=${2:-false}

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🤖 TEST MASTER - Complete Test Automation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Target Coverage: ${GREEN}${TARGET_COVERAGE}%${NC}"
echo -e "Dry Run: ${YELLOW}${DRY_RUN}${NC}"
echo ""

# Step 1: Test Quality Check
echo -e "${YELLOW}Step 1/4: Test Quality Check${NC}"
echo "─────────────────────────────────────────────────────────────"
python3 scripts/test_automation/test_quality_checker.py || true
echo ""

# Step 2: Coverage Analysis
echo -e "${YELLOW}Step 2/4: Coverage Analysis${NC}"
echo "─────────────────────────────────────────────────────────────"
python3 scripts/test_automation/coverage_monitor.py ${TARGET_COVERAGE} || true
echo ""

# Step 3: Auto-Generate Missing Tests
echo -e "${YELLOW}Step 3/4: Auto-Generate Missing Tests${NC}"
echo "─────────────────────────────────────────────────────────────"
if [ "$DRY_RUN" = "true" ]; then
    python3 scripts/test_automation/test_generator.py --dry-run
else
    python3 scripts/test_automation/test_generator.py
fi
echo ""

# Step 4: Run Complete Test Suite
echo -e "${YELLOW}Step 4/4: Run Complete Test Suite${NC}"
echo "─────────────────────────────────────────────────────────────"
cd apps/backend-rag
pytest tests/unit -v --cov=backend --cov-report=term-missing --cov-report=json:coverage.json --tb=short || true
cd ../..
echo ""

# Summary
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ TEST MASTER COMPLETE${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}📊 Reports Generated:${NC}"
echo -e "  - ${YELLOW}test_quality_report.txt${NC}"
echo -e "  - ${YELLOW}coverage_report.txt${NC}"
echo -e "  - ${YELLOW}apps/backend-rag/coverage.json${NC}"
echo ""
echo -e "${GREEN}💡 Next Steps:${NC}"
echo -e "  1. Review ${YELLOW}test_quality_report.txt${NC} for quality issues"
echo -e "  2. Review ${YELLOW}coverage_report.txt${NC} for coverage gaps"
echo -e "  3. Implement auto-generated test skeletons"
echo -e "  4. Re-run to verify improvements"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
