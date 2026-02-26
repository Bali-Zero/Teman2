"""Twitter Channel Adapter."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.twitter.config import TwitterChannelConfig
from backend.channels.twitter.formatter import TwitterMessageFormatter

logger = logging.getLogger(__name__)


class TwitterChannelAdapter(BaseChannel):
    """Twitter API v2 adapter for DMs."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.twitter_config = TwitterChannelConfig(
            bearer_token=config.get("bearer_token", ""),
            api_key=config.get("api_key"),
            api_secret=config.get("api_secret"),
        )
        self.formatter = TwitterMessageFormatter()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Parse Twitter webhook (Account Activity API)."""
        try:
            dm_events = raw_event.get("direct_message_events", [])
            if not dm_events:
                return ChannelMessage(
                    user_id="unknown", session_id="unknown", text="", channel="twitter"
                )

            dm = dm_events[0]
            sender_id = dm.get("message_create", {}).get("sender_id", "unknown")
            text = dm.get("message_create", {}).get("message_data", {}).get("text", "")

            return ChannelMessage(
                user_id=f"twitter_{sender_id}",
                session_id=f"tw_session_{sender_id}",
                text=text,
                channel="twitter",
                metadata={"sender_id": sender_id},
            )
        except Exception as e:
            logger.error(f"Failed to parse Twitter webhook: {e}")
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """Send DM via Twitter API v2."""
        formatted_text = self.formatter.format_response(response)
        if len(formatted_text) > self.twitter_config.max_message_length:
            formatted_text = self.truncate_message(
                formatted_text, self.twitter_config.max_message_length
            )

        url = "https://api.twitter.com/2/dm_conversations/with/:participant_id/messages"
        payload = {"text": formatted_text, "participant_id": channel_id}
        headers = {"Authorization": f"Bearer {self.twitter_config.bearer_token}"}

        try:
            await self.client.post(url, json=payload, headers=headers)
            logger.info(f"✅ Sent Twitter DM to {channel_id}")
        except Exception as e:
            logger.error(f"Twitter send failed: {e}")

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """Twitter doesn't support typing indicators."""
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
        return "twitter"

    @property
    def supports_markdown(self) -> bool:
        return False

    @property
    def supports_media(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return self.twitter_config.max_message_length
