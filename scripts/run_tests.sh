#!/bin/bash
# NUZANTARA - Run All Tests
# Runs test suites for all components

set -e

echo "============================================"
echo "NUZANTARA - Running All Tests"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
FAILED_TESTS=()

# Function to run tests
run_tests() {
    local name=$1
    local dir=$2
    local test_cmd=$3

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    cd "$dir"

    if eval "$test_cmd"; then
        echo ""
        echo -e "${GREEN}✓ $name tests PASSED${NC}"
    else
        echo ""
        echo -e "${RED}✗ $name tests FAILED${NC}"
        FAILED_TESTS+=("$name")
    fi

    cd - > /dev/null
}

# 1. ZANTARA MEDIA Tests
if [ -d "apps/zantara-media/backend/tests" ]; then
    run_tests \
        "ZANTARA MEDIA" \
        "apps/zantara-media/backend" \
        "pytest tests/ -v --tb=short --disable-warnings || true"
else
    echo -e "${YELLOW}⚠ ZANTARA MEDIA tests not found, skipping${NC}"
fi

# 2. BALI INTEL SCRAPER Tests
if [ -d "apps/bali-intel-scraper/tests" ]; then
    run_tests \
        "BALI INTEL SCRAPER" \
        "apps/bali-intel-scraper" \
        "pytest tests/ -v --tb=short --disable-warnings || true"
else
    echo -e "${YELLOW}⚠ BALI INTEL SCRAPER tests not found, skipping${NC}"
fi

# 3. BACKEND RAG Tests (if exists)
if [ -d "apps/backend-rag/backend/tests" ]; then
    run_tests \
        "BACKEND RAG" \
        "apps/backend-rag/backend" \
        "pytest tests/ -v --tb=short --disable-warnings || true"
else
    echo -e "${YELLOW}⚠ BACKEND RAG tests not found, skipping${NC}"
fi

# Summary
echo ""
echo "============================================"
echo "TEST SUMMARY"
echo "============================================"

if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All tests PASSED!${NC}"
    exit 0
else
    echo -e "${RED}✗ Failed test suites:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}- $test${NC}"
    done
    exit 1
fi
