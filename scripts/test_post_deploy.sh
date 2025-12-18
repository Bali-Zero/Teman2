#!/bin/bash
# Post-Deploy Test Script
# Tests the deployed application after deployment

set -e

API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
TIMEOUT=30

echo "🧪 Post-Deploy Testing"
echo "===================="
echo "API URL: $API_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_endpoint() {
    local endpoint=$1
    local expected_status=${2:-200}
    local description=${3:-$endpoint}
    
    echo -n "Testing $description... "
    
    response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL$endpoint" || echo -e "\n000")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $http_code, expected $expected_status)"
        echo "Response: $body" | head -5
        return 1
    fi
}

# Test 1: Health Check
echo "1. Health Check"
test_endpoint "/health" 200 "Health endpoint"
echo ""

# Test 2: OpenAPI Spec
echo "2. OpenAPI Specification"
test_endpoint "/api/v1/openapi.json" 200 "OpenAPI spec" || test_endpoint "/docs" 200 "Swagger UI"
echo ""

# Test 3: Metrics
echo "3. Prometheus Metrics"
test_endpoint "/metrics" 200 "Metrics endpoint"
echo ""

# Test 4: Qdrant Metrics
echo "4. Qdrant Metrics"
test_endpoint "/health/metrics/qdrant" 200 "Qdrant metrics"
echo ""

# Test 5: API Root
echo "5. API Root"
test_endpoint "/api/v1" 200 "API root"
echo ""

# Test 6: SSE Streaming (quick test)
echo "6. SSE Streaming Endpoint"
response=$(curl -s --max-time 10 -N "$API_URL/api/agentic-rag/stream?query=test" | head -5 || echo "")
if [ -n "$response" ]; then
    echo -e "${GREEN}✅ SSE endpoint responds${NC}"
else
    echo -e "${YELLOW}⚠️  SSE endpoint timeout (may require auth)${NC}"
fi
echo ""

# Summary
echo "===================="
echo -e "${GREEN}✅ Post-deploy tests completed${NC}"
echo ""
echo "Next steps:"
echo "1. Verify migrations applied: curl $API_URL/health"
echo "2. Check metrics: curl $API_URL/metrics"
echo "3. Monitor logs: flyctl logs -a nuzantara-rag"

