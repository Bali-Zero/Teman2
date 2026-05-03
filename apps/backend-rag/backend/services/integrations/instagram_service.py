"""
Instagram Service - Inbound + Outbound
Uses Meta Instagram Graph API (Messaging)

Handles:
- Sending messages to users via Instagram DMs
- Receiving webhook events
- Profile information retrieval
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


class InstagramService:
    """Service for interacting with Meta Instagram Graph API."""

    def __init__(self) -> None:
        self._token = settings.instagram_access_token
        self._account_id = settings.instagram_account_id
        self._client: httpx.AsyncClient | None = None

    @property
    def token(self) -> str | None:
        """Token."""
        return self._token or settings.instagram_access_token

    @property
    def account_id(self) -> str | None:
        """Count items."""
        return self._account_id or settings.instagram_account_id

    @property
    def api_url(self) -> str:
        """Api url."""
        return f"https://graph.instagram.com/v22.0/{self.account_id}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=HttpTimeoutConstants.EXTERNAL_API_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_message(
        self,
        recipient_id: str,
        text: str,
    ) -> dict[str, Any]:
        """
        Send an Instagram DM.

        Args:
            recipient_id: Recipient IGSID (Instagram Scoped ID)
            text: Message text

        Returns:
            Instagram API response

        Note:
            Instagram has a 1000 char limit per message.
        """
        if not self.token:
            raise ValueError("Instagram access token not configured")

        if not self.account_id:
            raise ValueError("Instagram account ID not configured")

        client = await self._get_client()

        payload: dict[str, Any] = {
            "recipient": {"id": recipient_id},
            "message": {"text": text[:1000]},
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

            result: dict[str, Any] = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                error_code = error_data.get("code", response.status_code)
                logger.error(f"Instagram API error [{error_code}]: {error_msg}")
                raise ValueError(f"Instagram API error [{error_code}]: {error_msg}")

            logger.info(f"Instagram message sent to {recipient_id}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to send Instagram message: {e}")
            raise

    async def mark_message_seen(self, sender_id: str) -> bool:
        """
        Send a 'mark_seen' action for the sender.

        Args:
            sender_id: IGSID of the sender

        Returns:
            Success status
        """
        if not self.token or not self.account_id:
            return False

        client = await self._get_client()

        payload = {
            "recipient": {"id": sender_id},
            "sender_action": "mark_seen",
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
            logger.warning(f"Failed to mark Instagram message as seen: {e}")
            return False

    async def get_profile(self) -> dict[str, Any]:
        """
        Get connected Instagram account profile info.

        Returns:
            Profile dict with id, username, name, profile_picture_url, followers_count
        """
        if not self.token:
            raise ValueError("Instagram access token not configured")

        client = await self._get_client()

        try:
            response = await client.get(
                "https://graph.instagram.com/v22.0/me",
                params={
                    "fields": "id,username,name,profile_picture_url,followers_count",
                    "access_token": self.token,
                },
            )

            result: dict[str, Any] = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                logger.error(f"Instagram profile error: {error_msg}")
                raise ValueError(f"Instagram profile error: {error_msg}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Instagram profile: {e}")
            raise

    def chunk_message(self, text: str, max_length: int = 950) -> list[str]:
        """
        Split long message into chunks for Instagram's 1000 char limit.

        Args:
            text: Full message text
            max_length: Maximum length per chunk (default 950 for safety margin)

        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        paragraphs = text.split("\n\n")

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

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

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


# Singleton instance
instagram_service = InstagramService()
