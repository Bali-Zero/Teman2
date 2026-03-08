#!/bin/bash
# Chat Streaming Test Script
# Tests SSE streaming functionality after deployment

set -e

FRONTEND_URL="https://kita.balizero.com"
CHAT_URL="$FRONTEND_URL/chat"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}💬 CHAT STREAMING TEST${NC}"
echo "========================"
echo ""

# Check if chat page loads
echo -e "${BLUE}1. Testing Chat Page Load${NC}"
echo "---------------------------"
CHAT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$CHAT_URL")
if [ "$CHAT_STATUS" -eq 200 ] || [ "$CHAT_STATUS" -eq 307 ]; then
    echo -e "${GREEN}✅ Chat page accessible (Status: $CHAT_STATUS)${NC}"
else
    echo -e "${RED}❌ Chat page error (Status: $CHAT_STATUS)${NC}"
    exit 1
fi

# Check for SSE endpoint (if exposed)
echo ""
echo -e "${BLUE}2. Testing SSE Endpoint${NC}"
echo "----------------------"
# Note: SSE endpoints are typically protected and require authentication
# This is a basic check - full testing requires browser automation
echo -e "${YELLOW}ℹ️  SSE endpoints require authentication${NC}"
echo -e "${YELLOW}ℹ️  Full testing requires browser automation (Playwright/Cypress)${NC}"

# Check for streaming-related JavaScript
echo ""
echo -e "${BLUE}3. Checking Streaming Code${NC}"
echo "-------------------------"
if curl -s "$CHAT_URL" | grep -qi "stream\|sse\|EventSource\|sendMessageStreaming"; then
    echo -e "${GREEN}✅ Streaming code detected in page${NC}"
else
    echo -e "${YELLOW}⚠️  Streaming code not found in HTML (may be in JS bundle)${NC}"
fi

# Manual Testing Instructions
echo ""
echo -e "${BLUE}📝 MANUAL TESTING INSTRUCTIONS${NC}"
echo "===================================="
echo ""
echo "To fully test chat streaming:"
echo "1. Open browser: $CHAT_URL"
echo "2. Login to the application"
echo "3. Send a test message"
echo "4. Verify:"
echo "   - Message appears immediately (optimistic update)"
echo "   - Streaming response appears character by character"
echo "   - No JavaScript errors in console"
echo "   - Connection stays stable"
echo "   - Can send multiple messages"
echo ""
echo "Expected Behavior:"
echo "  ✅ Messages stream in real-time"
echo "  ✅ No connection errors"
echo "  ✅ Proper error handling on failure"
echo "  ✅ Abort functionality works"
echo ""

echo -e "${GREEN}✅ Chat streaming test script completed${NC}"
echo ""
echo "For automated testing, use:"
echo "  - Playwright: npm run test:e2e"
echo "  - Cypress: npm run cypress:open"
