"""Twitter/X Channel Adapter — DM via API v2 with OAuth 1.0a."""

import hashlib
import hmac
import logging
import time
import urllib.parse
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.twitter.config import TwitterChannelConfig
from backend.channels.twitter.formatter import TwitterMessageFormatter

logger = logging.getLogger(__name__)


class TwitterChannelAdapter(BaseChannel):
    """Twitter/X API v2 adapter for DMs."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.twitter_config = TwitterChannelConfig(
            consumer_key=config.get("consumer_key", ""),
            consumer_secret=config.get("consumer_secret", ""),
            access_token=config.get("access_token", ""),
            access_token_secret=config.get("access_token_secret", ""),
            bearer_token=config.get("bearer_token", ""),
            client_id=config.get("client_id", ""),
            client_secret=config.get("client_secret", ""),
        )
        self.formatter = TwitterMessageFormatter()
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-init persistent AsyncClient (Golden Rule #10).

        Lifespan teardown calls ``close()`` via the channel-router
        adapter loop in ``app_factory.lifespan`` (security audit
        2026-04-03). ``isinstance`` guard protects unit tests that
        inject AsyncMock.
        """
        c = self._client
        if c is None or (isinstance(c, httpx.AsyncClient) and c.is_closed):
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @client.setter
    def client(self, value: httpx.AsyncClient | None) -> None:
        """Setter for unit tests that inject a mock AsyncClient."""
        self._client = value

    async def close(self) -> None:
        """Close the HTTP client to prevent connection leaks."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _oauth1_header(self, method: str, url: str, body: str = "") -> str:
        """Generate OAuth 1.0a Authorization header for X API v2."""
        oauth_params = {
            "oauth_consumer_key": self.twitter_config.consumer_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.twitter_config.access_token,
            "oauth_version": "1.0",
        }

        # Build signature base string
        params_str = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(oauth_params.items())
        )
        base_string = (
            f"{method.upper()}&"
            f"{urllib.parse.quote(url, safe='')}&"
            f"{urllib.parse.quote(params_str, safe='')}"
        )

        # Signing key
        signing_key = (
            f"{urllib.parse.quote(self.twitter_config.consumer_secret, safe='')}&"
            f"{urllib.parse.quote(self.twitter_config.access_token_secret, safe='')}"
        )

        import base64

        signature = base64.b64encode(
            hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha256).digest(),
        ).decode()

        oauth_params["oauth_signature"] = signature

        header_parts = ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )
        return f"OAuth {header_parts}"

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Parse X/Twitter webhook (Account Activity API)."""
        try:
            # X API v2 webhook format for DMs
            dm_events = raw_event.get("direct_message_events", [])
            if not dm_events:
                return ChannelMessage(
                    user_id="unknown", session_id="unknown", text="", channel="twitter",
                )

            dm = dm_events[0]
            sender_id = dm.get("message_create", {}).get("sender_id", "unknown")
            text = dm.get("message_create", {}).get("message_data", {}).get("text", "")

            return ChannelMessage(
                user_id=f"twitter_{sender_id}",
                session_id=f"tw_session_{sender_id}",
                text=text,
                channel="twitter",
                metadata={
                    "sender_id": sender_id,
                    "conversation_id": sender_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to parse X webhook: {e}")
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """Send DM via X API v2 with OAuth 1.0a."""
        formatted_text = self.formatter.format_response(response)
        if len(formatted_text) > self.twitter_config.max_message_length:
            formatted_text = self.truncate_message(
                formatted_text, self.twitter_config.max_message_length,
            )

        url = f"https://api.x.com/2/dm_conversations/with/{channel_id}/messages"
        payload = {"text": formatted_text}

        auth_header = self._oauth1_header("POST", url)
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }

        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            if resp.status_code == 201:
                logger.info(f"✅ Sent X DM to {channel_id}")
            else:
                logger.error(
                    f"X API error {resp.status_code}: {resp.text} (channel_id={channel_id})",
                )
        except Exception as e:
            logger.error(f"X DM send failed: {e}")
            raise  # Let send_response_safe() catch and route to DLQ

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """X doesn't support typing indicators."""
        pass

    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse],
    ) -> None:
        """Accumulate and send complete message."""
        text = ""
        async for r in response_stream:
            if r.text:
                text += r.text
        if text:
            await self.send_response_safe(channel_id, ChannelResponse(text=text, metadata={}))

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
