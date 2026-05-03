"""
Web Channel Configuration.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

from dataclasses import dataclass


@dataclass
class WebChannelConfig:
    """
    Configuration for Web channel adapter (SSE streaming).

    Attributes:
        max_message_length: Maximum length for web messages (unlimited for web)
        supports_markdown: Whether to use Markdown formatting
        supports_media: Whether to support media attachments
        stream_mode: Streaming mode ("sse" for Server-Sent Events)
        include_metadata: Include metadata in SSE events
    """

    max_message_length: int = 100000  # No practical limit for web
    supports_markdown: bool = True
    supports_media: bool = True
    stream_mode: str = "sse"
    include_metadata: bool = True

    # SSE-specific settings
    sse_retry_ms: int = 3000  # Client retry after disconnect
    sse_heartbeat_interval: int = 30  # Heartbeat every 30s to keep connection alive
