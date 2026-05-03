#!/bin/bash
# Script per configurare Telegram Bot

echo "🤖 Configurazione Bot Telegram per Zantara"
echo "=========================================="

# 1. Inserisci il tuo token reale da @BotFather
echo "📝 Incolla qui il tuo token Bot (formato: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz):"
read -r BOT_TOKEN

# Verifica formato token
if [[ ! $BOT_TOKEN =~ ^[0-9]+:[a-zA-Z0-9_-]+$ ]]; then
    echo "❌ Token non valido! Deve essere nel formato: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    exit 1
fi

echo "✅ Token formato valido"

# 2. Configura su Fly.io
echo "🔧 Configurazione token su Fly.io..."
fly secrets set TELEGRAM_BOT_TOKEN="$BOT_TOKEN" --app nuzantara-rag

if [ $? -eq 0 ]; then
    echo "✅ Token configurato con successo"
else
    echo "❌ Errore nella configurazione del token"
    exit 1
fi

# 3. Test bot
echo "🧪 Test del bot..."
python3 -c "
import httpx
import asyncio

async def test_bot():
    try:
        api_url = f'https://api.telegram.org/bot$BOT_TOKEN/getMe'
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url)
            data = response.json()
            
            if data.get('ok'):
                bot_info = data['result']
                print(f'✅ Bot Online: @{bot_info.get(\"username\")}')
                print(f'🤖 Nome: {bot_info.get(\"first_name\")}')
                print(f'🆔 ID: {bot_info.get(\"id\")}')
                return True
            else:
                print(f'❌ Errore: {data.get(\"description\")}')
                return False
    except Exception as e:
        print(f'❌ Errore connessione: {e}')
        return False

result = asyncio.run(test_bot())
exit(0 if result else 1)
"

if [ $? -eq 0 ]; then
    echo "✅ Bot test superato"
else
    echo "❌ Bot test fallito"
    exit 1
fi

# 4. Configura webhook
echo "🔗 Configurazione webhook..."
WEBHOOK_URL="https://nuzantara-rag.fly.dev/api/telegram/webhook"

python3 -c "
import httpx
import asyncio

async def setup_webhook():
    try:
        api_url = f'https://api.telegram.org/bot$BOT_TOKEN/setWebhook'
        data = {'url': WEBHOOK_URL}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=data)
            result = response.json()
            
            if result.get('ok'):
                print(f'✅ Webhook configurato: {WEBHOOK_URL}')
                return True
            else:
                print(f'❌ Errore webhook: {result.get(\"description\")}')
                return False
    except Exception as e:
        print(f'❌ Errore configurazione webhook: {e}')
        return False

result = asyncio.run(setup_webhook())
exit(0 if result else 1)
"

if [ $? -eq 0 ]; then
    echo "✅ Webhook configurato"
else
    echo "❌ Errore configurazione webhook"
    exit 1
fi

echo ""
echo "🎉 BOT TELEGRAM CONFIGURATO CON SUCCESSO!"
echo "=========================================="
echo "🤖 Bot Username: @$BOT_USERNAME"
echo "🔗 Webhook: $WEBHOOK_URL"
echo "💬 Ora puoi inviare messaggi al bot su Telegram!"
echo ""
echo "📋 Prossimi passi:"
echo "1. Trova il tuo bot su Telegram"
echo "2. Invia /start per iniziare"
echo "3. Prova a fare una domanda"
echo "4. Il bot dovrebbe rispondere usando l'AI di Nuzantara"
