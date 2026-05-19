#!/usr/bin/env python3
"""Setup Telegram webhook with the correct secret token.

Usage:
    fly ssh console -a nuzantara-rag -C "PYTHONPATH=/app python3 -m backend.scripts.setup_telegram_webhook"
"""

import asyncio
import os
import sys

# Add the app to path
sys.path.insert(0, "/app")


async def main() -> None:
    """Set up the Telegram webhook."""
    from backend.services.integrations.telegram_bot_service import TelegramBotService

    bot = TelegramBotService()
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

    if not secret:
        return


    try:
        await bot.set_webhook(
            url="https://nuzantara-rag.fly.dev/api/telegram/webhook",
            secret_token=secret,
            allowed_updates=["message", "edited_message", "callback_query"],
        )
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
