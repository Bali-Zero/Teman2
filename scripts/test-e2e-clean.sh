#!/bin/bash
# ZANTARA End-to-End Test Suite - Post Cleanup Verification
# Tests all critical paths after massive cleanup

set -e

echo "🧪 ZANTARA End-to-End Test Suite"
echo "================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

# Configuration
TS_BACKEND_URL="${TS_BACKEND_URL:-https://nuzantara-backend.fly.dev}"
RAG_BACKEND_URL="${RAG_BACKEND_URL:-https://nuzantara-rag.fly.dev}"
MEMORY_BACKEND_URL="${MEMORY_BACKEND_URL:-https://nuzantara-memory.fly.dev}"
WEBAPP_URL="${WEBAPP_URL:-https://zantara.balizero.com}"

# Test credentials (real team member)
TEST_EMAIL="zero@balizero.com"
TEST_PIN="010719"

# Helper functions
test_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAILED++))
}

test_skip() {
    echo -e "${YELLOW}⏭️  SKIP${NC}: $1"
    ((SKIPPED++))
}

test_info() {
    echo -e "${YELLOW}ℹ️  INFO${NC}: $1"
}

# Test 1: Health Checks
echo "📋 Phase 1: Health Checks"
echo "------------------------"

echo -n "Testing TypeScript Backend health... "
if curl -s -f "${TS_BACKEND_URL}/health" > /dev/null 2>&1; then
    test_pass "TypeScript Backend health check"
else
    test_fail "TypeScript Backend health check"
fi

echo -n "Testing RAG Backend health... "
if curl -s -f "${RAG_BACKEND_URL}/healthz" > /dev/null 2>&1; then
    test_pass "RAG Backend health check"
else
    test_fail "RAG Backend health check"
fi

echo -n "Testing Memory Backend health... "
if curl -s -f "${MEMORY_BACKEND_URL}/health" > /dev/null 2>&1; then
    test_pass "Memory Backend health check"
else
    test_fail "Memory Backend health check"
fi

echo ""

# Test 2: Login Flow
echo "📋 Phase 2: Login Flow"
echo "---------------------"

echo -n "Testing login endpoint... "
LOGIN_RESPONSE=$(curl -s -X POST "${TS_BACKEND_URL}/api/auth/team/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"pin\":\"${TEST_PIN}\"}" 2>&1)

if echo "$LOGIN_RESPONSE" | grep -q "token"; then
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    if [ -n "$TOKEN" ]; then
        test_pass "Login successful, token received"
        test_info "Token: ${TOKEN:0:20}..."
    else
        test_fail "Login response missing token"
    fi
else
    test_fail "Login failed: $LOGIN_RESPONSE"
    TOKEN=""
fi

echo ""

# Test 3: System Handlers
echo "📋 Phase 3: System Handlers"
echo "---------------------------"

if [ -n "$TOKEN" ]; then
    echo -n "Testing system.handlers.tools... "
    TOOLS_RESPONSE=$(curl -s -X POST "${TS_BACKEND_URL}/call" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "x-user-email: ${TEST_EMAIL}" \
        -d '{"key":"system.handlers.tools"}' 2>&1)

    if echo "$TOOLS_RESPONSE" | grep -q "tools"; then
        TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | grep -o '"tools"' | wc -l | tr -d ' ')
        test_pass "System handlers tools retrieved (found tools)"
        test_info "Tools response received"
    else
        test_fail "System handlers tools failed: $TOOLS_RESPONSE"
    fi
else
    test_skip "System handlers (no token)"
fi

echo ""

# Test 4: RAG Chat Streaming
echo "📋 Phase 4: RAG Chat Streaming"
echo "-----------------------------"

if [ -n "$TOKEN" ]; then
    echo -n "Testing chat stream endpoint... "
    STREAM_RESPONSE=$(timeout 5 curl -s -N "${RAG_BACKEND_URL}/bali-zero/chat-stream?query=test&user_email=${TEST_EMAIL}&session_id=test" \
        -H "Authorization: Bearer ${TOKEN}" 2>&1 || true)

    if echo "$STREAM_RESPONSE" | grep -q "token\|done\|error"; then
        test_pass "Chat stream endpoint responding"
    else
        test_fail "Chat stream endpoint not responding correctly"
    fi
else
    test_skip "RAG chat streaming (no token)"
fi

echo ""

# Test 5: Team Knowledge
echo "📋 Phase 5: Team Knowledge"
echo "-------------------------"

if [ -n "$TOKEN" ]; then
    echo -n "Testing team member search... "
    TEAM_QUERY="chi è Amanda"
    TEAM_RESPONSE=$(timeout 10 curl -s -N "${RAG_BACKEND_URL}/bali-zero/chat-stream?query=${TEAM_QUERY}&user_email=${TEST_EMAIL}&session_id=team_test" \
        -H "Authorization: Bearer ${TOKEN}" 2>&1 | head -20 || true)

    if echo "$TEAM_RESPONSE" | grep -qi "amanda\|team\|membro"; then
        test_pass "Team knowledge query responded"
    else
        test_fail "Team knowledge query failed or generic response"
    fi
else
    test_skip "Team knowledge (no token)"
fi

echo ""

# Test 6: Webapp Accessibility
echo "📋 Phase 6: Webapp Accessibility"
echo "--------------------------------"

echo -n "Testing login page... "
if curl -s -f "${WEBAPP_URL}/login.html" > /dev/null 2>&1; then
    test_pass "Login page accessible"
else
    test_fail "Login page not accessible"
fi

echo -n "Testing chat page (should redirect if not logged in)... "
CHAT_RESPONSE=$(curl -s -L "${WEBAPP_URL}/chat.html" 2>&1 | head -5)
if echo "$CHAT_RESPONSE" | grep -q "login\|chat\|zantara"; then
    test_pass "Chat page accessible or redirects correctly"
else
    test_fail "Chat page not accessible"
fi

echo ""

# Test 7: Legacy Code Audit
echo "📋 Phase 7: Legacy Code Audit"
echo "-----------------------------"

if [ -f "./scripts/audit-legacy.sh" ]; then
    echo -n "Running legacy code audit... "
    AUDIT_OUTPUT=$(./scripts/audit-legacy.sh 2>&1)
    if echo "$AUDIT_OUTPUT" | grep -q "Errors found: 0"; then
        test_pass "Legacy code audit: 0 errors"
    else
        ERROR_COUNT=$(echo "$AUDIT_OUTPUT" | grep -o "Errors found: [0-9]*" | grep -o "[0-9]*")
        test_fail "Legacy code audit: $ERROR_COUNT errors found"
    fi
else
    test_skip "Legacy code audit (script not found)"
fi

echo ""

# Summary
echo "================================="
echo "📊 Test Summary"
echo "================================="
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo -e "${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED + SKIPPED))
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
