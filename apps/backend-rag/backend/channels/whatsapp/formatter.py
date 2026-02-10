"""
WhatsApp Message Formatter.

Converts ChannelResponse to WhatsApp-specific formatting (limited Markdown).

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
from typing import Any

from backend.channels.base import ChannelResponse

logger = logging.getLogger(__name__)


class WhatsAppMessageFormatter:
    """Formats messages for WhatsApp (limited Markdown support)."""

    @staticmethod
    def format_response(response: ChannelResponse) -> str:
        """
        Format a ChannelResponse for WhatsApp.

        WhatsApp supports: *bold*, _italic_, ~strikethrough~, ```code```

        Args:
            response: Channel response to format

        Returns:
            Formatted message text (WhatsApp Markdown)
        """
        parts = []

        # Main text content
        if response.text:
            parts.append(response.text)

        # Add sources section (if available)
        if response.sources:
            sources_text = WhatsAppMessageFormatter._format_sources(response.sources)
            if sources_text:
                parts.append(f"\n\n*📚 Fonti:*\n{sources_text}")

        # Add workflow section (if available)
        if response.workflow:
            workflow_text = WhatsAppMessageFormatter._format_workflow(response.workflow)
            if workflow_text:
                parts.append(f"\n\n*📋 Piano:*\n{workflow_text}")

        return "\n".join(parts)

    @staticmethod
    def _format_sources(sources: list[dict[str, Any]]) -> str:
        """Format sources list for WhatsApp."""
        formatted_sources = []

        for idx, source in enumerate(sources[:5], 1):  # Max 5 sources
            title = source.get("title", "Documento")
            url = source.get("url")

            if url:
                formatted_sources.append(f"{idx}. {title}\n   {url}")
            else:
                formatted_sources.append(f"{idx}. {title}")

        return "\n".join(formatted_sources)

    @staticmethod
    def _format_workflow(workflow: dict[str, Any]) -> str:
        """Format workflow for WhatsApp."""
        name = workflow.get("name", "Workflow")
        steps = workflow.get("steps", [])

        if not steps:
            return f"*{name}*"

        # Format steps as numbered list
        formatted_steps = [f"*{name}:*"]
        for idx, step in enumerate(steps[:10], 1):
            if isinstance(step, dict):
                step_text = step.get("description") or step.get("action", "Step")
            else:
                step_text = str(step)

            formatted_steps.append(f"{idx}. {step_text}")

        return "\n".join(formatted_steps)

    @staticmethod
    def format_thinking(thinking_text: str) -> str:
        """Format LLM thinking for WhatsApp."""
        return f"_💭 {thinking_text}_"

    @staticmethod
    def format_error(error_message: str) -> str:
        """Format error message for WhatsApp."""
        return f"❌ *Errore:* {error_message}"
