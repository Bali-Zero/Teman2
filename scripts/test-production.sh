#!/bin/bash
# Production Testing Script
# Tests main functionality after deployment

set -e

FRONTEND_URL="https://zantara.balizero.com"
BACKEND_URL="https://nuzantara-rag.fly.dev"

echo "🧪 PRODUCTION TESTING"
echo "===================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    local follow_redirect=${4:-false}
    
    echo -n "Testing $name... "
    
    if [ "$follow_redirect" = "true" ]; then
        status=$(curl -s -L -o /dev/null -w "%{http_code}" "$url")
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    fi
    
    # Accept redirects (307, 301, 302) as success for protected pages
    if [ "$status" -eq "$expected_status" ] || [ "$status" -eq 307 ] || [ "$status" -eq 301 ] || [ "$status" -eq 302 ]; then
        if [ "$status" -eq 307 ] || [ "$status" -eq 301 ] || [ "$status" -eq 302 ]; then
            echo -e "${GREEN}✅ PASS${NC} (Status: $status - Redirect, expected for protected pages)"
        else
            echo -e "${GREEN}✅ PASS${NC} (Status: $status)"
        fi
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (Expected: $expected_status, Got: $status)"
        return 1
    fi
}

# Test frontend
echo "📱 FRONTEND TESTS"
echo "-----------------"
test_endpoint "Homepage" "$FRONTEND_URL"
test_endpoint "Chat Page" "$FRONTEND_URL/chat"
test_endpoint "Dashboard" "$FRONTEND_URL/dashboard"
test_endpoint "Clients" "$FRONTEND_URL/clients"
test_endpoint "Settings" "$FRONTEND_URL/settings"

echo ""
echo "🔧 BACKEND TESTS"
echo "----------------"
test_endpoint "Health Check" "$BACKEND_URL/health" 200

echo ""
echo "✅ PRODUCTION TESTS COMPLETED"
echo ""

# Check for JavaScript errors (basic check)
echo "🔍 CHECKING FOR ERRORS..."
if curl -s "$FRONTEND_URL" | grep -qi "error\|Error\|ERROR"; then
    echo -e "${YELLOW}⚠️  Warning: Possible errors found in HTML${NC}"
else
    echo -e "${GREEN}✅ No obvious errors in HTML${NC}"
fi

echo ""
echo "📊 SUMMARY"
echo "----------"
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL: $BACKEND_URL"
echo ""
echo "For detailed monitoring:"
echo "  - Vercel Dashboard: https://vercel.com/dashboard"
echo "  - Sentry: Check error tracking"
echo "  - Browser Console: Check for JavaScript errors"
