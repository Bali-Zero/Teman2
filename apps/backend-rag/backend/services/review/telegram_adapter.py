"""Telegram adapter for Review Gate — small wrapper, URL-based photo sends.

We don't reuse :mod:`backend.services.integrations.telegram_bot_service` for
photo sends because that implementation requires multipart uploads with a
file-like object; here we want the lightweight Bot API variant where ``photo``
is a public URL (our Tigris signed URLs). Everything else (chat action,
edit message, callback answer) is also POST JSON — simpler and testable.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_review_telegram_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


@dataclass
class SendResult:
    ok: bool
    message_id: int | None = None
    response_body: dict | None = None
    error: str | None = None
    duration_ms: float = 0.0


class TelegramReviewAdapter:
    """Send Telegram messages for review workflow. URL-based photos.

    Parameters
    ----------
    bot_token : str | None
        Bot token; falls back to ``TELEGRAM_BOT_TOKEN`` env.
    http_client : httpx.AsyncClient, optional
        Injected client for tests; created per-call otherwise.
    """

    API_BASE = "https://api.telegram.org"
    DEFAULT_TIMEOUT = 15.0

    def __init__(
        self,
        bot_token: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        resolved = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not resolved:
            raise ValueError(
                "TelegramReviewAdapter requires TELEGRAM_BOT_TOKEN",
            )
        self.bot_token = resolved
        self._client = http_client
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    @property
    def api_url(self) -> str:
        return f"{self.API_BASE}/bot{self.bot_token}"

    async def send_photo_url(
        self,
        *,
        chat_id: int | str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> SendResult:
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "photo": photo_url,
            "parse_mode": parse_mode,
        }
        if caption:
            payload["caption"] = caption
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        return await self._post("sendPhoto", payload)

    async def send_message(
        self,
        *,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str = "HTML",
    ) -> SendResult:
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        return await self._post("sendMessage", payload)

    async def edit_message_reply_markup(
        self,
        *,
        chat_id: int | str,
        message_id: int,
        reply_markup: dict | None,
    ) -> SendResult:
        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "message_id": message_id,
        }
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)
        else:
            payload["reply_markup"] = json.dumps({"inline_keyboard": []})
        return await self._post("editMessageReplyMarkup", payload)

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> SendResult:
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
        }
        if text is not None:
            payload["text"] = text[:200]
        if show_alert:
            payload["show_alert"] = True
        return await self._post("answerCallbackQuery", payload)

    # ── internal ────────────────────────────────────────────────────

    async def _post(self, method: str, payload: dict) -> SendResult:
        start = time.perf_counter()
        client = self._client or _get_module_client(self.timeout)

        try:
            resp = await client.post(
                f"{self.api_url}/{method}",
                data=payload,
                timeout=self.timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            try:
                body = resp.json()
            except ValueError:
                return SendResult(
                    ok=False,
                    error=f"non-json response {resp.status_code}",
                    duration_ms=duration_ms,
                )

            if not body.get("ok"):
                return SendResult(
                    ok=False,
                    response_body=body,
                    error=body.get("description") or f"status {resp.status_code}",
                    duration_ms=duration_ms,
                )

            result = body.get("result", {})
            message_id = (
                result.get("message_id")
                if isinstance(result, dict)
                else None
            )
            return SendResult(
                ok=True,
                message_id=message_id,
                response_body=body,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001
            return SendResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
