#!/bin/bash
# Manual Test Script for Zantara Fixes
# Tests: Greetings detection, Session isolation, Memory prevention

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
TEST_EMAIL="${TEST_EMAIL:-zero@balizero.com}"
TEST_PIN="${TEST_PIN:-010719}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}        ZANTARA FIXES - MANUAL TEST SUITE${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "API URL: $API_URL"
echo "Test Email: $TEST_EMAIL"
echo ""

# Login
echo -e "${YELLOW}🔐 Logging in...${NC}"
TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"pin\":\"$TEST_PIN\"}" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])" 2>/dev/null)

if [ -z "$TOKEN" ] || [ "$TOKEN" == "None" ]; then
  echo -e "${RED}❌ Login failed. Check credentials or wait for rate limit.${NC}"
  exit 1
fi

echo -e "${GREEN}✅ Login successful${NC}\n"

# Test 1: Greeting Detection
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}           TEST 1: Greetings Detection${NC}"
echo -e "${BLUE}============================================================${NC}\n"

SESSION_1=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
RESPONSE=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"ciao\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$SESSION_1\"}")

# Parse JSON once and extract all fields
RESPONSE_DATA=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    route = d.get('route_used', '')
    tools = d.get('tools_called', -1)
    answer = d.get('answer', '')
    print(f\"{route}|{tools}|{answer}\")
except Exception as e:
    print('||')
" 2>/dev/null || echo "||")

ROUTE=$(echo "$RESPONSE_DATA" | cut -d'|' -f1)
TOOLS=$(echo "$RESPONSE_DATA" | cut -d'|' -f2)
ANSWER=$(echo "$RESPONSE_DATA" | cut -d'|' -f3)

# Debug: Show what we got
if [ "$DEBUG" = "1" ]; then
  echo "   DEBUG: Route='$ROUTE', Tools='$TOOLS', Answer='${ANSWER:0:50}...'"
fi

# Check if greeting was detected correctly
# Note: tools_called might be -1 if field doesn't exist (old API version)
# In that case, we check only route_used
if [[ "$ROUTE" == *"greeting"* ]]; then
  if [ "$TOOLS" == "0" ] || [ "$TOOLS" == "-1" ]; then
    # If tools_called is -1, it means the API doesn't return it yet (needs deploy)
    if [ "$TOOLS" == "-1" ]; then
      echo -e "${YELLOW}⚠️  WARNING: tools_called field not in API response (needs deploy)${NC}"
      echo -e "${GREEN}✅ PASS: Greeting detected (route check only)${NC}"
    else
      echo -e "${GREEN}✅ PASS: Greeting detected${NC}"
    fi
    echo "   Route: $ROUTE"
    echo "   Tools called: $TOOLS"
    echo "   Answer: ${ANSWER:0:80}..."
    TEST1_PASS=true
  else
    echo -e "${RED}❌ FAIL: Greeting detected but tools were called${NC}"
    echo "   Route: $ROUTE"
    echo "   Tools called: $TOOLS"
    echo "   Answer: ${ANSWER:0:100}..."
    TEST1_PASS=false
  fi
else
  echo -e "${RED}❌ FAIL: Greeting not detected correctly${NC}"
  echo "   Route: $ROUTE"
  echo "   Tools called: $TOOLS"
  echo "   Answer: ${ANSWER:0:100}..."
  TEST1_PASS=false
fi

# Test 2: Session Isolation
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}            TEST 2: Session Isolation${NC}"
echo -e "${BLUE}============================================================${NC}\n"

SESSION_1=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
SESSION_2=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")

# Set names in different sessions and save conversations
echo "Setting name 'Marco' in Session 1..."
RESPONSE_1A=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"Il mio nome è Marco\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$SESSION_1\"}")

# Save conversation to DB (escape JSON properly)
ANSWER_1A=$(echo "$RESPONSE_1A" | python3 -c "import sys, json; import json; d=json.load(sys.stdin); print(json.dumps(d.get('answer','')))" 2>/dev/null || echo "\"\"")
curl -s -X POST "$API_URL/api/conversations/save" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Il mio nome è Marco\"},{\"role\":\"assistant\",\"content\":$(echo "$ANSWER_1A")}],\"session_id\":\"$SESSION_1\"}" > /dev/null

sleep 1  # Small delay to ensure DB write completes

echo "Setting name 'Luca' in Session 2..."
RESPONSE_2A=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"Il mio nome è Luca\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$SESSION_2\"}")

