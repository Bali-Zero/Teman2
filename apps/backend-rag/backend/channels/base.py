"""
Base Channel - Abstract Interface

Defines the contract that all channel adapters must implement.
Provides normalized message/response formats for channel-agnostic processing.

Author: Claude Sonnet
Date: 2026-02-10
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """
    Normalized message format across all channels.

    This is the unified format that all channel adapters must produce.
    Allows the core business logic to be channel-agnostic.
    """

    user_id: str  # Unique user identifier (e.g., "telegram_123456", "whatsapp_+6281234567890")
    session_id: str  # Session identifier for conversation continuity
    text: str  # Message text content
    media: list[str] | None = None  # URLs to images/videos/documents
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific metadata
    channel: str = "unknown"  # Channel name (telegram, whatsapp, web, etc.)


@dataclass
class ChannelResponse:
    """
    Normalized response format across all channels.

    Channel adapters format this into platform-specific messages.
    """

    text: str  # Response text
    sources: list[dict] | None = None  # Citations/sources
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional data
    media: list[str] | None = None  # Media to send
    workflow: dict[str, Any] | None = None  # Workflow data (if applicable)


class BaseChannel(ABC):
    """
    Abstract base class for all channel adapters.

    Each channel (Telegram, WhatsApp, Instagram, etc.) must implement
    this interface to integrate with the unified architecture.

    Responsibilities:
    - Normalize incoming messages (platform → ChannelMessage)
    - Format outgoing responses (ChannelResponse → platform)
    - Handle platform-specific features (typing indicators, media, etc.)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize channel adapter.

        Args:
            config: Channel-specific configuration
        """
        self.config = config
        self.timeout = config.get("timeout", 30.0)
        self.update_interval = config.get("update_interval", 2.0)
        logger.info(f"✅ {self.channel_name} adapter initialized (timeout={self.timeout}s)")

    # ==================== Abstract Methods (MUST Implement) ====================

    @abstractmethod
    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """
        Normalize incoming message from platform-specific format.

        Args:
            raw_event: Raw webhook/API event from the platform

        Returns:
            Normalized ChannelMessage

        Example:
            Telegram raw_event → ChannelMessage with user_id="telegram_123456"
        """
        pass

    @abstractmethod
    async def send_response(self, channel_id: str, response: ChannelResponse) -> None:
        """
        Send response in platform-specific format.

        Args:
            channel_id: Platform-specific identifier (chat_id, phone_number, etc.)
            response: Normalized ChannelResponse to send

        Example:
            ChannelResponse → Telegram message with Markdown formatting
        """
        pass

    @abstractmethod
    async def send_status_update(self, channel_id: str, status: str) -> None:
        """
        Send status update (typing indicator, read receipt, etc.).

        Args:
            channel_id: Platform-specific identifier
            status: Status type (e.g., "typing", "recording", "uploading")

        Example:
            Telegram: sendChatAction with action="typing"
            WhatsApp: Mark message as read
        """
        pass

    @abstractmethod
    async def stream_response(
        self, channel_id: str, response_stream: AsyncIterator[ChannelResponse]
    ) -> None:
        """
        Handle streaming responses with platform-specific optimizations.

        Different channels have different constraints:
        - Telegram: Progressive message updates (1-2s interval)
        - WhatsApp: Multiple messages (no live updates)
        - Web: SSE token-by-token streaming

        Args:
            channel_id: Platform-specific identifier
            response_stream: Stream of ChannelResponse objects

        Example:
            Telegram: Update placeholder message every 1s with accumulated tokens
            Web: Yield SSE events for each token
        """
        pass

    # ==================== Properties (MUST Implement) ====================

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return channel name (e.g., 'telegram', 'whatsapp', 'web')."""
        pass

    @property
    @abstractmethod
    def supports_markdown(self) -> bool:
        """Whether channel supports Markdown formatting."""
        pass

    @property
    @abstractmethod
    def supports_media(self) -> bool:
        """Whether channel supports image/video/document sending."""
        pass

    @property
    @abstractmethod
    def max_message_length(self) -> int:
        """
        Maximum characters per message.

        Examples:
        - Telegram: 4096
        - WhatsApp: 4096
        - Twitter DM: 10000
        - Web: 100000+ (no practical limit)
        """
        pass

    # ==================== Helper Methods (Optional) ====================

    def truncate_message(self, text: str, max_length: int | None = None) -> str:
        """
        Truncate message to fit platform limits.

        Args:
            text: Message text
            max_length: Override max_message_length if provided

        Returns:
            Truncated text with ellipsis if needed
        """
        limit = max_length or self.max_message_length
        if len(text) <= limit:
            return text

        # Leave room for ellipsis
        return text[: limit - 20] + "\n\n_...continua..._"

    def split_message(self, text: str, max_length: int | None = None) -> list[str]:
        """
        Split long message into chunks that fit platform limits.

        Args:
            text: Message text
            max_length: Override max_message_length if provided

        Returns:
            List of message chunks
        """
        limit = max_length or self.max_message_length
        if len(text) <= limit:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= limit:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
