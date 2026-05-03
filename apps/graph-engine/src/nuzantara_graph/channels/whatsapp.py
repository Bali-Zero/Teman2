"""WhatsApp channel adapter — limited markdown, 1600 char limit, no streaming."""

from __future__ import annotations

from typing import Any

from nuzantara_graph.channels.base import ChannelAdapter
from nuzantara_schemas.state import ChannelType, GraphState


class WhatsAppChannelAdapter(ChannelAdapter):
    """WhatsApp Business API — limited formatting, 1600 char limit."""

    channel_type = ChannelType.WHATSAPP
    max_length = 1600
    supports_markdown = False
    supports_streaming = False

    def format_response(self, state: GraphState) -> dict[str, Any]:
        """Format response for WhatsApp — plain text, concise."""
        parts = [self._strip_markdown(state.answer)]

        # Compact sources (only first 3 due to length limits)
        if state.sources:
            src_lines = []
            for i, src in enumerate(state.sources[:3], 1):
                title = src.get("title", src.get("id", f"Source {i}"))
                src_lines.append(f"{i}. {title}")
            parts.append("\nSources: " + ", ".join(src_lines))

        text = "\n".join(parts)
        text = self.truncate(text)

        return {
            "text": text,
            "metadata": {
                "run_id": state.run_id,
                "intent": str(state.intent),
            },
        }

    def parse_incoming(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a WhatsApp Cloud API webhook.

        Handles text messages from the messages array.
        """
        entry = raw.get("entry", [{}])[0] if raw.get("entry") else {}
        changes = entry.get("changes", [{}])[0] if entry.get("changes") else {}
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {
                "query": "",
                "user_id": "unknown",
                "metadata": {"channel": "whatsapp", "empty": True},
            }

        msg = messages[0]
        return {
            "query": msg.get("text", {}).get("body", ""),
            "user_id": msg.get("from", "unknown"),
            "metadata": {
                "wa_id": msg.get("id"),
                "timestamp": msg.get("timestamp"),
                "phone_number_id": value.get("metadata", {}).get(
                    "phone_number_id"
                ),
                "channel": "whatsapp",
            },
        }

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting for plain text output."""
        import re

        # Remove bold/italic markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        # Remove headers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
        # Remove link formatting but keep text
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        return text.strip()
