#!/bin/bash
# Script di test per verificare che manual_trigger.sh funzioni correttamente

echo "🧪 Test Manual Trigger Script"
echo "=============================="
echo ""

# Verifica che il token sia configurato
echo "1️⃣ Verifica token Telegram su Fly.io..."
TOKEN_CHECK=$(fly secrets list --app nuzantara-rag | grep TELEGRAM_BOT_TOKEN)
if [ -n "$TOKEN_CHECK" ]; then
    echo "✅ Token configurato"
else
    echo "❌ Token non trovato"
    exit 1
fi

# Verifica che il bot funzioni
echo ""
echo "2️⃣ Verifica bot Telegram..."
BOT_INFO=$(curl -s "https://api.telegram.org/bot8295471667:AAHglwz8p8LxFnDgctmXuCs5aZa6lY78QO8/getMe")
if echo "$BOT_INFO" | grep -q '"ok":true'; then
    BOT_USERNAME=$(echo "$BOT_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('username', 'N/A'))" 2>/dev/null)
    echo "✅ Bot attivo: @$BOT_USERNAME"
else
    echo "❌ Bot non valido"
    exit 1
fi

# Verifica webhook
echo ""
echo "3️⃣ Verifica webhook..."
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot8295471667:AAHglwz8p8LxFnDgctmXuCs5aZa6lY78QO8/getWebhookInfo")
if echo "$WEBHOOK_INFO" | grep -q '"url"'; then
    WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['result'].get('url', 'N/A'))" 2>/dev/null)
    echo "✅ Webhook configurato: $WEBHOOK_URL"
else
    echo "⚠️  Webhook non configurato"
fi

# Verifica chat ID nello script
echo ""
echo "4️⃣ Verifica chat ID nello script..."
CHAT_ID=$(grep "TELEGRAM_ADMIN_CHAT_ID" scripts/automation/manual_trigger.sh | grep -oE "[0-9]+" | head -1)
if [ -n "$CHAT_ID" ]; then
    echo "✅ Chat ID configurato: $CHAT_ID"
else
    echo "❌ Chat ID non trovato nello script"
    exit 1
fi

echo ""
echo "=============================="
echo "✅ Tutti i controlli passati!"
echo ""
echo "💡 Per eseguire il report:"
echo "   ./scripts/automation/manual_trigger.sh"
echo ""
echo "⚠️  Nota: Assicurati che il chat ID $CHAT_ID abbia avviato"
echo "   una conversazione con @Balizerobot su Telegram (/start)"
