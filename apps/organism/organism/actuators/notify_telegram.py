"""Actuator: send a Telegram message via existing bot credentials."""
import os
import httpx
from organism.actuators.base import ActuatorBase


class NotifyTelegram(ActuatorBase):
    name = "notify_telegram"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy singleton httpx client per GR #10. Caller invokes aclose() on shutdown."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def aclose(self) -> None:
        """Close the persistent client. Call from dispatcher shutdown path."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _execute(self, params: dict) -> dict:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
        if not chat:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID env var not set")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        message = params.get("message", "(no message)")[:4000]
        client = await self._get_client()
        resp = await client.post(url, json={"chat_id": chat, "text": message})
        resp.raise_for_status()
        return {"status_code": resp.status_code, "chars_sent": len(message)}

    async def _dry_run(self, params: dict) -> dict:
        return {"would_send": params.get("message", "(no message)")[:200]}
