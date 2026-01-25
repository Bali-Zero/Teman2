#!/usr/bin/env python3
"""
Get Telegram Chat ID
====================
Script per ottenere il proprio Telegram Chat ID.

Usage:
    python get_telegram_chat_id.py

Oppure:
    1. Invia un messaggio a @userinfobot su Telegram
    2. Oppure inizia una chat con il bot e usa @JsonDumpBot
"""

import os
import asyncio
import aiohttp
from loguru import logger

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def get_updates(bot_token: str):
    """Ottieni ultimi messaggi ricevuti dal bot"""
    url = TELEGRAM_API.format(token=bot_token, method="getUpdates")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        logger.info(
                            f"✅ Trovati {len(updates)} messaggio(i) recente(i)"
                        )
                        logger.info("\n📱 Chat IDs trovati:")

                        seen_chats = set()
                        for update in updates:
                            message = update.get("message", {})
                            chat = message.get("chat", {})
                            chat_id = str(chat.get("id"))

                            if chat_id and chat_id not in seen_chats:
                                seen_chats.add(chat_id)
                                chat_type = chat.get("type", "unknown")
                                first_name = chat.get("first_name", "")
                                username = chat.get("username", "")
                                title = chat.get("title", "")

                                logger.info(f"\n   Chat ID: {chat_id}")
                                logger.info(f"   Tipo: {chat_type}")
                                if first_name:
                                    logger.info(f"   Nome: {first_name}")
                                if username:
                                    logger.info(f"   Username: @{username}")
                                if title:
                                    logger.info(f"   Titolo: {title}")

                        if seen_chats:
                            logger.info(
                                "\n✅ Usa uno di questi chat IDs in TELEGRAM_APPROVAL_CHAT_ID"
                            )
                            logger.info(
                                f"   Esempio: TELEGRAM_APPROVAL_CHAT_ID={','.join(seen_chats)}"
                            )
                        else:
                            logger.warning("⚠️  Nessun chat ID trovato")
                            logger.info(
                                "   💡 Invia un messaggio al bot prima di eseguire questo script"
                            )
                    else:
                        logger.warning("⚠️  Nessun messaggio trovato")
                        logger.info(
                            "   💡 Invia un messaggio al bot prima di eseguire questo script"
                        )
                        logger.info(
                            "   💡 Oppure usa @userinfobot per ottenere il tuo chat ID"
                        )
                else:
                    error_desc = data.get("description", "")
                    if "webhook" in error_desc.lower():
                        logger.warning("⚠️  Webhook attivo - non posso usare getUpdates")
                        logger.info("   💡 Il bot ha un webhook configurato")
                        logger.info(
                            "   💡 Usa @userinfobot per ottenere il tuo chat ID:"
                        )
                        logger.info("      1. Apri Telegram")
                        logger.info("      2. Cerca @userinfobot")
                        logger.info("      3. Invia qualsiasi messaggio")
                        logger.info("      4. Copia il numero 'ID' dalla risposta")
                    else:
                        logger.error(f"❌ Bot API error: {error_desc}")
            else:
                text = await resp.text()
                try:
                    error_data = await resp.json()
                    if error_data.get("error_code") == 409:
                        logger.warning("⚠️  Webhook attivo - non posso usare getUpdates")
                        logger.info(
                            "   💡 Usa @userinfobot per ottenere il tuo chat ID"
                        )
                    else:
                        logger.error(f"❌ HTTP {resp.status}: {text[:200]}")
                except:
                    logger.error(f"❌ HTTP {resp.status}: {text[:200]}")


async def main():
    """Main function"""
    logger.info("=" * 70)
    logger.info("📱 OTTIENI TELEGRAM CHAT ID")
    logger.info("=" * 70)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN non configurato")
        logger.info("\n💡 Come ottenere il bot token:")
        logger.info("   1. Apri Telegram e cerca @BotFather")
        logger.info("   2. Invia /newbot")
        logger.info("   3. Segui le istruzioni per creare il bot")
        logger.info("   4. Copia il token ricevuto")
        logger.info("\n💡 Come ottenere il chat ID:")
        logger.info("   Metodo 1: Invia un messaggio a @userinfobot")
        logger.info("   Metodo 2: Invia /start al tuo bot, poi esegui questo script")
        logger.info("   Metodo 3: Inizia chat con @JsonDumpBot e inoltra un messaggio")
        return

    logger.info(f"✅ Bot token trovato: {bot_token[:10]}...")
    logger.info("\n🔍 Cercando chat IDs dai messaggi recenti...")
    logger.info("   (Assicurati di aver inviato almeno un messaggio al bot)")

    await get_updates(bot_token)

    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
