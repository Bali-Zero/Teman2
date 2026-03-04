"""
Telegram Channel Scraper
Uses Telethon to fetch messages from public Telegram channels.
Requires: TELEGRAM_API_ID and TELEGRAM_API_HASH env vars (from my.telegram.org)
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / 'data'
SESSION_FILE = str(DATA_DIR / '.telegram_session')


async def fetch_telegram_channel(
    channel_username: str,
    limit: int = 10,
    api_id: int = None,
    api_hash: str = None,
    hours_back: int = 24,
) -> List[Dict]:
    """Fetch recent messages from a public Telegram channel."""
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError

    api_id = api_id or int(os.environ.get('TELEGRAM_API_ID', '0'))
    api_hash = api_hash or os.environ.get('TELEGRAM_API_HASH', '')

    if not api_id or not api_hash:
        raise ValueError('TELEGRAM_API_ID and TELEGRAM_API_HASH env vars required')

    client = TelegramClient(SESSION_FILE, api_id, api_hash)
    messages = []

    try:
        await client.start()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        async for msg in client.iter_messages(channel_username, limit=limit * 2):
            if msg.date and msg.date < cutoff:
                break
            if not msg.text or len(msg.text.strip()) < 20:
                continue

            messages.append({
                'text': msg.text.strip(),
                'date': msg.date.isoformat() if msg.date else '',
                'url': f'https://t.me/{channel_username}/{msg.id}',
                'views': getattr(msg, 'views', 0) or 0,
                'msg_id': msg.id,
            })

            if len(messages) >= limit:
                break

    except FloodWaitError as e:
        import logging
        logging.getLogger(__name__).warning(f'Telegram FloodWait: sleeping {e.seconds}s')
        await asyncio.sleep(e.seconds)
    finally:
        await client.disconnect()

    return messages


def fetch_telegram_channel_sync(
    channel_username: str,
    limit: int = 10,
    hours_back: int = 24,
) -> List[Dict]:
    """Sync wrapper around async Telethon code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If already in an async context, create a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run,
                fetch_telegram_channel(channel_username, limit=limit, hours_back=hours_back)
            ).result()
    else:
        return asyncio.run(
            fetch_telegram_channel(channel_username, limit=limit, hours_back=hours_back)
        )
