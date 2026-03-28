"""
WhatsApp Service - Inbound + Outbound
Uses Meta WhatsApp Business Cloud API

Handles:
- Sending messages to users
- Receiving webhook events
- Managing conversations
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for interacting with WhatsApp Business Cloud API."""

    def __init__(self) -> None:
        self._token = settings.whatsapp_api_token
        self._phone_number_id = settings.whatsapp_phone_number_id
        self._client: httpx.AsyncClient | None = None

    @property
    def token(self) -> str | None:
        """Token."""
        return self._token or settings.whatsapp_api_token

    @property
    def phone_number_id(self) -> str | None:
        """Phone number id."""
        return self._phone_number_id or settings.whatsapp_phone_number_id

    @property
    def api_url(self) -> str:
        """Api url."""
        return f"https://graph.facebook.com/v22.0/{self.phone_number_id}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=HttpTimeoutConstants.EXTERNAL_API_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_message(
        self,
        phone: str,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            phone: Recipient phone number (with country code, no +)
            text: Message text
            reply_to_message_id: Optional message ID to reply to

        Returns:
            WhatsApp API response

        Note:
            Phone format: "6281234567890" (no + prefix)
            WhatsApp has 4096 char limit per message
        """
        if not self.token:
            raise ValueError("WhatsApp API token not configured")

        if not self.phone_number_id:
            raise ValueError("WhatsApp phone number ID not configured")

        # Ensure phone has no + prefix (Meta API format)
        if phone.startswith("+"):
            phone = phone[1:]

        client = await self._get_client()

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": text[:4096]},  # Enforce char limit
        }

        # Add reply context if provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        try:
            response = await client.post(
                f"{self.api_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            result = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                error_code = error_data.get("code", response.status_code)
                logger.error(f"WhatsApp API error [{error_code}]: {error_msg}")
                raise ValueError(f"WhatsApp API error [{error_code}]: {error_msg}")

            logger.info(f"Message sent to {phone}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            raise

    async def send_typing_action(
        self,
        phone: str,
    ) -> bool:
        """
        Send typing indicator (mark as read).

        Note: WhatsApp Cloud API doesn't have typing indicator.
        We mark the last message as read instead.

        Args:
            phone: Recipient phone number

        Returns:
            Success status
        """
        # WhatsApp Cloud API doesn't support typing indicator
        # This is a placeholder for consistency with other messaging services
        logger.debug(f"Typing action not supported for WhatsApp, skipping for {phone}")
        return True

    async def mark_message_read(
        self,
        message_id: str,
    ) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: Message ID to mark as read

        Returns:
            Success status
        """
        if not self.token or not self.phone_number_id:
            return False

        client = await self._get_client()

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            response = await client.post(
                f"{self.api_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Failed to mark message as read: {e}")
            return False

    def format_message(self, text: str) -> str:
        """
        Format message for WhatsApp.

        WhatsApp supports basic markdown:
        - *bold*
        - _italic_
        - ~strikethrough~
        - ```code```

        Args:
            text: Raw text

        Returns:
            Formatted text (currently passthrough, can be enhanced)
        """
        # For now, pass through as-is
        # WhatsApp handles basic markdown natively
        return text

    def chunk_message(self, text: str, max_length: int = 4000) -> list[str]:
        """
        Split long message into chunks for WhatsApp's 4096 char limit.

        Args:
            text: Full message text
            max_length: Maximum length per chunk (default 4000 for safety margin)

        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first to avoid breaking mid-sentence
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            # If adding this paragraph exceeds limit, save current chunk
            if len(current_chunk) + len(para) + 2 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # If single paragraph is too long, split by newlines
                if len(para) > max_length:
                    lines = para.split("\n")
                    for line in lines:
                        if len(current_chunk) + len(line) + 1 > max_length:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"
                else:
                    current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


# Singleton instance
whatsapp_service = WhatsAppService()
