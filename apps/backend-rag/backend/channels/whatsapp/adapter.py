"""
WhatsApp Channel Adapter.

Implements BaseChannel for WhatsApp Business API (Meta Cloud API).

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.whatsapp.config import WhatsAppChannelConfig
from backend.channels.whatsapp.formatter import WhatsAppMessageFormatter

logger = logging.getLogger(__name__)


class WhatsAppChannelAdapter(BaseChannel):
    """
    WhatsApp Business API adapter for multi-channel architecture.

    Features:
    - Webhook-based message reception (Meta Cloud API)
    - Complete message delivery (no progressive updates)
    - Limited Markdown support (*bold*, _italic_)
    - Media support (images, documents)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize WhatsApp adapter."""
        super().__init__(config)

        self.whatsapp_config = WhatsAppChannelConfig(
            access_token=config.get("access_token", ""),
            phone_number_id=config.get("phone_number_id", ""),
            business_account_id=config.get("business_account_id"),
            max_message_length=config.get("max_message_length", 1600),
        )

        self.formatter = WhatsAppMessageFormatter()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client to prevent connection leaks."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """
        Parse WhatsApp webhook into ChannelMessage.

        WhatsApp webhook structure:
        {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "id": "wamid.xxx",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello"}
                        }],
                        "contacts": [{"profile": {"name": "John"}}]
                    }
                }]
            }]
        }
        """
        try:
            entry = raw_event.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            messages = value.get("messages", [])
            if not messages:
                logger.warning("No messages in WhatsApp webhook")
                return ChannelMessage(
                    user_id="unknown",
                    session_id="unknown",
                    text="",
                    channel="whatsapp",
                )

            message = messages[0]
            from_phone = message.get("from", "unknown")
            message_type = message.get("type", "text")

            # Extract text
            text = ""
            if message_type == "text":
                text = message.get("text", {}).get("body", "")

            # Extract contact name
            contacts = value.get("contacts", [])
            sender_name = None
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name")

            # Session ID = phone number
            session_id = f"wa_session_{from_phone}"

            # Metadata
            metadata = {
                "phone": from_phone,
                "sender_name": sender_name,
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp"),
                "message_type": message_type,
            }

            logger.info(
                f"📨 WhatsApp message: phone={from_phone}, name={sender_name}, text={text[:50]}...",
            )

            return ChannelMessage(
                user_id=f"whatsapp_{from_phone}",
                session_id=session_id,
                text=text,
                metadata=metadata,
                channel="whatsapp",
            )

        except Exception as e:
            logger.error(f"Failed to parse WhatsApp webhook: {e}", exc_info=True)
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """Send complete response to WhatsApp."""
        try:
            # Format response
            formatted_text = self.formatter.format_response(response)

            # Truncate if needed
            if len(formatted_text) > self.whatsapp_config.max_message_length:
                formatted_text = self.truncate_message(
                    formatted_text, self.whatsapp_config.max_message_length,
                )

            # Send via Meta API
            url = f"{self.whatsapp_config.api_base_url}/{self.whatsapp_config.api_version}/{self.whatsapp_config.phone_number_id}/messages"

            payload = {
                "messaging_product": "whatsapp",
                "to": channel_id,
                "type": "text",
                "text": {"body": formatted_text},
            }

            headers = {
                "Authorization": f"Bearer {self.whatsapp_config.access_token}",
                "Content-Type": "application/json",
            }

            result = await self.client.post(url, json=payload, headers=headers)
            result.raise_for_status()

            logger.info(f"✅ Sent WhatsApp message to {channel_id}")

        except Exception as e:
            logger.error(f"Error sending WhatsApp response: {e}", exc_info=True)

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """
        WhatsApp doesn't support typing indicators.
        This method is a no-op for compatibility.
        """
        logger.debug(f"WhatsApp status update (no-op): {status} for {channel_id}")

    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse],
    ) -> None:
        """
        Stream response to WhatsApp (accumulated, then sent once).

        WhatsApp doesn't support progressive updates like Telegram.
        We accumulate all tokens and send complete message.
        """
        accumulated_text = ""
        accumulated_sources = []
        accumulated_workflow = None

        try:
            # Accumulate all events
            async for response in response_stream:
                if response.text:
                    accumulated_text += response.text

                if response.sources:
                    accumulated_sources.extend(response.sources)

                if response.workflow:
                    accumulated_workflow = response.workflow

            # Send complete message
            if accumulated_text:
                final_response = ChannelResponse(
                    text=accumulated_text,
                    sources=accumulated_sources if accumulated_sources else None,
                    workflow=accumulated_workflow,
                    metadata={"final": True},
                )

                await self.send_response(channel_id, final_response)

                logger.info(f"✅ Completed WhatsApp stream: {len(accumulated_text)} chars")

        except Exception as e:
            logger.error(f"Error streaming to WhatsApp: {e}", exc_info=True)

            # Send error message
            error_text = self.formatter.format_error("Si è verificato un errore. Riprova.")
            error_response = ChannelResponse(text=error_text, metadata={})
            await self.send_response(channel_id, error_response)

    # BaseChannel properties

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "whatsapp"

    @property
    def supports_markdown(self) -> bool:
        """WhatsApp supports limited Markdown."""
        return self.whatsapp_config.supports_markdown

    @property
    def supports_media(self) -> bool:
        """WhatsApp supports media."""
        return self.whatsapp_config.supports_media

    @property
    def max_message_length(self) -> int:
        """WhatsApp max message length: 1600 characters."""
        return self.whatsapp_config.max_message_length
