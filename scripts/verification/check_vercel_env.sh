#!/bin/bash
# Script per verificare configurazione Vercel Environment Variables
# Esegui: bash scripts/verification/check_vercel_env.sh

echo "======================================================================"
echo "VERIFICA CONFIGURAZIONE VERCEL ENVIRONMENT VARIABLES"
echo "======================================================================"
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📋 ISTRUZIONI PER VERIFICA MANUALE:"
echo ""
echo "1. Accedi a Vercel Dashboard: https://vercel.com/dashboard"
echo "2. Seleziona il progetto: nuzantara-mouth"
echo "3. Vai su: Settings → Environment Variables"
echo ""
echo "======================================================================"
echo "VARIABILI RICHIESTE:"
echo "======================================================================"
echo ""
echo "✅ NUZANTARA_API_URL"
echo "   Valore atteso: https://nuzantara-rag.fly.dev"
echo "   Ambiente: Production, Preview, Development"
echo ""
echo "✅ NEXT_PUBLIC_API_URL"
echo "   Valore atteso: https://nuzantara-rag.fly.dev"
echo "   Ambiente: Production, Preview, Development"
echo ""
echo "======================================================================"
echo "VERIFICA AUTOMATICA (se Vercel CLI installato):"
echo "======================================================================"
echo ""

if command -v vercel &> /dev/null; then
    echo "✅ Vercel CLI trovato"
    echo ""
    echo "Esegui manualmente:"
    echo "  vercel env ls"
    echo ""
    echo "Cerca queste variabili:"
    echo "  - NUZANTARA_API_URL"
    echo "  - NEXT_PUBLIC_API_URL"
else
    echo "⚠️  Vercel CLI non installato"
    echo ""
    echo "Installa con:"
    echo "  npm i -g vercel"
    echo ""
    echo "Oppure verifica manualmente dal dashboard web"
fi

echo ""
echo "======================================================================"
echo "TEST CONNETTIVITÀ BACKEND:"
echo "======================================================================"
echo ""

BACKEND_URL="https://nuzantara-rag.fly.dev"

echo "Testando: $BACKEND_URL/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Backend raggiungibile (HTTP $HTTP_CODE)${NC}"
    echo ""
    echo "Response:"
    curl -s "$BACKEND_URL/health" | head -5
else
    echo -e "${RED}❌ Backend NON raggiungibile (HTTP $HTTP_CODE)${NC}"
fi

echo ""
echo ""
echo "======================================================================"
echo "PROSSIMI PASSI:"
echo "======================================================================"
echo ""
echo "1. Se le variabili MANCANO su Vercel:"
echo "   → Aggiungile dal dashboard"
echo "   → Redeploya il progetto"
echo ""
echo "2. Se le variabili SONO PRESENTI ma il problema persiste:"
echo "   → Verifica che siano impostate per 'Production' environment"
echo "   → Controlla che il valore sia esattamente: https://nuzantara-rag.fly.dev"
echo "   → Verifica che non ci siano spazi o caratteri extra"
echo ""
echo "3. Dopo aver aggiunto/modificato le variabili:"
echo "   → Vai su Deployments"
echo "   → Clicca 'Redeploy' sull'ultimo deployment"
echo ""
echo "======================================================================"
