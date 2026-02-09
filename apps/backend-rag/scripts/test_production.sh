#!/bin/bash
# Test conversation persistence in production
# Quick verification script

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🧪 Testing Conversation Persistence in Production${NC}"
echo ""

# Configuration
PROD_URL="${PROD_URL:-https://nuzantara-rag.fly.dev}"
SESSION_ID="prod-test-$(date +%s)"

# Check if JWT token is set
if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}❌ JWT_TOKEN not set${NC}"
    echo "Export your token: export JWT_TOKEN='your-token'"
    exit 1
fi

echo "🌐 Production URL: $PROD_URL"
echo "🔑 Session ID: $SESSION_ID"
echo ""

# Test 1: Send first message (questo verifica anche che il backend sia attivo)
echo -e "${YELLOW}Test 1: Sending first message...${NC}"
RESPONSE1=$(curl -s -X POST "$PROD_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
        \"query\": \"Ciao, come ti chiami?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"environment\": \"production\"}
    }")

echo "$RESPONSE1" | jq '.'

PERSISTED=$(echo "$RESPONSE1" | jq -r '.persisted')
CONV_ID=$(echo "$RESPONSE1" | jq -r '.conversation_id')

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
RESPONSE2=$(curl -s -X POST "$PROD_URL/webhook/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "{
        \"query\": \"Ricordi come ti chiami?\",
        \"session_id\": \"$SESSION_ID\",
        \"metadata\": {\"test\": true, \"step\": 2}
    }")

echo "$RESPONSE2" | jq '.'

PERSISTED2=$(echo "$RESPONSE2" | jq -r '.persisted')
ANSWER=$(echo "$RESPONSE2" | jq -r '.answer')

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
HISTORY=$(curl -s -X GET "$PROD_URL/webhook/chat/history/$SESSION_ID" \
    -H "Authorization: Bearer $JWT_TOKEN")

echo "$HISTORY" | jq '.'

MSG_COUNT=$(echo "$HISTORY" | jq -r '.total_messages')

if [ "$MSG_COUNT" -ge 4 ]; then
    echo -e "${GREEN}✅ History retrieved ($MSG_COUNT messages)${NC}"
else
    echo -e "${RED}❌ Expected at least 4 messages, got $MSG_COUNT${NC}"
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ All production tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 Test Summary:"
echo "  • Session ID: $SESSION_ID"
echo "  • Conversation ID: $CONV_ID"
echo "  • Messages persisted: $MSG_COUNT"
echo "  • Backend: $PROD_URL"
echo ""
echo "🎉 Sistema di persistenza funzionante in produzione!"
echo ""
echo "Next steps:"
echo "  1. Update frontend to use /webhook/chat"
echo "  2. Deploy frontend to Vercel"
echo "  3. Test with real users"
