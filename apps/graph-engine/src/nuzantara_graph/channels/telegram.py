"""Telegram channel adapter — full markdown, 4096 char limit, streaming support."""

from __future__ import annotations

import re
from typing import Any

from nuzantara_graph.channels.base import ChannelAdapter
from nuzantara_schemas.state import ChannelType, GraphState


class TelegramChannelAdapter(ChannelAdapter):
    """Telegram Bot API — MarkdownV2 format, 4096 char limit."""

    channel_type = ChannelType.TELEGRAM
    max_length = 4096
    supports_markdown = True
    supports_streaming = True

    def format_response(self, state: GraphState) -> dict[str, Any]:
        """Format response for Telegram with MarkdownV2 escaping."""
        parts = [state.answer]

        # Add compact sources
        sources_text = self._format_sources(state)
        if sources_text:
            parts.append(f"\n\nSources:\n{sources_text}")

        text = "\n".join(parts)
        text = self.truncate(text)

        return {
            "text": text,
            "parse_mode": "MarkdownV2",
            "metadata": {
                "run_id": state.run_id,
                "intent": str(state.intent),
                "confidence": self._format_confidence(state),
            },
        }

    def parse_incoming(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a Telegram webhook update.

        Handles both regular messages and callback queries.
        """
        message = raw.get("message", {})
        callback = raw.get("callback_query", {})

        if callback:
            user = callback.get("from", {})
            return {
                "query": callback.get("data", ""),
                "user_id": str(user.get("id", "unknown")),
                "metadata": {
                    "chat_id": callback.get("message", {}).get("chat", {}).get("id"),
                    "message_id": callback.get("message", {}).get("message_id"),
                    "channel": "telegram",
                    "is_callback": True,
                },
            }

        user = message.get("from", {})
        return {
            "query": message.get("text", ""),
            "user_id": str(user.get("id", "unknown")),
            "metadata": {
                "chat_id": message.get("chat", {}).get("id"),
                "message_id": message.get("message_id"),
                "first_name": user.get("first_name", ""),
                "channel": "telegram",
                "is_callback": False,
            },
        }

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = r"_*[]()~`>#+-=|{}.!"
        return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", text)
