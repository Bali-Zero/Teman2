#!/bin/bash
# Script per verificare lo stato del bot Telegram Zantara

echo "🔍 Verifica Bot Telegram Zantara"
echo "=================================="

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verifica se il token è configurato su Fly.io
echo "📋 Verifica secrets su Fly.io..."
TELEGRAM_SECRETS=$(fly secrets list --app nuzantara-rag 2>/dev/null | grep -i telegram || echo "")

if [ -z "$TELEGRAM_SECRETS" ]; then
    echo -e "${RED}❌ Nessun secret Telegram trovato su Fly.io${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Secrets Telegram trovati su Fly.io${NC}"
echo "$TELEGRAM_SECRETS"

# 2. Chiedi il token per verificare direttamente con Telegram API
echo ""
echo "🔑 Per verificare lo stato del bot, inserisci il token Telegram:"
echo "   (Puoi ottenerlo da @BotFather su Telegram)"
read -r BOT_TOKEN

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}❌ Token non fornito${NC}"
    exit 1
fi

# Verifica formato token
if [[ ! $BOT_TOKEN =~ ^[0-9]+:[a-zA-Z0-9_-]+$ ]]; then
    echo -e "${RED}❌ Formato token non valido!${NC}"
    echo "   Formato atteso: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    exit 1
fi

echo ""
echo "🧪 Verifica bot con Telegram API..."

# Verifica bot info
BOT_INFO=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe")

if echo "$BOT_INFO" | grep -q '"ok":true'; then
    BOT_USERNAME=$(echo "$BOT_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('username', 'N/A'))" 2>/dev/null)
    BOT_NAME=$(echo "$BOT_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('first_name', 'N/A'))" 2>/dev/null)
    BOT_ID=$(echo "$BOT_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('id', 'N/A'))" 2>/dev/null)
    
    echo -e "${GREEN}✅ Bot trovato e attivo!${NC}"
    echo "   Username: @${BOT_USERNAME}"
    echo "   Nome: ${BOT_NAME}"
    echo "   ID: ${BOT_ID}"
    
    # Verifica webhook
    echo ""
    echo "🔗 Verifica webhook..."
    WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
    
    if echo "$WEBHOOK_INFO" | grep -q '"url":""'; then
        echo -e "${YELLOW}⚠️  Webhook non configurato${NC}"
        echo ""
        echo "Vuoi configurare il webhook ora? (y/n)"
        read -r SETUP_WEBHOOK
        
        if [ "$SETUP_WEBHOOK" = "y" ]; then
            WEBHOOK_URL="https://nuzantara-rag.fly.dev/api/telegram/webhook"
            echo "Configurazione webhook: ${WEBHOOK_URL}..."
            
            WEBHOOK_RESULT=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
                -H "Content-Type: application/json" \
                -d "{\"url\": \"${WEBHOOK_URL}\"}")
            
            if echo "$WEBHOOK_RESULT" | grep -q '"ok":true'; then
                echo -e "${GREEN}✅ Webhook configurato con successo!${NC}"
            else
                echo -e "${RED}❌ Errore nella configurazione del webhook${NC}"
                echo "$WEBHOOK_RESULT"
            fi
        fi
    else
        WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('url', 'N/A'))" 2>/dev/null)
        echo -e "${GREEN}✅ Webhook configurato: ${WEBHOOK_URL}${NC}"
    fi
    
else
    ERROR_MSG=$(echo "$BOT_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('description', 'Errore sconosciuto'))" 2>/dev/null)
    echo -e "${RED}❌ Bot non trovato o token non valido${NC}"
    echo "   Errore: ${ERROR_MSG}"
    echo ""
    echo "Possibili cause:"
    echo "1. Il bot è stato eliminato su Telegram"
    echo "2. Il token non è più valido"
    echo "3. Il token è errato"
    echo ""
    echo "Soluzione:"
    echo "1. Apri Telegram e cerca @BotFather"
    echo "2. Invia /mybots"
    echo "3. Verifica se @Balizerobot esiste ancora"
    echo "4. Se non esiste, crea un nuovo bot con /newbot"
    echo "5. Copia il nuovo token e aggiornalo su Fly.io:"
    echo "   fly secrets set TELEGRAM_BOT_TOKEN=\"NUOVO_TOKEN\" --app nuzantara-rag"
    exit 1
fi

echo ""
echo "✅ Verifica completata!"
