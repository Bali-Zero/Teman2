#!/bin/bash
# Fix Telegram Chat ID - Helper Script
# Aiuta a ottenere e configurare un nuovo chat ID valido

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRAPER_DIR="$PROJECT_DIR/apps/bali-intel-scraper"
ENV_FILE="$SCRAPER_DIR/.env.local"

echo "🔧 Telegram Chat ID Fix Helper"
echo ""

# Verificare che .env.local esista
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ File .env.local non trovato: $ENV_FILE"
    exit 1
fi

# Caricare variabili
export $(grep -v '^#' "$ENV_FILE" | grep -E "TELEGRAM" | xargs)

# Verificare bot token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN non configurato"
    exit 1
fi

echo "✅ Bot token trovato"
echo ""

# Test bot
echo "🧪 Test bot..."
cd "$SCRAPER_DIR"
python3 scripts/test_telegram_bot.py

echo ""
echo "📋 PROSSIMI STEP:"
echo ""
echo "1. Se il test mostra 'user is deactivated':"
echo "   → Ottieni un nuovo chat ID valido"
echo ""
echo "2. Come ottenere chat ID:"
echo "   a) Invia un messaggio a @userinfobot su Telegram"
echo "   b) Oppure invia /start a @zantara_bot, poi:"
echo "      python3 scripts/get_telegram_chat_id.py"
echo ""
echo "3. Aggiorna .env.local:"
echo "   TELEGRAM_APPROVAL_CHAT_ID=NUOVO_CHAT_ID"
echo ""
echo "4. Testa di nuovo:"
echo "   python3 scripts/test_telegram_bot.py"
echo ""
