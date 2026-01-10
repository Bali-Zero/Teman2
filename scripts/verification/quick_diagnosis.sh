#!/bin/bash
# Quick Diagnosis Script - Verifica rapida stato sistema
# Esegui: bash scripts/verification/quick_diagnosis.sh

echo "======================================================================"
echo "QUICK DIAGNOSIS - DASHBOARD ZANTARA"
echo "======================================================================"
echo "Data: $(date)"
echo "======================================================================"
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BACKEND_URL="https://nuzantara-rag.fly.dev"
FRONTEND_URL="https://zantara.balizero.com"

# Test 1: Backend Health
echo "======================================================================"
echo "1. BACKEND HEALTH CHECK"
echo "======================================================================"
echo ""

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Backend raggiungibile (HTTP $HTTP_CODE)${NC}"
    HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health" 2>/dev/null)
    echo "Response: $HEALTH_RESPONSE" | head -3
else
    echo -e "${RED}❌ Backend NON raggiungibile (HTTP $HTTP_CODE)${NC}"
fi

echo ""

# Test 2: Frontend Reachability
echo "======================================================================"
echo "2. FRONTEND REACHABILITY"
echo "======================================================================"
echo ""

FRONTEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" 2>/dev/null)

if [ "$FRONTEND_CODE" = "200" ] || [ "$FRONTEND_CODE" = "301" ] || [ "$FRONTEND_CODE" = "302" ]; then
    echo -e "${GREEN}✅ Frontend raggiungibile (HTTP $FRONTEND_CODE)${NC}"
else
    echo -e "${RED}❌ Frontend NON raggiungibile (HTTP $FRONTEND_CODE)${NC}"
fi

echo ""

# Test 3: CORS Preflight
echo "======================================================================"
echo "3. CORS PREFLIGHT TEST"
echo "======================================================================"
echo ""

CORS_RESPONSE=$(curl -s -i -X OPTIONS \
  -H "Origin: $FRONTEND_URL" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type" \
  "$BACKEND_URL/api/crm/clients" 2>&1)

if echo "$CORS_RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
    ALLOW_ORIGIN=$(echo "$CORS_RESPONSE" | grep -i "Access-Control-Allow-Origin" | head -1 | tr -d '\r')
    echo -e "${GREEN}✅ CORS header presente:${NC}"
    echo "   $ALLOW_ORIGIN"
    
    if echo "$ALLOW_ORIGIN" | grep -q "$FRONTEND_URL" || echo "$ALLOW_ORIGIN" | grep -q "\\*"; then
        echo -e "${GREEN}✅ Origin consentito${NC}"
    else
        echo -e "${YELLOW}⚠️  Origin potrebbe non essere esplicitamente consentito${NC}"
    fi
else
    echo -e "${RED}❌ CORS header NON presente${NC}"
fi

if echo "$CORS_RESPONSE" | grep -q "Access-Control-Allow-Credentials"; then
    echo -e "${GREEN}✅ Access-Control-Allow-Credentials presente${NC}"
else
    echo -e "${YELLOW}⚠️  Access-Control-Allow-Credentials NON presente${NC}"
fi

echo ""

# Test 4: API Endpoint (senza auth - dovrebbe dare 401)
echo "======================================================================"
echo "4. API ENDPOINT TEST (senza autenticazione)"
echo "======================================================================"
echo ""

API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Origin: $FRONTEND_URL" \
  "$BACKEND_URL/api/crm/clients" 2>/dev/null)

if [ "$API_RESPONSE" = "401" ] || [ "$API_RESPONSE" = "403" ]; then
    echo -e "${GREEN}✅ API endpoint risponde correttamente (HTTP $API_RESPONSE - atteso senza auth)${NC}"
elif [ "$API_RESPONSE" = "200" ]; then
    echo -e "${YELLOW}⚠️  API endpoint restituisce 200 senza auth (possibile problema sicurezza)${NC}"
else
    echo -e "${YELLOW}⚠️  API endpoint risponde con HTTP $API_RESPONSE${NC}"
fi

echo ""

# Test 5: Proxy Route (se possibile)
echo "======================================================================"
echo "5. PROXY ROUTE TEST"
echo "======================================================================"
echo ""

PROXY_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "$FRONTEND_URL/api/health" 2>/dev/null)

if [ "$PROXY_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ Proxy route funziona (HTTP $PROXY_RESPONSE)${NC}"
elif [ "$PROXY_RESPONSE" = "404" ]; then
    echo -e "${YELLOW}⚠️  Proxy route non trovato (HTTP 404)${NC}"
    echo "   (Potrebbe essere normale se /api/health non esiste)"
else
    echo -e "${YELLOW}⚠️  Proxy route risponde con HTTP $PROXY_RESPONSE${NC}"
fi

echo ""

# Riepilogo
echo "======================================================================"
echo "RIEPILOGO"
echo "======================================================================"
echo ""

ISSUES=0

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ Backend non raggiungibile${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [ "$FRONTEND_CODE" != "200" ] && [ "$FRONTEND_CODE" != "301" ] && [ "$FRONTEND_CODE" != "302" ]; then
    echo -e "${RED}❌ Frontend non raggiungibile${NC}"
    ISSUES=$((ISSUES + 1))
fi

if ! echo "$CORS_RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
    echo -e "${RED}❌ CORS non configurato correttamente${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ Tutti i test base sono passati${NC}"
    echo ""
    echo "Prossimi passi:"
    echo "  1. Verifica Vercel environment variables manualmente"
    echo "  2. Testa login e cookie nel browser"
    echo "  3. Controlla console browser per errori dettagliati"
else
    echo -e "${RED}⚠️  Trovati $ISSUES problema/i${NC}"
    echo ""
    echo "Risolvi i problemi sopra prima di procedere con le verifiche manuali."
fi

echo ""
echo "======================================================================"
echo "Per verifiche dettagliate:"
echo "  - CORS: bash scripts/verification/check_backend_cors.sh"
echo "  - Vercel: bash scripts/verification/check_vercel_env.sh"
echo "  - Login: vedi scripts/verification/test_login_cookies.md"
echo "======================================================================"
