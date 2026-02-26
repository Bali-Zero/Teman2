#!/bin/bash
# Test conversation persistence in LOCAL environment
# No authentication required for local testing

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🧪 Testing Conversation Persistence (LOCAL)${NC}"
echo ""

# Configuration
LOCAL_URL="${LOCAL_URL:-http://localhost:8080}"
SESSION_ID="local-test-$(date +%s)"

echo "🌐 Local URL: $LOCAL_URL"
echo "🔑 Session ID: $SESSION_ID"
echo ""

# Check if backend is running
echo -e "${YELLOW}Checking if backend is running...${NC}"
if ! curl -f -s "$LOCAL_URL/docs" > /dev/null 2>&1; then
    echo -e "${RED}❌ Backend not running at $LOCAL_URL${NC}"
    echo ""
    echo "Start the backend first:"
    echo "  cd apps/backend-rag/backend"
    echo "  uvicorn backend.app.main_cloud:app --reload --port 8080"
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"
echo ""

# Test 1: Send first message
echo -e "${YELLOW}Test 1: Sending first message...${NC}"
RESPONSE1=$(curl -s -X POST "$LOCAL_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"Ciao, come ti chiami?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"environment\": \"local\"}
    }")

echo "$RESPONSE1" | jq '.' 2>/dev/null || echo "$RESPONSE1"

PERSISTED=$(echo "$RESPONSE1" | jq -r '.persisted' 2>/dev/null || echo "false")
CONV_ID=$(echo "$RESPONSE1" | jq -r '.conversation_id' 2>/dev/null || echo "null")

if [ "$PERSISTED" == "true" ] && [ "$CONV_ID" != "null" ]; then
    echo -e "${GREEN}✅ Message persisted (ID: $CONV_ID)${NC}"
else
    echo -e "${RED}❌ Message NOT persisted${NC}"
    echo "Response: $RESPONSE1"
    exit 1
fi
echo ""

sleep 2

# Test 2: Send follow-up message
echo -e "${YELLOW}Test 2: Sending follow-up message...${NC}"
RESPONSE2=$(curl -s -X POST "$LOCAL_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"Ricordi come ti chiami?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"step\": 2}
    }")

echo "$RESPONSE2" | jq '.' 2>/dev/null || echo "$RESPONSE2"

PERSISTED2=$(echo "$RESPONSE2" | jq -r '.persisted' 2>/dev/null || echo "false")
ANSWER=$(echo "$RESPONSE2" | jq -r '.answer' 2>/dev/null || echo "")

if [ "$PERSISTED2" == "true" ]; then
    echo -e "${GREEN}✅ Follow-up message persisted${NC}"
else
    echo -e "${RED}❌ Follow-up NOT persisted${NC}"
    exit 1
fi

# Check if AI remembers context
if echo "$ANSWER" | grep -qi "zantara\|nome"; then
    echo -e "${GREEN}✅ AI has context awareness (remembers name)${NC}"
else
    echo -e "${YELLOW}⚠️  Context awareness unclear${NC}"
fi
echo ""

# Test 3: Retrieve history
echo -e "${YELLOW}Test 3: Retrieving conversation history...${NC}"
HISTORY=$(curl -s -X GET "$LOCAL_URL/webhook/chat/history/$SESSION_ID")

echo "$HISTORY" | jq '.' 2>/dev/null || echo "$HISTORY"

MSG_COUNT=$(echo "$HISTORY" | jq -r '.total_messages' 2>/dev/null || echo "0")

if [ "$MSG_COUNT" -ge 4 ]; then
    echo -e "${GREEN}✅ History retrieved ($MSG_COUNT messages)${NC}"
else
    echo -e "${RED}❌ Expected at least 4 messages, got $MSG_COUNT${NC}"
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ All local tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 Test Summary:"
echo "  • Session ID: $SESSION_ID"
echo "  • Conversation ID: $CONV_ID"
echo "  • Messages persisted: $MSG_COUNT"
echo "  • Backend: $LOCAL_URL"
echo ""
echo "🎉 Sistema di persistenza funzionante in locale!"
echo ""
echo "Next: Deploy to production and test with real JWT token"
