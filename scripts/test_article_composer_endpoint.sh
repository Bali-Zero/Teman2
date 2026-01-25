#!/bin/bash
# Test manuale endpoint Article Composer

set -e

API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
ENDPOINT="${ENDPOINT:-/api/articles/compose}"
ADMIN_API_KEY="${ADMIN_API_KEY:-}"

echo "🧪 Test Manuale Article Composer Endpoint"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if API key is provided
if [ -z "$ADMIN_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  ADMIN_API_KEY non fornito${NC}"
    echo "   Usa: ADMIN_API_KEY=your_key $0"
    echo "   Oppure esporta: export ADMIN_API_KEY=your_key"
    echo ""
    echo "   Per ottenere la chiave:"
    echo "   fly secrets list -a nuzantara-rag | grep ADMIN_API_KEY"
    exit 1
fi

echo "✅ API Key fornita: ${ADMIN_API_KEY:0:10}..."
echo ""

# Test 1: Status endpoint
echo "1️⃣ Test Status Endpoint..."
STATUS_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "X-API-Key: $ADMIN_API_KEY" \
    "$API_URL/api/articles/compose/status")

HTTP_CODE=$(echo "$STATUS_RESPONSE" | tail -1)
BODY=$(echo "$STATUS_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Status endpoint OK${NC}"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    echo -e "${RED}❌ Status endpoint failed: HTTP $HTTP_CODE${NC}"
    echo "$BODY"
fi
echo ""

# Test 2: Compose endpoint
echo "2️⃣ Test Compose Endpoint..."
COMPOSE_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $ADMIN_API_KEY" \
    -d '{
        "title": "Test Article Deployment",
        "content": "This is a test article to verify deployment is working correctly. It contains enough words to pass validation and provide meaningful context for the AI to work with. The article discusses important topics related to business and technology in Indonesia.",
        "category": "business"
    }' \
    "$API_URL$ENDPOINT")

HTTP_CODE=$(echo "$COMPOSE_RESPONSE" | tail -1)
BODY=$(echo "$COMPOSE_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Compose endpoint OK${NC}"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    
    # Check if cached
    CACHED=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cached', False))" 2>/dev/null || echo "false")
    if [ "$CACHED" = "true" ]; then
        echo -e "${GREEN}✅ Cache hit!${NC}"
    else
        echo -e "${YELLOW}ℹ️  Cache miss (prima richiesta)${NC}"
    fi
else
    echo -e "${RED}❌ Compose endpoint failed: HTTP $HTTP_CODE${NC}"
    echo "$BODY"
fi
echo ""

# Test 3: Rate limiting (make 11 requests)
echo "3️⃣ Test Rate Limiting (11 richieste rapide)..."
RATE_LIMIT_COUNT=0
for i in {1..11}; do
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $ADMIN_API_KEY" \
        -d '{
            "title": "Rate Limit Test",
            "content": "Test content for rate limiting with enough words to pass validation.",
            "category": "business"
        }' \
        "$API_URL$ENDPOINT")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    
    if [ "$HTTP_CODE" = "429" ]; then
        RATE_LIMIT_COUNT=$((RATE_LIMIT_COUNT + 1))
        echo -e "${YELLOW}⚠️  Richiesta $i: Rate limited (429)${NC}"
    elif [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Richiesta $i: OK${NC}"
    else
        echo -e "${RED}❌ Richiesta $i: HTTP $HTTP_CODE${NC}"
    fi
    
    # Small delay to avoid overwhelming
    sleep 0.5
done

if [ "$RATE_LIMIT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Rate limiting funziona! ($RATE_LIMIT_COUNT richieste limitate)${NC}"
else
    echo -e "${YELLOW}⚠️  Rate limiting non attivato (potrebbe essere normale se le richieste sono troppo lente)${NC}"
fi
echo ""

# Test 4: Cache test (second request should be cached)
echo "4️⃣ Test Caching (seconda richiesta identica)..."
FIRST_START=$(date +%s%N)
FIRST_RESPONSE=$(curl -s \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $ADMIN_API_KEY" \
    -d '{
        "title": "Cache Test Article",
        "content": "This article tests caching functionality with enough content to pass validation.",
        "category": "business"
    }' \
    "$API_URL$ENDPOINT")
FIRST_END=$(date +%s%N)
FIRST_TIME=$((($FIRST_END - $FIRST_START) / 1000000))

sleep 1

SECOND_START=$(date +%s%N)
SECOND_RESPONSE=$(curl -s \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $ADMIN_API_KEY" \
    -d '{
        "title": "Cache Test Article",
        "content": "This article tests caching functionality with enough content to pass validation.",
        "category": "business"
    }' \
    "$API_URL$ENDPOINT")
SECOND_END=$(date +%s%N)
SECOND_TIME=$((($SECOND_END - $SECOND_START) / 1000000))

FIRST_CACHED=$(echo "$FIRST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cached', False))" 2>/dev/null || echo "false")
SECOND_CACHED=$(echo "$SECOND_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cached', False))" 2>/dev/null || echo "false")

echo "   Prima richiesta: ${FIRST_TIME}ms, cached: $FIRST_CACHED"
echo "   Seconda richiesta: ${SECOND_TIME}ms, cached: $SECOND_CACHED"

if [ "$SECOND_CACHED" = "true" ]; then
    echo -e "${GREEN}✅ Cache funziona! Seconda richiesta è cached${NC}"
    if [ "$SECOND_TIME" -lt "$FIRST_TIME" ]; then
        SPEEDUP=$(echo "scale=2; $FIRST_TIME / $SECOND_TIME" | bc)
        echo -e "${GREEN}   Speedup: ${SPEEDUP}x più veloce${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Cache non attivo o Redis non configurato${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}✅ Test completati!${NC}"
echo ""
echo "Per monitorare le metriche:"
echo "  curl $API_URL/metrics | grep article_compose"
echo ""
echo "Per vedere i log:"
echo "  fly logs -a nuzantara-rag | grep article_composer"
