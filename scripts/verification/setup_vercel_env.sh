#!/bin/bash
# Script per configurare Vercel Environment Variables
# Esegui: bash scripts/verification/setup_vercel_env.sh

echo "======================================================================"
echo "CONFIGURAZIONE VERCEL ENVIRONMENT VARIABLES"
echo "======================================================================"
echo ""

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BACKEND_URL="https://nuzantara-rag.fly.dev"
PROJECT_NAME="nuzantara-mouth"

echo "Progetto: $PROJECT_NAME"
echo "Backend URL: $BACKEND_URL"
echo ""

# Verifica Vercel CLI
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}❌ Vercel CLI non trovato${NC}"
    echo ""
    echo "Installa con:"
    echo "  npm i -g vercel"
    echo ""
    echo "Oppure configura manualmente dal dashboard:"
    echo "  https://vercel.com/dashboard"
    echo ""
    echo "Vedi guida: scripts/verification/vercel_env_check.md"
    exit 1
fi

echo -e "${GREEN}✅ Vercel CLI trovato${NC}"
echo ""

# Verifica login
echo "Verificando login Vercel..."
if ! vercel whoami &> /dev/null; then
    echo -e "${YELLOW}⚠️  Non sei loggato in Vercel${NC}"
    echo ""
    echo "Esegui login con:"
    echo "  vercel login"
    echo ""
    exit 1
fi

USER=$(vercel whoami 2>/dev/null)
echo -e "${GREEN}✅ Loggato come: $USER${NC}"
echo ""

# Lista env vars esistenti
echo "======================================================================"
echo "ENVIRONMENT VARIABLES ESISTENTI"
echo "======================================================================"
echo ""

# Cerca directory mouth (potrebbe essere già nella directory corretta)
if [ -d "apps/mouth" ]; then
    cd apps/mouth
elif [ -d "../apps/mouth" ]; then
    cd ../apps/mouth
elif [ -f "package.json" ] && grep -q "next" package.json 2>/dev/null; then
    # Siamo già nella directory mouth
    echo "Directory corrente: $(pwd)"
else
    echo "⚠️  Directory apps/mouth non trovata, continuo dalla directory corrente"
fi

vercel env ls 2>/dev/null | head -20

echo ""
echo "======================================================================"
echo "VERIFICA VARIABILI RICHIESTE"
echo "======================================================================"
echo ""

# Verifica NUZANTARA_API_URL
ENV_LIST=$(vercel env ls 2>/dev/null)
NUZANTARA_EXISTS=$(echo "$ENV_LIST" | grep -c "NUZANTARA_API_URL" || echo "0")
if [ "$NUZANTARA_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✅ NUZANTARA_API_URL trovata${NC}"
    echo "$ENV_LIST" | grep "NUZANTARA_API_URL"
else
    echo -e "${RED}❌ NUZANTARA_API_URL NON trovata${NC}"
fi

echo ""

# Verifica NEXT_PUBLIC_API_URL
NEXT_PUBLIC_EXISTS=$(echo "$ENV_LIST" | grep -c "NEXT_PUBLIC_API_URL" || echo "0")
if [ "$NEXT_PUBLIC_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✅ NEXT_PUBLIC_API_URL trovata${NC}"
    echo "$ENV_LIST" | grep "NEXT_PUBLIC_API_URL"
else
    echo -e "${RED}❌ NEXT_PUBLIC_API_URL NON trovata${NC}"
fi

echo ""

# Se mancano, aggiungi automaticamente
if [ "$NUZANTARA_EXISTS" -eq 0 ] || [ "$NEXT_PUBLIC_EXISTS" -eq 0 ]; then
    echo "======================================================================"
    echo "CONFIGURAZIONE AUTOMATICA"
    echo "======================================================================"
    echo ""
    echo "Aggiungendo variabili mancanti..."
    echo ""
    
    # Aggiungi NUZANTARA_API_URL
    if [ "$NUZANTARA_EXISTS" -eq 0 ]; then
        echo "Aggiungendo NUZANTARA_API_URL per Production..."
        echo "$BACKEND_URL" | vercel env add NUZANTARA_API_URL production 2>&1 | grep -v "^$" || true
        echo "Aggiungendo NUZANTARA_API_URL per Preview..."
        echo "$BACKEND_URL" | vercel env add NUZANTARA_API_URL preview 2>&1 | grep -v "^$" || true
        echo "Aggiungendo NUZANTARA_API_URL per Development..."
        echo "$BACKEND_URL" | vercel env add NUZANTARA_API_URL development 2>&1 | grep -v "^$" || true
        echo -e "${GREEN}✅ NUZANTARA_API_URL aggiunta${NC}"
        echo ""
    fi
    
    # Aggiungi NEXT_PUBLIC_API_URL
    if [ "$NEXT_PUBLIC_EXISTS" -eq 0 ]; then
        echo "Aggiungendo NEXT_PUBLIC_API_URL per Production..."
        echo "$BACKEND_URL" | vercel env add NEXT_PUBLIC_API_URL production 2>&1 | grep -v "^$" || true
        echo "Aggiungendo NEXT_PUBLIC_API_URL per Preview..."
        echo "$BACKEND_URL" | vercel env add NEXT_PUBLIC_API_URL preview 2>&1 | grep -v "^$" || true
        echo "Aggiungendo NEXT_PUBLIC_API_URL per Development..."
        echo "$BACKEND_URL" | vercel env add NEXT_PUBLIC_API_URL development 2>&1 | grep -v "^$" || true
        echo -e "${GREEN}✅ NEXT_PUBLIC_API_URL aggiunta${NC}"
        echo ""
    fi
    
    echo "======================================================================"
    echo "✅ CONFIGURAZIONE COMPLETATA"
    echo "======================================================================"
    echo ""
    echo "⚠️  IMPORTANTE: Redeploya il progetto per applicare le modifiche"
    echo ""
    echo "Verifica variabili aggiunte:"
    vercel env ls 2>/dev/null | grep -E "NUZANTARA_API_URL|NEXT_PUBLIC_API_URL" || echo "Nessuna variabile trovata"
    echo ""
    echo "Opzioni per redeploy:"
    echo "  1. Redeploy manuale:"
    echo "     cd apps/mouth && vercel deploy --prod"
    echo ""
    echo "  2. Oppure dal dashboard Vercel:"
    echo "     Deployments → [Ultimo] → ⋯ → Redeploy"
    echo ""
    echo "  3. Oppure fai push di un commit (trigger automatico)"
    echo ""
else
    echo "======================================================================"
    echo "✅ TUTTE LE VARIABILI SONO PRESENTI"
    echo "======================================================================"
    echo ""
    echo "Verifica che i valori siano corretti:"
    echo "  - NUZANTARA_API_URL = $BACKEND_URL"
    echo "  - NEXT_PUBLIC_API_URL = $BACKEND_URL"
    echo ""
    echo "Se i valori sono diversi, aggiornali manualmente dal dashboard."
    echo ""
fi

echo "======================================================================"
