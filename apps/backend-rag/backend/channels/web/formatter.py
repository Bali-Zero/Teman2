"""
Web Message Formatter.

Converts ChannelResponse to Web-specific formatting (rich Markdown).

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
from typing import Any

from backend.channels.base import ChannelResponse

logger = logging.getLogger(__name__)


class WebMessageFormatter:
    """Formats messages for web frontend (rich Markdown, no escaping needed)."""

    @staticmethod
    def format_response(response: ChannelResponse) -> str:
        """
        Format a ChannelResponse for web frontend.

        Args:
            response: Channel response to format

        Returns:
            Formatted message text (GitHub-flavored Markdown)
        """
        parts = []

        # Main text content
        if response.text:
            parts.append(response.text)

        # Add sources section (if available)
        if response.sources:
            sources_text = WebMessageFormatter._format_sources(response.sources)
            if sources_text:
                parts.append(f"\n\n## 📚 Fonti\n\n{sources_text}")

        # Add workflow section (if available)
        if response.workflow:
            workflow_text = WebMessageFormatter._format_workflow(response.workflow)
            if workflow_text:
                parts.append(f"\n\n## 📋 Piano d'azione\n\n{workflow_text}")

        return "\n".join(parts)

    @staticmethod
    def _format_sources(sources: list[dict[str, Any]]) -> str:
        """
        Format sources list for web.

        Args:
            sources: List of source dictionaries

        Returns:
            Formatted sources string
        """
        formatted_sources = []

        for idx, source in enumerate(sources, 1):
            title = source.get("title", "Documento")
            url = source.get("url")
            collection = source.get("collection", "")

            if url:
                formatted_sources.append(f"{idx}. [{title}]({url}) _({collection})_")
            else:
                formatted_sources.append(f"{idx}. {title} _({collection})_")

        return "\n".join(formatted_sources)

    @staticmethod
    def _format_workflow(workflow: dict[str, Any]) -> str:
        """
        Format workflow for web.

        Args:
            workflow: Workflow dictionary

        Returns:
            Formatted workflow string
        """
        name = workflow.get("name", "Workflow")
        steps = workflow.get("steps", [])

        if not steps:
            return f"**{name}**"

        # Format steps as numbered list
        formatted_steps = [f"**{name}:**\n"]
        for idx, step in enumerate(steps, 1):
            if isinstance(step, dict):
                step_text = step.get("description") or step.get("action", "Step")
            else:
                step_text = str(step)

            formatted_steps.append(f"{idx}. {step_text}")

        return "\n".join(formatted_steps)

    @staticmethod
    def format_thinking(thinking_text: str) -> str:
        """
        Format LLM thinking/reasoning for web.

        Args:
            thinking_text: LLM reasoning text

        Returns:
            Formatted thinking (blockquote)
        """
        return f"> 💭 {thinking_text}"

    @staticmethod
    def format_tool_call(tool_name: str, tool_args: dict[str, Any] | None = None) -> str:
        """
        Format tool call notification for web.

        Args:
            tool_name: Name of tool being called
            tool_args: Optional tool arguments

        Returns:
            Formatted tool call message
        """
        if tool_args:
            args_str = ", ".join(f"{k}={v}" for k, v in list(tool_args.items())[:2])
            return f"🔧 `{tool_name}({args_str})`"
        else:
            return f"🔧 `{tool_name}()`"

    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format error message for web.

        Args:
            error_message: Error message

        Returns:
            Formatted error (bold + emoji)
        """
        return f"❌ **Errore:** {error_message}"

    @staticmethod
    def format_status(status: str) -> str:
        """
        Format status message for web.

        Args:
            status: Status text

        Returns:
            Formatted status
        """
        status_emojis = {
            "processing": "⏳",
            "thinking": "💭",
            "searching": "🔍",
            "analyzing": "🔬",
            "complete": "✅",
            "error": "❌",
        }

        emoji = status_emojis.get(status.lower(), "📍")
        return f"{emoji} {status.capitalize()}..."
