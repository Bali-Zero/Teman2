#!/usr/bin/env python3
"""
Script per testare il bot Telegram Zantara
Verifica che il bot risponda correttamente ai messaggi
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

BOT_TOKEN = "8295471667:AAHufchz_6zO5i8BitsUGNof5fVn8iMHHPE"
WEBHOOK_URL = "https://nuzantara-rag.fly.dev/api/telegram/webhook"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def test_bot_info():
    """Test 1: Verifica che il bot esista e sia attivo"""
    print("🧪 Test 1: Verifica informazioni bot...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/getMe")
            data = response.json()
            
            if data.get("ok"):
                bot_info = data["result"]
                print(f"✅ Bot trovato:")
                print(f"   Username: @{bot_info.get('username')}")
                print(f"   Nome: {bot_info.get('first_name')}")
                print(f"   ID: {bot_info.get('id')}")
                return True
            else:
                print(f"❌ Errore: {data.get('description')}")
                return False
        except Exception as e:
            print(f"❌ Errore connessione: {e}")
            return False


async def test_webhook_info():
    """Test 2: Verifica configurazione webhook"""
    print("\n🧪 Test 2: Verifica webhook...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE}/getWebhookInfo")
            data = response.json()
            
            if data.get("ok"):
                webhook_info = data["result"]
                url = webhook_info.get("url", "")
                pending = webhook_info.get("pending_update_count", 0)
                
                if url:
                    print(f"✅ Webhook configurato:")
                    print(f"   URL: {url}")
                    print(f"   Updates in attesa: {pending}")
                    
                    # Verifica che l'URL sia raggiungibile
                    if "nuzantara-rag.fly.dev" in url:
                        print("✅ URL webhook corretto")
                    else:
                        print("⚠️  URL webhook potrebbe non essere corretto")
                    
                    return True
                else:
                    print("❌ Webhook non configurato")
                    return False
            else:
                print(f"❌ Errore: {data.get('description')}")
                return False
        except Exception as e:
            print(f"❌ Errore connessione: {e}")
            return False


async def test_webhook_endpoint():
    """Test 3: Verifica che l'endpoint webhook sia raggiungibile"""
    print("\n🧪 Test 3: Verifica endpoint webhook...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Simula un update Telegram (messaggio di test)
            test_update = {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {
                        "id": 1125336968,
                        "is_bot": False,
                        "first_name": "Test",
                        "username": "test_user"
                    },
                    "chat": {
                        "id": 1125336968,
                        "type": "private"
                    },
                    "date": int(datetime.now().timestamp()),
                    "text": "/start"
                }
            }
            
            # Prova a raggiungere l'endpoint (potrebbe richiedere autenticazione)
            response = await client.post(
                WEBHOOK_URL,
                json=test_update,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Endpoint raggiungibile e risponde")
                return True
            elif response.status_code == 403:
                print("⚠️  Endpoint richiede autenticazione (normale se webhook secret è configurato)")
                return True  # Questo è normale se c'è un secret token
            elif response.status_code == 401:
                print("⚠️  Endpoint richiede autenticazione")
                return True
            else:
                print(f"⚠️  Risposta inaspettata: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except httpx.TimeoutException:
            print("❌ Timeout: endpoint non raggiungibile")
            return False
        except Exception as e:
            print(f"⚠️  Errore: {e}")
            return False


async def test_send_message(chat_id: str):
    """Test 4: Invia un messaggio di test al bot"""
    print(f"\n🧪 Test 4: Invio messaggio di test a chat {chat_id}...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "🧪 Test bot - Se ricevi questo messaggio, il bot funziona!",
                    "parse_mode": "Markdown"
                }
            )
            data = response.json()
            
            if data.get("ok"):
                print("✅ Messaggio inviato con successo!")
                print(f"   Message ID: {data['result'].get('message_id')}")
                return True
            else:
                error_code = data.get("error_code", "unknown")
                description = data.get("description", "Unknown error")
                print(f"❌ Errore invio messaggio:")
                print(f"   Code: {error_code}")
                print(f"   Description: {description}")
                
                if error_code == 403:
                    print("   💡 Suggerimento: Il bot potrebbe non essere avviato. Invia /start al bot prima.")
                elif error_code == 400:
                    print("   💡 Suggerimento: Chat ID potrebbe non essere valido")
                
                return False
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False


async def main():
    print("=" * 60)
    print("🤖 TEST BOT TELEGRAM ZANTARA")
    print("=" * 60)
    print(f"Bot Token: {BOT_TOKEN[:20]}...")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print("=" * 60)
    
    results = []
    
    # Test 1: Bot info
    results.append(await test_bot_info())
    
    # Test 2: Webhook info
    results.append(await test_webhook_info())
    
    # Test 3: Webhook endpoint
    results.append(await test_webhook_endpoint())
    
    # Test 4: Send message (opzionale, richiede chat_id)
    if len(sys.argv) > 1:
        chat_id = sys.argv[1]
        results.append(await test_send_message(chat_id))
    else:
        print("\n💡 Per testare l'invio di messaggi, esegui:")
        print(f"   python3 {sys.argv[0]} <chat_id>")
        print(f"   Esempio: python3 {sys.argv[0]} 1125336968")
    
    # Riepilogo
    print("\n" + "=" * 60)
    print("📊 RIEPILOGO TEST")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Test passati: {passed}/{total}")
    
    if passed == total:
        print("✅ Tutti i test sono passati!")
        return 0
    else:
        print("⚠️  Alcuni test non sono passati")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
