#!/bin/bash

echo "🧪 ZANTARA Pricing Integration Test Suite"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test endpoint
test_query() {
    local description="$1"
    local query="$2"
    local expected="$3"

    echo -n "Testing: $description ... "

    response=$(curl -s -X POST 'http://localhost:8000/bali-zero/chat' \
        -H 'Content-Type: application/json' \
        -d "{\"query\": \"$query\"}")

    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "Expected: $expected"
        echo "Got: $response" | head -5
        ((FAILED++))
    fi
}

# Health check
echo "1. Health Check"
echo "---------------"
curl -s http://localhost:8000/health | python3 -m json.tool
echo ""

# Run tests
echo "2. Pricing Query Tests"
echo "---------------------"
echo ""

# TABULA RASA: Test queries use generic terms - no specific codes
test_query "Indonesian long-stay permit query" "Berapa harga long-stay permit?" "IDR"
test_query "Italian remote worker query" "Quanto costa remote worker visa?" "Remote Worker"
test_query "English long-stay permit query" "How much is long-stay permit for remote workers?" "Remote Worker"
test_query "Tax registration query" "Berapa biaya tax registration?" "IDR"
test_query "Tourism visa query" "Price for tourism visa?" "IDR"
test_query "Company setup query" "How much to setup company?" "IDR"
test_query "Business permit query" "Long-stay permit for business owner price?" "permit"
test_query "Tax service query" "Cost of annual tax filing?" "taxation"

echo ""
echo "3. Direct Pricing Endpoints"
echo "---------------------------"
echo ""

echo -n "GET /pricing/all ... "
if curl -s http://localhost:8000/pricing/all | grep -q "PREZZI UFFICIALI"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo -n "GET /pricing/visa ... "
if curl -s http://localhost:8000/pricing/visa | grep -q "IDR"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo -n "GET /pricing/kitas ... "
if curl -s http://localhost:8000/pricing/kitas | grep -q "IDR"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo -n "POST /pricing/search ... "
if curl -s -X POST http://localhost:8000/pricing/search -H 'Content-Type: application/json' -d '{"query":"remote worker permit"}' | grep -q "Remote Worker"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo ""
echo "=========================================="
echo "📊 Test Results"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
fi
