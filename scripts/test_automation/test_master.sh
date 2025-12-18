#!/bin/bash
# Test Master - Orchestrazione Completa Test Automation
# Esegue tutti gli strumenti di test automation in sequenza

set -e

echo "🤖 TEST MASTER - Complete Test Automation"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
TARGET_COVERAGE=${1:-90}
DRY_RUN=${2:-false}

echo "Configuration:"
echo "  Target Coverage: ${TARGET_COVERAGE}%"
echo "  Dry Run: $DRY_RUN"
echo ""

# Step 1: Test Quality Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/4: Test Quality Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 scripts/test_automation/test_quality_checker.py apps/backend-rag/tests/unit || {
    echo -e "${YELLOW}⚠️  Some tests have quality issues${NC}"
}

echo ""

# Step 2: Coverage Analysis
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/4: Coverage Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 scripts/test_automation/coverage_monitor.py $TARGET_COVERAGE || {
    echo -e "${YELLOW}⚠️  Coverage below target${NC}"
}

echo ""

# Step 3: Test Generation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/4: Auto-Generate Missing Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$DRY_RUN" = "true" ]; then
    python3 scripts/test_automation/test_generator.py --dry-run
else
    python3 scripts/test_automation/test_generator.py
fi

echo ""

# Step 4: Run All Tests
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/4: Run Complete Test Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd apps/backend-rag

# Run tests
pytest tests/unit -v --cov=backend --cov-config=.coveragerc --cov-report=term-missing --cov-report=json:coverage.json || {
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
}

cd ../..

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TEST MASTER COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Reports Generated:"
echo "  - test_quality_report.txt"
echo "  - coverage_report.txt"
echo "  - apps/backend-rag/coverage.json"
echo ""
echo "💡 Next Steps:"
echo "  1. Review quality report for test improvements"
echo "  2. Check coverage report for gaps"
echo "  3. Implement generated test skeletons"
echo "  4. Run again to verify improvements"
echo ""
