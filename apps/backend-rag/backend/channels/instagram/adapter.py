"""Instagram Channel Adapter."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.instagram.config import InstagramChannelConfig
from backend.channels.instagram.formatter import InstagramMessageFormatter

logger = logging.getLogger(__name__)


class InstagramChannelAdapter(BaseChannel):
    """Instagram Business API adapter."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.instagram_config = InstagramChannelConfig(
            access_token=config.get("access_token", ""),
            instagram_account_id=config.get("instagram_account_id", ""),
        )
        self.formatter = InstagramMessageFormatter()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Parse Instagram webhook."""
        try:
            entry = raw_event.get("entry", [{}])[0]
            messaging = entry.get("messaging", [{}])[0]
            sender_id = messaging.get("sender", {}).get("id", "unknown")
            message_text = messaging.get("message", {}).get("text", "")

            return ChannelMessage(
                user_id=f"instagram_{sender_id}",
                session_id=f"ig_session_{sender_id}",
                text=message_text,
                channel="instagram",
                metadata={"sender_id": sender_id},
            )
        except Exception as e:
            logger.error(f"Failed to parse Instagram webhook: {e}")
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """Send message via Instagram API."""
        formatted_text = self.formatter.format_response(response)
        if len(formatted_text) > self.instagram_config.max_message_length:
            formatted_text = self.truncate_message(
                formatted_text, self.instagram_config.max_message_length
            )

        url = "https://graph.facebook.com/v18.0/me/messages"
        payload = {"recipient": {"id": channel_id}, "message": {"text": formatted_text}}
        headers = {"Authorization": f"Bearer {self.instagram_config.access_token}"}

        try:
            await self.client.post(url, json=payload, headers=headers)
            logger.info(f"✅ Sent Instagram message to {channel_id}")
        except Exception as e:
            logger.error(f"Instagram send failed: {e}")

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """Instagram doesn't support typing indicators."""
        pass

    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse]
    ) -> None:
        """Accumulate and send complete message."""
        text = ""
        async for r in response_stream:
            if r.text:
                text += r.text
        if text:
            await self.send_response(channel_id, ChannelResponse(text=text, metadata={}))

    @property
    def channel_name(self) -> str:
        return "instagram"

    @property
    def supports_markdown(self) -> bool:
        return False

    @property
    def supports_media(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return self.instagram_config.max_message_length