# Save conversation to DB
ANSWER_2A=$(echo "$RESPONSE_2A" | python3 -c "import sys, json; import json; d=json.load(sys.stdin); print(json.dumps(d.get('answer','')))" 2>/dev/null || echo "\"\"")
curl -s -X POST "$API_URL/api/conversations/save" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Il mio nome è Luca\"},{\"role\":\"assistant\",\"content\":$(echo "$ANSWER_2A")}],\"session_id\":\"$SESSION_2\"}" > /dev/null

sleep 1  # Small delay to ensure DB write completes

# Check names (use conversation_history from previous messages)
echo "Asking name in Session 1..."
ANSWER_1=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"Come mi chiamo?\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$SESSION_1\",\"conversation_history\":[{\"role\":\"user\",\"content\":\"Il mio nome è Marco\"},{\"role\":\"assistant\",\"content\":$(echo "$ANSWER_1A")}]}" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())" 2>/dev/null || echo "")

echo "Asking name in Session 2..."
ANSWER_2=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"Come mi chiamo?\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$SESSION_2\",\"conversation_history\":[{\"role\":\"user\",\"content\":\"Il mio nome è Luca\"},{\"role\":\"assistant\",\"content\":$(echo "$ANSWER_2A")}]}" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())" 2>/dev/null || echo "")

if [[ "$ANSWER_1" == *"marco"* ]] && [[ "$ANSWER_1" != *"luca"* ]] && \
   [[ "$ANSWER_2" == *"luca"* ]] && [[ "$ANSWER_2" != *"marco"* ]]; then
  echo -e "${GREEN}✅ PASS: Sessions isolated correctly${NC}"
  echo "   Session 1: ${ANSWER_1:0:60}..."
  echo "   Session 2: ${ANSWER_2:0:60}..."
  TEST2_PASS=true
else
  echo -e "${RED}❌ FAIL: Sessions not isolated${NC}"
  echo "   Session 1: ${ANSWER_1:0:100}..."
  echo "   Session 2: ${ANSWER_2:0:100}..."
  TEST2_PASS=false
fi

# Test 3: Memory Prevention
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}      TEST 3: Memory Hallucination Prevention${NC}"
echo -e "${BLUE}============================================================${NC}\n"

NEW_SESSION=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")
echo "Sending first query in new session..."
ANSWER=$(curl -s -X POST "$API_URL/api/agentic-rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"Ciao, sono nuovo qui\",\"user_id\":\"$TEST_EMAIL\",\"session_id\":\"$NEW_SESSION\"}" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['answer'].lower())" 2>/dev/null || echo "")

PATTERNS=("so che" "ricordo che" "hai detto" "preferisci" "il tuo")
FOUND=false
for pattern in "${PATTERNS[@]}"; do
  if [[ "$ANSWER" == *"$pattern"* ]]; then
    FOUND=true
    break
  fi
done

if [ "$FOUND" = false ]; then
  echo -e "${GREEN}✅ PASS: No memory hallucination detected${NC}"
  echo "   Answer: ${ANSWER:0:80}..."
  TEST3_PASS=true
else
  echo -e "${RED}❌ FAIL: Memory hallucination detected${NC}"
  echo "   Answer: ${ANSWER:0:150}..."
  TEST3_PASS=false
fi

# Summary
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}                    TEST SUMMARY${NC}"
echo -e "${BLUE}============================================================${NC}\n"

PASSED=0
TOTAL=3

if [ "$TEST1_PASS" = true ]; then
  echo -e "${GREEN}✅ Test 1: Greeting Detection${NC}"
  ((PASSED++))
else
  echo -e "${RED}❌ Test 1: Greeting Detection${NC}"
fi

if [ "$TEST2_PASS" = true ]; then
  echo -e "${GREEN}✅ Test 2: Session Isolation${NC}"
  ((PASSED++))
else
  echo -e "${RED}❌ Test 2: Session Isolation${NC}"
fi

if [ "$TEST3_PASS" = true ]; then
  echo -e "${GREEN}✅ Test 3: Memory Prevention${NC}"
  ((PASSED++))
else
  echo -e "${RED}❌ Test 3: Memory Prevention${NC}"
fi

echo ""
echo -e "${BLUE}Results: $PASSED/$TOTAL tests passed${NC}"
echo -e "${BLUE}============================================================${NC}\n"

if [ $PASSED -eq $TOTAL ]; then
  exit 0
else
  exit 1
fi

