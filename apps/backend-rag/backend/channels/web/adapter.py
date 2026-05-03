"""
Web Channel Adapter.

Implements BaseChannel for web applications using SSE (Server-Sent Events) streaming.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.web.config import WebChannelConfig
from backend.channels.web.formatter import WebMessageFormatter

logger = logging.getLogger(__name__)


class WebChannelAdapter(BaseChannel):
    """
    Web application adapter using SSE (Server-Sent Events) streaming.

    Features:
    - Token-by-token streaming via SSE
    - Rich Markdown support
    - Real-time event delivery
    - No message length limits
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize Web adapter.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)

        # Parse Web-specific config
        self.web_config = WebChannelConfig(
            max_message_length=config.get("max_message_length", 100000),
            supports_markdown=config.get("supports_markdown", True),
            supports_media=config.get("supports_media", True),
            stream_mode=config.get("stream_mode", "sse"),
        )

        self.formatter = WebMessageFormatter()

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """
        Parse web request into ChannelMessage.

        Expected request structure:
        {
            "query": "What is the capital of France?",
            "user_id": "user@example.com",
            "session_id": "web_session_123",
            "conversation_history": [...]
        }

        Args:
            raw_event: Web request dict

        Returns:
            Normalized ChannelMessage
        """
        try:
            # Extract fields
            user_id = raw_event.get("user_id", "anonymous")
            session_id = raw_event.get("session_id", "web_session_unknown")
            text = raw_event.get("query", "")

            # Extract conversation history (if present)
            conversation_history = raw_event.get("conversation_history", [])

            # Extract images (for vision)
            images = raw_event.get("images", [])

            # Build metadata
            metadata = {
                "conversation_id": raw_event.get("conversation_id"),
                "enable_vision": raw_event.get("enable_vision", False),
                "conversation_history_length": len(conversation_history),
                "has_images": len(images) > 0,
            }

            logger.info(
                f"🌐 Web message received: user={user_id[:20]}, "
                f"session={session_id}, text={text[:50]}...",
            )

            return ChannelMessage(
                user_id=user_id,
                session_id=session_id,
                text=text,
                media=images if images else None,
                metadata=metadata,
                channel="web",
            )

        except Exception as e:
            logger.error(f"Failed to parse web request: {e}", exc_info=True)
            raise

    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """
        Send a complete response to web client.

        NOTE: For web, we typically use stream_response() instead.
        This method exists for compatibility but is rarely used.

        Args:
            channel_id: Session/correlation ID
            response: Response to send
        """
        logger.warning("send_response called for web channel (use stream_response instead)")

        # Format response
        formatted_text = self.formatter.format_response(response)

        logger.info(f"✅ Web response formatted: {len(formatted_text)} chars")

        # In real implementation, this would send via HTTP response
        # But for SSE streaming, we use stream_response() instead

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """
        Send status update to web client (via SSE).

        NOTE: In practice, this is handled by stream_response() yielding
        status events. This method is here for interface compatibility.

        Args:
            channel_id: Session/correlation ID
            status: Status type ("processing", "thinking", etc.)
        """
        logger.debug(f"📍 Web status update: {status} (channel: {channel_id})")

        # In stream_response(), we yield status events directly
        # This method is for non-streaming scenarios (rarely used)

    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse],
    ) -> AsyncIterator[str]:
        """
        Stream response to web client using SSE format.

        SSE Event Format:
        data: {"type": "token", "data": "Hello"}

        Args:
            channel_id: Session/correlation ID
            response_stream: AsyncIterator of ChannelResponse events

        Yields:
            SSE-formatted strings (data: {...})
        """
        try:
            # Yield initial status
            yield self._format_sse_event(
                {
                    "type": "status",
                    "data": {"status": "processing", "correlation_id": channel_id},
                },
            )

            # Stream events
            async for response in response_stream:
                # Convert ChannelResponse → SSE event
                event = self._channel_response_to_sse(response)

                # Yield SSE-formatted event
                yield self._format_sse_event(event)

            # Yield final status
            yield self._format_sse_event(
                {
                    "type": "status",
                    "data": {"status": "completed", "correlation_id": channel_id},
                },
            )

            logger.info(f"✅ Completed web stream for channel {channel_id}")

        except Exception as e:
            logger.error(f"Error streaming to web: {e}", exc_info=True)

            # Send error event
            error_event = {
                "type": "error",
                "data": {
                    "error_type": "fatal_error",
                    "message": f"Stream failed: {str(e)}",
                    "fatal": True,
                    "correlation_id": channel_id,
                },
            }
            yield self._format_sse_event(error_event)

    def _channel_response_to_sse(self, response: ChannelResponse) -> dict[str, Any]:
        """
        Convert ChannelResponse to SSE event dict.

        Args:
            response: ChannelResponse to convert

        Returns:
            SSE event dictionary
        """
        event_type = response.metadata.get("event_type", "token")

        # Map event types
        if event_type == "token":
            return {"type": "token", "data": response.text}

        elif event_type == "thinking":
            return {"type": "thinking", "data": response.text}

        elif event_type == "tool_call":
            return {"type": "tool_call", "data": response.metadata}

        elif event_type == "observation":
            return {"type": "observation", "data": response.text}

        elif event_type == "sources":
            return {"type": "sources", "data": response.sources}

        elif event_type == "workflow":
            return {"type": "workflow", "data": response.workflow}

        elif event_type == "answer":
            # Final complete answer
            return {
                "type": "answer",
                "data": {
                    "text": response.text,
                    "sources": response.sources,
                    "workflow": response.workflow,
                },
            }

        else:
            # Unknown event type - pass through
            return {"type": event_type, "data": response.text or response.metadata}

    def _format_sse_event(self, event: dict[str, Any]) -> str:
        """
        Format event as SSE string.

        SSE Format:
        data: {"type": "token", "data": "Hello"}

        Args:
            event: Event dictionary

        Returns:
            SSE-formatted string
        """
        event_json = json.dumps(event)
        return f"data: {event_json}\n\n"

    # BaseChannel abstract properties

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "web"

    @property
    def supports_markdown(self) -> bool:
        """Web supports rich Markdown."""
        return self.web_config.supports_markdown

    @property
    def supports_media(self) -> bool:
        """Web supports media attachments."""
        return self.web_config.supports_media

    @property
    def max_message_length(self) -> int:
        """Web has no practical message length limit."""
        return self.web_config.max_message_length
