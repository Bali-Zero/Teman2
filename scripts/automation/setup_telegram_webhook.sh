#!/bin/bash
# Script per configurare il webhook Telegram con il secret token

BOT_TOKEN="8295471667:AAHufchz_6zO5i8BitsUGNof5fVn8iMHHPE"
WEBHOOK_URL="https://nuzantara-rag.fly.dev/api/telegram/webhook"

echo "🔧 Configurazione webhook Telegram con secret token..."
echo ""

# Recupera il secret token da Fly.io
echo "📋 Recupero secret token da Fly.io..."
SECRET_TOKEN=$(fly ssh console --app nuzantara-rag -C "echo \$TELEGRAM_WEBHOOK_SECRET" 2>/dev/null | tail -1 | tr -d '\r\n')

if [ -z "$SECRET_TOKEN" ] || [ "$SECRET_TOKEN" = "" ]; then
    echo "⚠️  Impossibile recuperare il secret token automaticamente"
    echo "💡 Inserisci manualmente il secret token (o lascia vuoto per continuare senza):"
    read -r SECRET_TOKEN
fi

# Prepara il payload
PAYLOAD="{\"url\": \"${WEBHOOK_URL}\", \"allowed_updates\": [\"message\", \"edited_message\", \"callback_query\"]}"

if [ -n "$SECRET_TOKEN" ] && [ "$SECRET_TOKEN" != "" ]; then
    PAYLOAD=$(echo "$PAYLOAD" | python3 -c "import sys, json; d=json.load(sys.stdin); d['secret_token']=sys.argv[1]; print(json.dumps(d))" "$SECRET_TOKEN")
    echo "✅ Secret token incluso nel payload"
else
    echo "⚠️  Configurazione webhook senza secret token"
fi

echo ""
echo "🔗 Configurazione webhook..."
RESULT=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

if echo "$RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); exit(0 if d.get('ok') else 1)" 2>/dev/null; then
    echo "✅ Webhook configurato con successo!"
    echo ""
    echo "📊 Verifica configurazione..."
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
else
    echo "❌ Errore nella configurazione del webhook:"
    echo "$RESULT" | python3 -m json.tool
    exit 1
fi
