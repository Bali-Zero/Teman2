#!/bin/bash
# Script per verificare configurazione CORS backend
# Esegui: bash scripts/verification/check_backend_cors.sh

echo "======================================================================"
echo "VERIFICA CONFIGURAZIONE CORS BACKEND"
echo "======================================================================"
echo ""

BACKEND_URL="https://nuzantara-rag.fly.dev"
FRONTEND_ORIGIN="https://zantara.balizero.com"

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Testing CORS configuration for:"
echo "  Backend: $BACKEND_URL"
echo "  Frontend Origin: $FRONTEND_ORIGIN"
echo ""

# Test OPTIONS request (preflight)
echo "======================================================================"
echo "1. TEST PREFLIGHT (OPTIONS) REQUEST"
echo "======================================================================"
echo ""

RESPONSE=$(curl -s -i -X OPTIONS \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type" \
  "$BACKEND_URL/api/crm/clients" 2>&1)

echo "$RESPONSE" | head -20
echo ""

# Check for CORS headers
if echo "$RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
    ALLOW_ORIGIN=$(echo "$RESPONSE" | grep -i "Access-Control-Allow-Origin" | head -1)
    echo -e "${GREEN}✅ Access-Control-Allow-Origin header found:${NC}"
    echo "   $ALLOW_ORIGIN"
    
    if echo "$ALLOW_ORIGIN" | grep -q "$FRONTEND_ORIGIN"; then
        echo -e "${GREEN}✅ Origin $FRONTEND_ORIGIN is allowed${NC}"
    else
        echo -e "${YELLOW}⚠️  Origin $FRONTEND_ORIGIN may not be explicitly allowed${NC}"
        echo "   (Check if wildcard '*' is used or if origin is in allowed list)"
    fi
else
    echo -e "${RED}❌ Access-Control-Allow-Origin header NOT found${NC}"
fi

if echo "$RESPONSE" | grep -q "Access-Control-Allow-Credentials"; then
    ALLOW_CREDENTIALS=$(echo "$RESPONSE" | grep -i "Access-Control-Allow-Credentials" | head -1)
    echo -e "${GREEN}✅ Access-Control-Allow-Credentials header found:${NC}"
    echo "   $ALLOW_CREDENTIALS"
else
    echo -e "${YELLOW}⚠️  Access-Control-Allow-Credentials header NOT found${NC}"
    echo "   (May be required for cookie-based authentication)"
fi

if echo "$RESPONSE" | grep -q "Access-Control-Allow-Methods"; then
    ALLOW_METHODS=$(echo "$RESPONSE" | grep -i "Access-Control-Allow-Methods" | head -1)
    echo -e "${GREEN}✅ Access-Control-Allow-Methods header found:${NC}"
    echo "   $ALLOW_METHODS"
else
    echo -e "${YELLOW}⚠️  Access-Control-Allow-Methods header NOT found${NC}"
fi

echo ""
echo "======================================================================"
echo "2. TEST ACTUAL GET REQUEST"
echo "======================================================================"
echo ""

GET_RESPONSE=$(curl -s -i \
  -H "Origin: $FRONTEND_ORIGIN" \
  "$BACKEND_URL/api/crm/clients" 2>&1)

HTTP_CODE=$(echo "$GET_RESPONSE" | head -1 | grep -oE '[0-9]{3}' | head -1)

echo "HTTP Status: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✅ Request succeeded (HTTP $HTTP_CODE)${NC}"
    echo ""
    if echo "$GET_RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
        CORS_ORIGIN=$(echo "$GET_RESPONSE" | grep -i "Access-Control-Allow-Origin" | head -1)
        echo -e "${GREEN}✅ CORS headers present in actual response:${NC}"
        echo "   $CORS_ORIGIN"
    else
        echo -e "${YELLOW}⚠️  CORS headers missing in actual response${NC}"
    fi
else
    echo -e "${RED}❌ Request failed (HTTP $HTTP_CODE)${NC}"
fi

echo ""
echo "======================================================================"
echo "3. VERIFICA CONFIGURAZIONE FLY.IO"
echo "======================================================================"
echo ""

if command -v fly &> /dev/null; then
    echo "✅ Fly CLI trovato"
    echo ""
    echo "Per verificare secrets:"
    echo "  fly secrets list -a nuzantara-rag"
    echo ""
    echo "Per impostare ZANTARA_ALLOWED_ORIGINS:"
    echo "  fly secrets set ZANTARA_ALLOWED_ORIGINS=\"https://zantara.balizero.com,https://www.zantara.balizero.com\" -a nuzantara-rag"
else
    echo "⚠️  Fly CLI non installato"
    echo ""
    echo "Installa con:"
    echo "  curl -L https://fly.io/install.sh | sh"
fi

echo ""
echo "======================================================================"
echo "4. VERIFICA FILE CORS CONFIG"
echo "======================================================================"
echo ""

CORS_FILE="apps/backend-rag/backend/app/setup/cors_config.py"

if [ -f "$CORS_FILE" ]; then
    echo "✅ File CORS config trovato: $CORS_FILE"
    echo ""
    echo "Verifica che contenga:"
    echo "  - 'https://zantara.balizero.com' in default_origins"
    echo ""
    echo "Contenuto rilevante:"
    grep -A 10 "default_origins" "$CORS_FILE" | head -15
else
    echo -e "${RED}❌ File CORS config NON trovato: $CORS_FILE${NC}"
fi

echo ""
echo "======================================================================"
echo "RIEPILOGO"
echo "======================================================================"
echo ""
echo "✅ Se tutti i test sono passati:"
echo "   - CORS è configurato correttamente"
echo "   - Il problema potrebbe essere altrove (auth, proxy, etc.)"
echo ""
echo "❌ Se i test falliscono:"
echo "   1. Verifica che il backend sia deployato con CORS config aggiornato"
echo "   2. Controlla che ZANTARA_ALLOWED_ORIGINS sia impostato su Fly.io"
echo "   3. Verifica che cors_config.py includa zantara.balizero.com"
echo "   4. Redeploy backend se necessario"
echo ""
echo "======================================================================"
