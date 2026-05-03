"""Web channel adapter — rich markdown, unlimited length, streaming support."""

from __future__ import annotations

from typing import Any

from nuzantara_graph.channels.base import ChannelAdapter
from nuzantara_schemas.state import ChannelType, GraphState


class WebChannelAdapter(ChannelAdapter):
    """Web/SSE channel — richest output format."""

    channel_type = ChannelType.WEB
    max_length = 100_000  # Effectively unlimited
    supports_markdown = True
    supports_streaming = True

    def format_response(self, state: GraphState) -> dict[str, Any]:
        """Format response with rich markdown, sources, and confidence."""
        parts = [state.answer]

        # Add sources section
        sources_text = self._format_sources(state)
        if sources_text:
            parts.append(f"\n\n---\n**Sources:**\n{sources_text}")

        # Add confidence indicator
        confidence_text = self._format_confidence(state)
        parts.append(f"\n\n*{confidence_text}*")

        text = "\n".join(parts)

        return {
            "text": text,
            "metadata": {
                "run_id": state.run_id,
                "intent": str(state.intent),
                "domain": state.domain,
                "confidence": state.confidence.model_dump(),
                "token_usage": {
                    "total_tokens": state.total_tokens,
                    "total_cost_usd": state.total_cost_usd,
                },
            },
        }

    def parse_incoming(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a web request — already structured JSON."""
        return {
            "query": raw.get("query", raw.get("message", "")),
            "user_id": raw.get("user_id", "anonymous"),
            "metadata": {
                "session_id": raw.get("session_id"),
                "channel": "web",
            },
        }
