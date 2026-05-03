"""Base channel adapter — ABC for multi-channel output formatting.

Each channel has different constraints:
  - Web:      Rich markdown, unlimited length, progressive streaming
  - Telegram: Full markdown, 4096 char limit, progressive streaming
  - WhatsApp: Limited markdown, 1600 char limit, no streaming
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from nuzantara_schemas.state import ChannelType, GraphState


class ChannelAdapter(ABC):
    """Abstract base for channel-specific message formatting."""

    channel_type: ChannelType
    max_length: int
    supports_markdown: bool
    supports_streaming: bool

    @abstractmethod
    def format_response(self, state: GraphState) -> dict[str, Any]:
        """Format a completed GraphState into a channel-specific response.

        Returns a dict with at minimum:
          - "text": the formatted response text
          - "metadata": any channel-specific metadata
        """
        ...

    @abstractmethod
    def parse_incoming(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse an incoming message from this channel into a normalized format.

        Returns a dict with:
          - "query": the user's message text
          - "user_id": channel-specific user identifier
          - "metadata": any extra channel data
        """
        ...

    def truncate(self, text: str) -> str:
        """Truncate text to channel's max length with ellipsis."""
        if len(text) <= self.max_length:
            return text
        return text[: self.max_length - 3] + "..."

    def _format_sources(self, state: GraphState) -> str:
        """Format sources as a compact list."""
        if not state.sources:
            return ""
        lines = []
        for i, src in enumerate(state.sources[:5], 1):
            title = src.get("title", src.get("id", f"Source {i}"))
            lines.append(f"{i}. {title}")
        return "\n".join(lines)

    def _format_confidence(self, state: GraphState) -> str:
        """Format confidence as a simple indicator."""
        overall = state.confidence.overall
        if overall >= 0.8:
            return "High confidence"
        elif overall >= 0.5:
            return "Medium confidence"
        else:
            return "Low confidence"
