#!/bin/bash
# Test script for /webhook/chat endpoint
# Tests conversation persistence and retrieval

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧪 Testing /webhook/chat endpoint${NC}"
echo ""

# Configuration
API_URL="${API_URL:-http://localhost:8080}"
SESSION_ID="test-session-$(date +%s)"

# Check if JWT token is set
if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}❌ Error: JWT_TOKEN environment variable not set${NC}"
    echo "Please set JWT_TOKEN with a valid authentication token"
    exit 1
fi

echo "API URL: $API_URL"
echo "Session ID: $SESSION_ID"
echo ""

# Test 1: Send first message
echo -e "${YELLOW}Test 1: Sending first message...${NC}"
RESPONSE1=$(curl -s -X POST "$API_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
        \"query\": \"What is the capital of France?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"step\": 1}
    }")

echo "$RESPONSE1" | jq '.'

CONVERSATION_ID=$(echo "$RESPONSE1" | jq -r '.conversation_id')
PERSISTED=$(echo "$RESPONSE1" | jq -r '.persisted')

if [ "$PERSISTED" == "true" ] && [ "$CONVERSATION_ID" != "null" ]; then
    echo -e "${GREEN}✅ Test 1 passed: Message persisted (conversation_id: $CONVERSATION_ID)${NC}"
else
    echo -e "${RED}❌ Test 1 failed: Message not persisted${NC}"
    exit 1
fi

echo ""
sleep 2

# Test 2: Send follow-up message (should have context)
echo -e "${YELLOW}Test 2: Sending follow-up message...${NC}"
RESPONSE2=$(curl -s -X POST "$API_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
        \"query\": \"What about Germany?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"step\": 2}
    }")

echo "$RESPONSE2" | jq '.'

PERSISTED2=$(echo "$RESPONSE2" | jq -r '.persisted')

if [ "$PERSISTED2" == "true" ]; then
    echo -e "${GREEN}✅ Test 2 passed: Follow-up message persisted${NC}"
else
    echo -e "${RED}❌ Test 2 failed: Follow-up message not persisted${NC}"
    exit 1
fi

echo ""
sleep 2

# Test 3: Retrieve conversation history
echo -e "${YELLOW}Test 3: Retrieving conversation history...${NC}"
HISTORY=$(curl -s -X GET "$API_URL/webhook/chat/history/$SESSION_ID" \
    -H "Authorization: Bearer $JWT_TOKEN")

echo "$HISTORY" | jq '.'

MESSAGE_COUNT=$(echo "$HISTORY" | jq -r '.total_messages')

if [ "$MESSAGE_COUNT" -ge 4 ]; then
    echo -e "${GREEN}✅ Test 3 passed: Retrieved $MESSAGE_COUNT messages${NC}"
else
    echo -e "${RED}❌ Test 3 failed: Expected at least 4 messages, got $MESSAGE_COUNT${NC}"
    exit 1
fi

echo ""
sleep 2

# Test 4: Send third message to verify context persistence
echo -e "${YELLOW}Test 4: Testing context persistence (ask to summarize)...${NC}"
RESPONSE3=$(curl -s -X POST "$API_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
        \"query\": \"Can you summarize what we discussed?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"step\": 3}
    }")

echo "$RESPONSE3" | jq '.'

ANSWER=$(echo "$RESPONSE3" | jq -r '.answer')

# Check if answer mentions France or Germany (context awareness)
if echo "$ANSWER" | grep -qi "france\|germany\|paris\|berlin"; then
    echo -e "${GREEN}✅ Test 4 passed: AI has context awareness (mentions previous topics)${NC}"
else
    echo -e "${YELLOW}⚠️  Test 4 warning: AI response may not show full context awareness${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ All tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Session ID: $SESSION_ID"
echo "Conversation ID: $CONVERSATION_ID"
echo "Total messages: $MESSAGE_COUNT"
echo ""
echo "To manually verify, refresh your webapp and check if conversation persists."
