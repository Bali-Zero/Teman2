#!/bin/bash
# Script per configurare correttamente il webhook Telegram con secret token

BOT_TOKEN="8295471667:AAHufchz_6zO5i8BitsUGNof5fVn8iMHHPE"
WEBHOOK_URL="https://nuzantara-rag.fly.dev/api/telegram/webhook"

echo "🔧 Configurazione webhook Telegram con secret token"
echo "=================================================="
echo ""

# Opzione 1: Usa il secret token esistente da Fly.io
echo "📋 Opzione 1: Configurazione con secret token esistente"
echo "   (Il secret token verrà letto dalle variabili d'ambiente su Fly.io)"
echo ""
echo "💡 Per configurare il webhook correttamente:"
echo ""
echo "   1. Esegui questo comando sulla macchina Fly.io:"
echo "      fly ssh console --app nuzantara-rag"
echo ""
echo "   2. Poi esegui questo script Python:"
echo ""
cat << 'PYTHON_SCRIPT'
import os
import asyncio
import httpx

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET")
WEBHOOK_URL = "https://nuzantara-rag.fly.dev/api/telegram/webhook"

async def configure():
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "edited_message", "callback_query"]
    }
    if SECRET_TOKEN:
        payload["secret_token"] = SECRET_TOKEN
        print(f"✅ Secret token configurato: {SECRET_TOKEN[:10]}...")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json=payload
        )
        result = resp.json()
        if result.get("ok"):
            print("✅ Webhook configurato con successo!")
            verify = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
            info = verify.json().get("result", {})
            print(f"   URL: {info.get('url')}")
            print(f"   Updates in attesa: {info.get('pending_update_count', 0)}")
        else:
            print(f"❌ Errore: {result.get('description')}")

asyncio.run(configure())
PYTHON_SCRIPT

echo ""
echo "=================================================="
echo ""
echo "📊 Stato attuale webhook:"
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool | grep -E "url|pending_update_count|last_error"

echo ""
echo "💡 NOTA: Il webhook attualmente restituisce 403 perché il secret token"
echo "   non è configurato nel webhook di Telegram. Una volta configurato,"
echo "   gli updates in attesa verranno processati correttamente."
