"""Instagram Message Formatter (plain text only)."""

import logging

from backend.channels.base import ChannelResponse
from backend.channels.source_filter import public_sources

logger = logging.getLogger(__name__)


class InstagramMessageFormatter:
    """Format messages for Instagram DMs (plain text)."""

    @staticmethod
    def format_response(response: ChannelResponse) -> str:
        """Format response for Instagram (plain text only)."""
        parts = []
        if response.text:
            parts.append(response.text)
        safe_sources = public_sources(response.sources)
        if safe_sources:
            parts.append("\n\n📚 Fonti:")
            for idx, src in enumerate(safe_sources[:3], 1):
                parts.append(f"{idx}. {src.get('title', 'Link')}")
                if src.get("url"):
                    parts.append(f"   {src['url']}")
        return "\n".join(parts)

    @staticmethod
    def format_error(error: str) -> str:
        return f"❌ Errore: {error}"
