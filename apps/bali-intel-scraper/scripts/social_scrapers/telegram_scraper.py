"""
Telegram Channel Scraper
Primary: scrapes public channel preview pages (t.me/s/) — no API keys needed.
Fallback: uses Telethon if TELEGRAM_API_ID/TELEGRAM_API_HASH are set (more messages, richer data).
"""

import os
from datetime import datetime

import httpx
from bs4 import BeautifulSoup


def fetch_telegram_channel_sync(
    channel_username: str,
    limit: int = 10,
    hours_back: int = 24,
) -> list[dict]:
    """Fetch messages from a public Telegram channel.

    Uses t.me/s/ public preview (no auth). Falls back to Telethon if API creds are set.
    """
    api_id = os.environ.get('TELEGRAM_API_ID', '')
    api_hash = os.environ.get('TELEGRAM_API_HASH', '')

    if api_id and api_hash:
        return _fetch_via_telethon(channel_username, limit, hours_back, int(api_id), api_hash)

    return _fetch_via_preview(channel_username, limit)


def _fetch_via_preview(channel_username: str, limit: int = 10) -> list[dict]:
    """Scrape t.me/s/<channel> public preview page — no auth required."""
    url = f'https://t.me/s/{channel_username}'
    resp = httpx.get(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
        timeout=15,
        follow_redirects=True,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'lxml')
    msg_widgets = soup.select('div.tgme_widget_message_wrap')

    messages = []
    for widget in reversed(msg_widgets):  # newest first
        text_el = widget.select_one('div.tgme_widget_message_text')
        if not text_el:
            continue

        text = text_el.get_text(strip=True)
        if len(text) < 20:
            continue

        # Extract message URL
        msg_link = widget.select_one('a.tgme_widget_message_date')
        msg_url = msg_link['href'] if msg_link else f'https://t.me/{channel_username}'

        # Extract date
        date_el = widget.select_one('time.datetime')
        msg_date = date_el['datetime'] if date_el else datetime.now().isoformat()

        # Extract views
        views_el = widget.select_one('span.tgme_widget_message_views')
        views_text = views_el.get_text(strip=True) if views_el else '0'
        views = _parse_views(views_text)

        messages.append({
            'text': text,
            'date': msg_date,
            'url': msg_url,
            'views': views,
        })

        if len(messages) >= limit:
            break

    return messages


def _parse_views(text: str) -> int:
    """Parse view counts like '1.2K', '3.4M'."""
    text = text.strip().upper()
    if not text or text == '0':
        return 0
    multipliers = {'K': 1000, 'M': 1000000}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(text.replace(',', '').replace('.', ''))
    except ValueError:
        return 0


def _fetch_via_telethon(
    channel_username: str,
    limit: int,
    hours_back: int,
    api_id: int,
    api_hash: str,
) -> list[dict]:
    """Fetch via Telethon API (richer data, requires auth)."""
    import asyncio
    from datetime import timedelta, timezone
    from pathlib import Path

    async def _fetch():
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError

        session_file = str(Path(__file__).parent.parent.parent / 'data' / '.telegram_session')
        client = TelegramClient(session_file, api_id, api_hash)
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

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _fetch()).result()
    else:
        return asyncio.run(_fetch())
