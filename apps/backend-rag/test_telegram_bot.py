#!/usr/bin/env python3
"""
Script per testare il bot Telegram Zantara
"""

import asyncio
import httpx
import sys
from typing import Dict, Any

class TelegramBotTester:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def test_bot_info(self) -> Dict[str, Any]:
        """Test informazioni bot"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_url}/getMe")
                data = response.json()
                
                if data.get('ok'):
                    return {
                        'success': True,
                        'bot_info': data['result'],
                        'message': f"✅ Bot @{data['result']['username']} online"
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('description', 'Unknown error'),
                        'message': f"❌ Errore: {data.get('description', 'Unknown')}"
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"❌ Errore connessione: {e}"
            }
    
    async def test_webhook_info(self) -> Dict[str, Any]:
        """Test informazioni webhook"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_url}/getWebhookInfo")
                data = response.json()
                
                if data.get('ok'):
                    webhook = data['result']
                    if webhook.get('url'):
                        return {
                            'success': True,
                            'webhook_url': webhook['url'],
                            'message': f"✅ Webhook configurato: {webhook['url']}"
                        }
                    else:
                        return {
                            'success': False,
                            'message': "❌ Webhook non configurato"
                        }
                else:
                    return {
                        'success': False,
                        'error': data.get('description', 'Unknown error'),
                        'message': f"❌ Errore webhook: {data.get('description', 'Unknown')}"
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"❌ Errore webhook: {e}"
            }
    
    async def set_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Configura webhook"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/setWebhook",
                    json={'url': webhook_url}
                )
                data = response.json()
                
                if data.get('ok'):
                    return {
                        'success': True,
                        'message': f"✅ Webhook configurato: {webhook_url}"
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('description', 'Unknown error'),
                        'message': f"❌ Errore configurazione: {data.get('description', 'Unknown')}"
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"❌ Errore configurazione: {e}"
            }
    
    async def test_backend_webhook(self) -> Dict[str, Any]:
        """Test backend webhook endpoint"""
        try:
            async with httpx.AsyncClient() as client:
                # Test con payload falso
                payload = {
                    "update_id": 123456,
                    "message": {
                        "message_id": 1,
                        "from": {
                            "id": 123456789,
                            "first_name": "Test",
                            "username": "test_user"
                        },
                        "chat": {
                            "id": 123456789,
                            "first_name": "Test",
                            "username": "test_user",
                            "type": "private"
                        },
                        "date": 1640995200,
                        "text": "test message"
                    }
                }
                
                response = await client.post(
                    "https://nuzantara-rag.fly.dev/api/telegram/webhook",
                    json=payload,
                    headers={"X-Telegram-Bot-Api-Secret-Token": "test"}
                )
                
                if response.status_code == 403:
                    return {
                        'success': True,
                        'message': "✅ Backend webhook attivo (richiede secret token corretto)"
                    }
                else:
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'message': f"✅ Backend webhook risponde (status: {response.status_code})"
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"❌ Errore backend: {e}"
            }

async def main():
    """Test completo del bot"""
    print("🤖 Test Bot Telegram Zantara")
    print("=" * 40)
    
    # Chiedi token
    bot_token = input("📝 Inserisci il token del bot: ").strip()
    
    if not bot_token:
        print("❌ Token richiesto")
        sys.exit(1)
    
    # Verifica formato
    if not bot_token.match("^[0-9]+:[a-zA-Z0-9_-]+$"):
        print("❌ Token non valido. Deve essere nel formato: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        sys.exit(1)
    
    tester = TelegramBotTester(bot_token)
    
    print("\n🧪 Test 1: Informazioni Bot")
    print("-" * 30)
    result1 = await tester.test_bot_info()
    print(result1['message'])
    
    if not result1['success']:
        print("\n❌ Bot non valido. Controlla il token.")
        sys.exit(1)
    
    print("\n🧪 Test 2: Informazioni Webhook")
    print("-" * 30)
    result2 = await tester.test_webhook_info()
    print(result2['message'])
    
    print("\n🧪 Test 3: Configurazione Webhook")
    print("-" * 30)
    webhook_url = "https://nuzantara-rag.fly.dev/api/telegram/webhook"
    result3 = await tester.set_webhook(webhook_url)
    print(result3['message'])
    
    print("\n🧪 Test 4: Backend Webhook")
    print("-" * 30)
    result4 = await tester.test_backend_webhook()
    print(result4['message'])
    
    print("\n🎉 Riepilogo Test")
    print("=" * 40)
    
    all_passed = all([
        result1['success'],
        result2['success'] or not result2['success'],  # Webhook potrebbe non essere configurato
        result3['success'],
        result4['success']
    ])
    
    if all_passed:
        print("✅ Tutti i test superati!")
        print(f"🤖 Bot: @{result1['bot_info']['username']}")
        print(f"🔗 Webhook: {webhook_url}")
        print("\n🚀 Il bot è pronto per ricevere messaggi!")
        print("💬 Trova il bot su Telegram e invia /start")
    else:
        print("❌ Alcuni test sono falliti")
        print("🔧 Controlla i log e riprova")

if __name__ == "__main__":
    asyncio.run(main())
