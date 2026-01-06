#!/bin/bash
# Script 7: Integration tests for migrated services
# Usage: ./07-integration-tests.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  INTEGRATION TESTS                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Get service URLs
echo -e "${YELLOW}→ Enter Railway backend URL:${NC}"
read -r BACKEND_URL

echo -e "${YELLOW}→ Enter Vercel frontend URL:${NC}"
read -r FRONTEND_URL

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name=$1
    local test_command=$2

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -e "\n${BLUE}TEST $TOTAL_TESTS: $test_name${NC}"

    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# =============================================================================
# BACKEND TESTS
# =============================================================================

echo -e "\n${BLUE}━━━ Backend Tests ━━━${NC}\n"

run_test "Backend health check" \
    "curl -f \"${BACKEND_URL}/health\" -s | grep -q 'status'"

run_test "Backend root endpoint" \
    "curl -f \"${BACKEND_URL}/\" -s"

run_test "API docs accessible" \
    "curl -f \"${BACKEND_URL}/docs\" -s | grep -q 'swagger'"

run_test "Database connection" \
    "curl -f \"${BACKEND_URL}/health\" -s | grep -q 'database'"

run_test "Qdrant connection" \
    "curl -f \"${BACKEND_URL}/health\" -s | grep -q 'qdrant'"

# =============================================================================
# FRONTEND TESTS
# =============================================================================

echo -e "\n${BLUE}━━━ Frontend Tests ━━━${NC}\n"

run_test "Frontend accessible" \
    "curl -f \"${FRONTEND_URL}\" -s | grep -q 'html'"

run_test "Frontend loads React" \
    "curl -f \"${FRONTEND_URL}\" -s | grep -q 'react'"

run_test "API proxy working" \
    "curl -f \"${FRONTEND_URL}/api/health\" -s"

# =============================================================================
# API TESTS (with auth)
# =============================================================================

echo -e "\n${BLUE}━━━ API Endpoint Tests ━━━${NC}\n"

echo -e "${YELLOW}Enter test JWT token (or skip):${NC}"
read -r JWT_TOKEN

if [ -n "$JWT_TOKEN" ]; then
    AUTH_HEADER="Authorization: Bearer $JWT_TOKEN"

    run_test "Chat endpoint (authenticated)" \
        "curl -f -X POST \"${BACKEND_URL}/api/chat\" \
        -H 'Content-Type: application/json' \
        -H '$AUTH_HEADER' \
        -d '{\"message\": \"test\", \"user_id\": \"test\"}' -s"

    run_test "Search endpoint" \
        "curl -f -X POST \"${BACKEND_URL}/api/search\" \
        -H 'Content-Type: application/json' \
        -H '$AUTH_HEADER' \
        -d '{\"query\": \"test\"}' -s"

else
    echo -e "${YELLOW}⚠ Skipping authenticated tests${NC}"
fi

# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

echo -e "\n${BLUE}━━━ Performance Tests ━━━${NC}\n"

echo -e "${YELLOW}Testing response times...${NC}"

# Backend response time
START_TIME=$(date +%s%N)
curl -f "${BACKEND_URL}/health" -s > /dev/null
END_TIME=$(date +%s%N)
RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))

echo -e "${BLUE}Backend response time: ${RESPONSE_TIME}ms${NC}"

if [ "$RESPONSE_TIME" -lt 1000 ]; then
    echo -e "${GREEN}✓ Good (<1s)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${YELLOW}⚠ Slow (>1s)${NC}"
fi

# Frontend response time
START_TIME=$(date +%s%N)
curl -f "${FRONTEND_URL}" -s > /dev/null
END_TIME=$(date +%s%N)
RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))

echo -e "${BLUE}Frontend response time: ${RESPONSE_TIME}ms${NC}"

if [ "$RESPONSE_TIME" -lt 2000 ]; then
    echo -e "${GREEN}✓ Good (<2s)${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${YELLOW}⚠ Slow (>2s)${NC}"
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo -e "\n${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  TEST SUMMARY                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

echo -e "${BLUE}Total tests:  $TOTAL_TESTS${NC}"
echo -e "${GREEN}Passed:       $PASSED_TESTS${NC}"
echo -e "${RED}Failed:       $FAILED_TESTS${NC}"

SUCCESS_RATE=$(( PASSED_TESTS * 100 / TOTAL_TESTS ))
echo -e "${BLUE}Success rate: ${SUCCESS_RATE}%${NC}\n"

if [ "$FAILED_TESTS" -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Migration successful.${NC}\n"
    exit 0
else
    echo -e "${YELLOW}⚠ Some tests failed. Review before production cutover.${NC}\n"
    exit 1
fi
