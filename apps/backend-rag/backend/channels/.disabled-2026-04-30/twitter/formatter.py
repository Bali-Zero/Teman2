"""Twitter Message Formatter (plain text)."""

import logging

from backend.channels.base import ChannelResponse

logger = logging.getLogger(__name__)


class TwitterMessageFormatter:
    """Format messages for Twitter DMs (plain text)."""

    @staticmethod
    def format_response(response: ChannelResponse) -> str:
        """Format response for Twitter DMs."""
        parts = []
        if response.text:
            parts.append(response.text)
        if response.sources:
            parts.append("\n\n📚 Sources:")
            for idx, src in enumerate(response.sources[:3], 1):
                title = src.get("title", "Link")
                url = src.get("url", "")
                parts.append(f"{idx}. {title} {url}")
        return "\n".join(parts)

    @staticmethod
    def format_error(error: str) -> str:
        return f"❌ Error: {error}"
