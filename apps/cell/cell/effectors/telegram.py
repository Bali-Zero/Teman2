"""Telegram alerter — CELL's voice to the human operator."""
import logging
from typing import Any

logger = logging.getLogger("cell.telegram")

class TelegramAlerter:
    def __init__(self, client: Any, bot_token: str, chat_id: str) -> None:
        self._client = client
        self._token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, message: str) -> bool:
        try:
            response = await self._client.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": self._chat_id, "text": f"🧬 CELL: {message}", "parse_mode": "Markdown"},
            )
            if response.status_code == 200:
                logger.info(f"Telegram alert sent: {message[:50]}...")
                return True
            logger.warning(f"Telegram API returned {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
