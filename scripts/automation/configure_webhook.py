#!/usr/bin/env python3
"""
Script per configurare il webhook Telegram con il secret token
Esegue sulla macchina Fly.io per accedere alle variabili d'ambiente
"""

import os
import asyncio
import httpx

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8295471667:AAHufchz_6zO5i8BitsUGNof5fVn8iMHHPE")
SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET")
WEBHOOK_URL = "https://nuzantara-rag.fly.dev/api/telegram/webhook"

async def configure_webhook():
    """Configura il webhook Telegram con il secret token"""
    print(f"🔧 Configurazione webhook Telegram...")
    print(f"   URL: {WEBHOOK_URL}")
    print(f"   Secret Token: {'***' if SECRET_TOKEN else 'NON CONFIGURATO'}")
    
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "edited_message", "callback_query"]
    }
    
    if SECRET_TOKEN:
        payload["secret_token"] = SECRET_TOKEN
        print("✅ Secret token incluso")
    else:
        print("⚠️  Secret token non trovato nelle variabili d'ambiente")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json=payload
            )
            result = response.json()
            
            if result.get("ok"):
                print("✅ Webhook configurato con successo!")
                
                # Verifica configurazione
                verify_response = await client.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
                )
                verify_result = verify_response.json()
                
                if verify_result.get("ok"):
                    webhook_info = verify_result["result"]
                    print(f"\n📊 Stato webhook:")
                    print(f"   URL: {webhook_info.get('url')}")
                    print(f"   Updates in attesa: {webhook_info.get('pending_update_count', 0)}")
                    if webhook_info.get('last_error_message'):
                        print(f"   ⚠️  Ultimo errore: {webhook_info.get('last_error_message')}")
                
                return True
            else:
                print(f"❌ Errore: {result.get('description')}")
                return False
                
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(configure_webhook())
    exit(0 if success else 1)
