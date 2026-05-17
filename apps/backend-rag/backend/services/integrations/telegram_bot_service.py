"""
Telegram Bot Service for Zantara
Handles incoming messages and sends responses via Telegram Bot API.
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramBotService:
    """Service for interacting with Telegram Bot API."""

    def __init__(self) -> None:
        self._token = settings.telegram_bot_token
        self._client: httpx.AsyncClient | None = None

    @property
    def token(self) -> str | None:
        """Token."""
        return self._token or settings.telegram_bot_token

    @property
    def api_url(self) -> str:
        """Api url."""
        return f"{TELEGRAM_API_BASE}{self.token}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=HttpTimeoutConstants.TELEGRAM_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = "Markdown",
        reply_to_message_id: int | None = None,
        disable_web_page_preview: bool = True,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a message to a Telegram chat.

        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Markdown, HTML, or None for plain text
            reply_to_message_id: Optional message to reply to
            disable_web_page_preview: Disable link previews
            reply_markup: Optional inline keyboard

        Returns:
            Telegram API response
        """
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = await client.post(
                f"{self.api_url}/sendMessage",
                json=payload,
            )

            result = response.json()

            if not result.get("ok"):
                error_code = result.get("error_code", "unknown")
                description = result.get("description", "Unknown error")
                logger.error("Telegram API error [%s]: %s", error_code, description)
                raise ValueError(f"Telegram API error [{error_code}]: {description}")

            logger.info("Message sent to chat %s", chat_id)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to send Telegram message: %s", e)
            raise

    async def send_photo(
        self,
        chat_id: int | str,
        photo: Any,
        caption: str | None = None,
        parse_mode: str | None = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a photo to a Telegram chat using multipart upload.

        Args:
            chat_id: Target chat ID
            photo: File-like object (opened in 'rb' mode)
            caption: Optional photo caption
            parse_mode: HTML, Markdown, or None
            reply_markup: Optional inline keyboard

        Returns:
            Telegram API response
        """
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            import json

            data["reply_markup"] = json.dumps(reply_markup)

        files = {"photo": ("photo.jpg", photo, "image/jpeg")}

        try:
            response = await client.post(
                f"{self.api_url}/sendPhoto",
                data=data,
                files=files,
            )

            result = response.json()

            if not result.get("ok"):
                error_code = result.get("error_code", "unknown")
                description = result.get("description", "Unknown error")
                logger.error("Telegram API error [%s]: %s", error_code, description)
                raise ValueError(f"Telegram API error [{error_code}]: {description}")

            logger.info("Photo sent to chat %s", chat_id)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to send Telegram photo: %s", e)
            raise

    async def send_chat_action(
        self,
        chat_id: int | str,
        action: str = "typing",
    ) -> bool:
        """
        Send a chat action (typing indicator, etc.)

        Args:
            chat_id: Target chat ID
            action: typing, upload_photo, record_video, etc.

        Returns:
            Success status
        """
        if not self.token:
            return False

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.api_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning("Failed to send chat action: %s", e)
            return False

    async def set_webhook(
        self,
        url: str,
        secret_token: str | None = None,
        allowed_updates: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Set webhook URL for receiving updates.

        Args:
            url: HTTPS URL for webhook
            secret_token: Secret for X-Telegram-Bot-Api-Secret-Token header
            allowed_updates: List of update types to receive

        Returns:
            Telegram API response
        """
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        payload: dict[str, Any] = {"url": url}

        if secret_token:
            payload["secret_token"] = secret_token

        if allowed_updates:
            payload["allowed_updates"] = allowed_updates

        try:
            response = await client.post(
                f"{self.api_url}/setWebhook",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            logger.info("Webhook set to %s: %s", url, result)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to set webhook: %s", e)
            raise

    async def delete_webhook(self) -> dict[str, Any]:
        """Remove webhook and switch to polling mode."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        try:
            response = await client.post(f"{self.api_url}/deleteWebhook")
            response.raise_for_status()
            result = response.json()

            logger.info("Webhook deleted: %s", result)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to delete webhook: %s", e)
            raise

    async def get_webhook_info(self) -> dict[str, Any]:
        """Get current webhook configuration."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        try:
            response = await client.get(f"{self.api_url}/getWebhookInfo")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error("Failed to get webhook info: %s", e)
            raise

    async def get_me(self) -> dict[str, Any]:
        """Get bot information."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        try:
            response = await client.get(f"{self.api_url}/getMe")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error("Failed to get bot info: %s", e)
            raise

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """
        Answer a callback query from an inline keyboard button.

        Args:
            callback_query_id: ID of the callback query
            text: Text to show to user (toast or alert)
            show_alert: If True, show alert dialog instead of toast

        Returns:
            Telegram API response
        """
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text

        try:
            response = await client.post(
                f"{self.api_url}/answerCallbackQuery",
                json=payload,
            )
            result = response.json()
            logger.debug("Answered callback query: %s", result)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to answer callback query: %s", e)
            raise

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file path from Telegram servers for downloading."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.api_url}/getFile",
                json={"file_id": file_id},
            )
            result = response.json()

            if not result.get("ok"):
                error_code = result.get("error_code", "unknown")
                description = result.get("description", "Unknown error")
                logger.error("Telegram getFile error [%s]: %s", error_code, description)
                raise ValueError(f"Telegram getFile error [{error_code}]: {description}")

            logger.info("Got file info for %s", file_id)
            return result.get("result", {})

        except httpx.HTTPError as e:
            logger.error("Failed to get file: %s", e)
            raise

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from Telegram servers."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        try:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"Downloaded file: {file_path} ({len(response.content)} bytes)")
            return response.content

        except httpx.HTTPError as e:
            logger.error("Failed to download file %s: %s", file_path, e)
            raise

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: str | None = "Markdown",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Edit the text of a message.

        Args:
            chat_id: Target chat ID
            message_id: ID of message to edit
            text: New message text
            parse_mode: Markdown, HTML, or None for plain text
            reply_markup: Optional new inline keyboard

        Returns:
            Telegram API response
        """
        if not self.token:
            raise ValueError("Telegram bot token not configured")

        client = await self._get_client()

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = await client.post(
                f"{self.api_url}/editMessageText",
                json=payload,
            )
            result = response.json()

            if not result.get("ok"):
                error_code = result.get("error_code", "unknown")
                description = result.get("description", "Unknown error")
                logger.error("Telegram API error [%s]: %s", error_code, description)

            logger.debug("Edited message %s in chat %s", message_id, chat_id)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to edit message: %s", e)
            raise


# Singleton instance
telegram_bot = TelegramBotService()
