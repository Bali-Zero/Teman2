#!/bin/bash
# Login
echo "Attempting login..."
LOGIN_RESP=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}')

# Extract token (simple grep/cut for portability)
TOKEN=$(echo $LOGIN_RESP | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "Login failed. Response:"
  echo $LOGIN_RESP
  exit 1
fi

echo "Login successful! Token acquired."

echo "RAW_TOKEN:$TOKEN"

# Chat Stream
echo "Sending chat query requiring TOOL (KBLI Search)..."
curl -N -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"Qual è il KBLI per un ristorante?","user_id":"zero@balizero.com","enable_vision":false}'

