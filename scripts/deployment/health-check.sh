#!/bin/bash
# Health check script for deployed services
# Validates that all services are running and responsive

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MAX_RETRIES=10
RETRY_DELAY=10

# Services to check
BACKEND_URL="${BACKEND_URL:-https://nuzantara-rag.fly.dev}"
FRONTEND_URL="${FRONTEND_URL:-https://www.balizero.com}"

echo -e "${BLUE}🏥 Nuzantara Health Check${NC}"
echo "=================================="

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local max_retries=${3:-$MAX_RETRIES}
    
    echo ""
    echo -e "${YELLOW}Checking $name...${NC}"
    echo "URL: $url"
    
    for i in $(seq 1 $max_retries); do
        echo -n "Attempt $i/$max_retries: "
        
        # Try to fetch the endpoint
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
        
        if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
            echo -e "${GREEN}✓ Success (HTTP $HTTP_CODE)${NC}"
            
            # Try to get response body if it's a health endpoint
            if [[ "$url" == *"/health"* ]]; then
                echo "Response:"
                curl -s "$url" | jq . 2>/dev/null || curl -s "$url"
            fi
            
            return 0
        else
            echo -e "${RED}✗ Failed (HTTP $HTTP_CODE)${NC}"
            
            if [ $i -lt $max_retries ]; then
                echo "Retrying in ${RETRY_DELAY}s..."
                sleep $RETRY_DELAY
            fi
        fi
    done
    
    echo -e "${RED}❌ Health check failed after $max_retries attempts${NC}"
    return 1
}

# Function to check response time
check_latency() {
    local url=$1
    local name=$2
    
    echo ""
    echo -e "${YELLOW}Checking latency for $name...${NC}"
    
    RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}\n' "$url")
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Response time: ${RESPONSE_TIME}s${NC}"
        
        # Warn if response time is high
        if (( $(echo "$RESPONSE_TIME > 2" | bc -l) )); then
            echo -e "${YELLOW}⚠ Warning: High response time${NC}"
        fi
        
        return 0
    else
        echo -e "${RED}✗ Failed to measure response time${NC}"
        return 1
    fi
}

ERRORS=0

# Check Backend RAG
echo ""
echo "==================================="
echo "Backend RAG Service"
echo "==================================="
if check_endpoint "$BACKEND_URL/health" "Backend RAG Health"; then
    check_latency "$BACKEND_URL/health" "Backend RAG"
else
    ERRORS=$((ERRORS + 1))
fi

# Check Frontend
echo ""
echo "==================================="
echo "Mouth Frontend Service"
echo "==================================="
if check_endpoint "$FRONTEND_URL" "Mouth Frontend"; then
    check_latency "$FRONTEND_URL" "Mouth Frontend"
else
    ERRORS=$((ERRORS + 1))
fi

# Integration test - Frontend can reach Backend
echo ""
echo "==================================="
echo "Integration Tests"
echo "==================================="
echo -e "${YELLOW}Testing frontend-backend connectivity...${NC}"

# This would be replaced with actual integration test
echo -e "${GREEN}✓ Integration test placeholder${NC}"

# Summary
echo ""
echo "==================================="
echo "Health Check Summary"
echo "==================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All health checks passed!${NC}"
    echo ""
    echo "Service URLs:"
    echo "  Backend:  $BACKEND_URL"
    echo "  Frontend: $FRONTEND_URL"
    exit 0
else
    echo -e "${RED}❌ Health check failed with $ERRORS error(s)${NC}"
    exit 1
fi
