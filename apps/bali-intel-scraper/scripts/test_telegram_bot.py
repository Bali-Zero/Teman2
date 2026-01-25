#!/usr/bin/env python3
"""
Test Telegram Bot Configuration
================================
Verifica che il bot Telegram sia configurato correttamente e possa inviare messaggi.
"""

import os
import asyncio
import aiohttp
from loguru import logger

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def test_bot_info(bot_token: str):
    """Test bot info endpoint"""
    url = TELEGRAM_API.format(token=bot_token, method="getMe")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    logger.success(f"✅ Bot attivo: @{bot_info.get('username')}")
                    logger.info(f"   Bot ID: {bot_info.get('id')}")
                    logger.info(f"   Nome: {bot_info.get('first_name')}")
                    return True
                else:
                    logger.error(f"❌ Bot API error: {data.get('description')}")
                    return False
            else:
                logger.error(f"❌ HTTP {resp.status}")
                return False


async def test_send_message(bot_token: str, chat_id: str):
    """Test invio messaggio a chat ID"""
    url = TELEGRAM_API.format(token=bot_token, method="sendMessage")

    payload = {
        "chat_id": chat_id,
        "text": "🧪 Test messaggio da Intel Scraper Bot\n\nSe ricevi questo messaggio, la configurazione è corretta! ✅",
        "parse_mode": "Markdown",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok"):
                    logger.success(
                        f"✅ Messaggio inviato con successo a chat ID {chat_id}"
                    )
                    logger.info(
                        f"   Message ID: {data.get('result', {}).get('message_id')}"
                    )
                    return True
                else:
                    error = data.get("description", "Unknown error")
                    error_code = data.get("error_code", 0)
                    logger.error(f"❌ Telegram API error: {error_code} - {error}")

                    if error_code == 403:
                        if "deactivated" in error.lower():
                            logger.error("   ⚠️  L'utente Telegram è DISATTIVATO")
                            logger.info(
                                "   💡 Soluzione: L'utente deve essere attivo e aver avviato il bot con /start"
                            )
                        elif "blocked" in error.lower():
                            logger.error("   ⚠️  Il bot è stato BLOCCATO dall'utente")
                            logger.info(
                                "   💡 Soluzione: L'utente deve sbloccare il bot"
                            )
                        else:
                            logger.error(
                                "   ⚠️  L'utente non può ricevere messaggi da questo bot"
                            )
                            logger.info(
                                "   💡 Soluzione: L'utente deve avviare il bot con /start"
                            )
                    elif error_code == 400:
                        logger.error("   ⚠️  Chat ID non valido")
                        logger.info(
                            "   💡 Soluzione: Verificare che il chat ID sia corretto"
                        )

                    return False
            else:
                text = await resp.text()
                logger.error(f"❌ HTTP {resp.status}: {text[:200]}")
                return False


async def get_chat_info(bot_token: str, chat_id: str):
    """Ottieni info sul chat"""
    url = TELEGRAM_API.format(token=bot_token, method="getChat")

    payload = {"chat_id": chat_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok"):
                    chat_info = data.get("result", {})
                    logger.info("📱 Chat Info:")
                    logger.info(f"   Tipo: {chat_info.get('type')}")
                    logger.info(
                        f"   Nome: {chat_info.get('first_name') or chat_info.get('title', 'N/A')}"
                    )
                    logger.info(f"   Username: @{chat_info.get('username', 'N/A')}")
                    return True
                else:
                    logger.warning(
                        f"⚠️  Non è possibile ottenere info sul chat: {data.get('description')}"
                    )
                    return False
            else:
                return False


async def main():
    """Test completo configurazione Telegram"""
    logger.info("=" * 70)
    logger.info("🧪 TEST CONFIGURAZIONE TELEGRAM BOT")
    logger.info("=" * 70)

    # 1. Verificare bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN non configurato")
        logger.info("   Configurare in .env.local:")
        logger.info("   TELEGRAM_BOT_TOKEN=your_bot_token")
        return

    logger.info(f"✅ Bot token trovato: {bot_token[:10]}...")

    # 2. Test bot info
    logger.info("\n1️⃣ Test Bot Info...")
    bot_ok = await test_bot_info(bot_token)
    if not bot_ok:
        logger.error("❌ Bot non valido o token errato")
        return

    # 3. Verificare chat IDs
    chat_ids_str = os.getenv("TELEGRAM_APPROVAL_CHAT_ID") or os.getenv(
        "TELEGRAM_CHAT_ID", ""
    )
    if not chat_ids_str:
        logger.error("❌ TELEGRAM_APPROVAL_CHAT_ID non configurato")
        logger.info("   Configurare in .env.local:")
        logger.info("   TELEGRAM_APPROVAL_CHAT_ID=your_chat_id")
        return

    chat_ids = [cid.strip() for cid in chat_ids_str.split(",") if cid.strip()]
    logger.info(f"✅ Trovati {len(chat_ids)} chat ID(s): {', '.join(chat_ids)}")

    # 4. Test ogni chat ID
    logger.info("\n2️⃣ Test Invio Messaggi...")
    all_ok = True

    for chat_id in chat_ids:
        logger.info(f"\n📱 Test chat ID: {chat_id}")

        # Prova a ottenere info sul chat
        await get_chat_info(bot_token, chat_id)

        # Test invio messaggio
        success = await test_send_message(bot_token, chat_id)
        if not success:
            all_ok = False

    # 5. Riepilogo
    logger.info("\n" + "=" * 70)
    if all_ok:
        logger.success("✅ TUTTI I TEST PASSATI!")
        logger.info("   Il bot Telegram è configurato correttamente.")
    else:
        logger.error("❌ ALCUNI TEST FALLITI")
        logger.info("\n💡 SOLUZIONI:")
        logger.info("   1. Verificare che l'utente Telegram sia ATTIVO")
        logger.info("   2. L'utente deve avviare il bot con /start")
        logger.info("   3. L'utente non deve aver bloccato il bot")
        logger.info("   4. Verificare che il chat ID sia corretto")
        logger.info("\n📱 Come ottenere il chat ID:")
        logger.info("   - Invia un messaggio a @userinfobot su Telegram")
        logger.info("   - Oppure inizia una chat con il bot e usa @JsonDumpBot")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
