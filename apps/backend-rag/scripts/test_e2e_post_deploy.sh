#!/bin/bash
# E2E Tests Post-Deploy - Communication Features
# Tests the 3 scenarios from PROMPT 5 against production

set -e

RAG_BACKEND_URL="${RAG_BACKEND_URL:-https://nuzantara-rag.fly.dev}"
TEST_EMAIL="${TEST_EMAIL:-zero@balizero.com}"
TEST_PIN="${TEST_PIN:-010719}"

echo "🧪 E2E Post-Deploy Tests - Communication Features"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

test_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    exit 1
}

test_info() {
    echo -e "${YELLOW}ℹ️  INFO${NC}: $1"
}

# Test 1: Health Check
echo "📋 Test 1: Health Check"
echo "----------------------"
if curl -s -f "${RAG_BACKEND_URL}/health" > /dev/null 2>&1; then
    test_pass "Health check"
else
    test_fail "Health check failed"
fi
echo ""

# Test 2: Login
echo "📋 Test 2: Login"
echo "--------------"
LOGIN_RESPONSE=$(curl -s -X POST "https://nuzantara-backend.fly.dev/api/auth/team/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"pin\":\"${TEST_PIN}\"}" 2>&1)

if echo "$LOGIN_RESPONSE" | grep -q "token"; then
    TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    if [ -n "$TOKEN" ]; then
        test_pass "Login successful"
        test_info "Token: ${TOKEN:0:20}..."
    else
        test_fail "Login response missing token"
    fi
else
    test_fail "Login failed: $LOGIN_RESPONSE"
fi
echo ""

# Test 3: Scenario 1 - Same Language Response (Italian)
echo "📋 Test 3: Scenario 1 - Same Language Response"
echo "----------------------------------------------"
QUERY_1="Ciao, come stai?"
test_info "Query: $QUERY_1"

RESPONSE_1=$(timeout 30 curl -s -N "${RAG_BACKEND_URL}/bali-zero/chat-stream?query=${QUERY_1}&user_email=${TEST_EMAIL}&session_id=e2e_test_1" \
    -H "Authorization: Bearer ${TOKEN}" 2>&1 | head -50 || true)

if echo "$RESPONSE_1" | grep -qi "ciao\|bene\|come\|posso\|aiutarti\|grazie"; then
    test_pass "Italian response contains Italian keywords"
    test_info "Response preview: $(echo "$RESPONSE_1" | head -100 | tr '\n' ' ' | cut -c1-200)..."
else
    test_fail "Italian response missing Italian keywords"
    test_info "Response: $RESPONSE_1"
fi
echo ""

# Test 4: Scenario 2 - Empathetic Tone
echo "📋 Test 4: Scenario 2 - Empathetic Tone"
echo "---------------------------------------"
QUERY_2="Ho sbagliato tutto con il mio visto, sono disperato!"
test_info "Query: $QUERY_2"

RESPONSE_2=$(timeout 30 curl -s -N "${RAG_BACKEND_URL}/bali-zero/chat-stream?query=${QUERY_2}&user_email=${TEST_EMAIL}&session_id=e2e_test_2" \
    -H "Authorization: Bearer ${TOKEN}" 2>&1 | head -50 || true)

if echo "$RESPONSE_2" | grep -qi "capisco\|tranquillo\|aiuto\|soluzione\|possibilità"; then
    test_pass "Emotional response contains empathetic keywords"
    test_info "Response preview: $(echo "$RESPONSE_2" | head -100 | tr '\n' ' ' | cut -c1-200)..."
else
    test_fail "Emotional response missing empathetic keywords"
    test_info "Response: $RESPONSE_2"
fi
echo ""

# Test 5: Scenario 3 - Step-by-Step Instructions
echo "📋 Test 5: Scenario 3 - Step-by-Step Instructions"
echo "------------------------------------------------"
QUERY_3="Come faccio a richiedere il KITAS E33G?"
test_info "Query: $QUERY_3"

RESPONSE_3=$(timeout 30 curl -s -N "${RAG_BACKEND_URL}/bali-zero/chat-stream?query=${QUERY_3}&user_email=${TEST_EMAIL}&session_id=e2e_test_3" \
    -H "Authorization: Bearer ${TOKEN}" 2>&1 | head -100 || true)

if echo "$RESPONSE_3" | grep -qE "[1-9][\.\)]"; then
    NUMBERED_COUNT=$(echo "$RESPONSE_3" | grep -oE "[1-9][\.\)]" | wc -l | tr -d ' ')
    if [ "$NUMBERED_COUNT" -ge 2 ]; then
        test_pass "Procedural response contains numbered list ($NUMBERED_COUNT items)"
        test_info "Response preview: $(echo "$RESPONSE_3" | head -100 | tr '\n' ' ' | cut -c1-300)..."
    else
        test_fail "Procedural response has less than 2 numbered items ($NUMBERED_COUNT)"
    fi
else
    test_fail "Procedural response missing numbered list"
    test_info "Response: $RESPONSE_3"
fi
echo ""

# Summary
echo "=================================================="
echo "✅ All E2E Post-Deploy Tests Passed!"
echo "=================================================="

