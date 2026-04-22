"""Actuator: send a Telegram message via existing bot credentials.

Reads `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID` from the environment —
these are already present on Pro/Air for the existing Telegram channels.
Message is truncated to 4000 chars (Telegram's limit is 4096, with margin).
"""
import os

import httpx

from organism.actuators.base import ActuatorBase


class NotifyTelegram(ActuatorBase):
    name = "notify_telegram"

    async def _execute(self, params: dict) -> dict:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
        if not chat:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID env var not set")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        message = params.get("message", "(no message)")[:4000]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, json={"chat_id": chat, "text": message}
            )
            resp.raise_for_status()
        return {"status_code": resp.status_code, "chars_sent": len(message)}

    async def _dry_run(self, params: dict) -> dict:
        return {"would_send": params.get("message", "(no message)")[:200]}
