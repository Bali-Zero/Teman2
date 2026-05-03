"""
Telegram Message Formatter.

Converts ChannelResponse to Telegram-specific formatting.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
from typing import Any

from backend.channels.base import ChannelResponse

logger = logging.getLogger(__name__)


class TelegramMessageFormatter:
    """Formats messages for Telegram Bot API."""

    @staticmethod
    def format_response(response: ChannelResponse) -> str:
        """
        Format a ChannelResponse for Telegram (Markdown).

        Args:
            response: Channel response to format

        Returns:
            Formatted message text (Telegram Markdown)
        """
        parts = []

        # Main text content
        if response.text:
            parts.append(response.text)

        # Add sources section (if available)
        if response.sources:
            sources_text = TelegramMessageFormatter._format_sources(response.sources)
            if sources_text:
                parts.append(f"\n\n📚 *Fonti:*\n{sources_text}")

        # Add workflow section (if available)
        if response.workflow:
            workflow_text = TelegramMessageFormatter._format_workflow(response.workflow)
            if workflow_text:
                parts.append(f"\n\n📋 *Piano d'azione:*\n{workflow_text}")

        return "\n".join(parts)

    @staticmethod
    def _format_sources(sources: list[dict[str, Any]]) -> str:
        """
        Format sources list for Telegram.

        Args:
            sources: List of source dictionaries

        Returns:
            Formatted sources string
        """
        formatted_sources = []

        for idx, source in enumerate(sources[:5], 1):  # Max 5 sources
            title = source.get("title", "Documento")
            url = source.get("url")

            if url:
                # Telegram Markdown: [text](url)
                formatted_sources.append(f"{idx}. [{title}]({url})")
            else:
                formatted_sources.append(f"{idx}. {title}")

        return "\n".join(formatted_sources)

    @staticmethod
    def _format_workflow(workflow: dict[str, Any]) -> str:
        """
        Format workflow for Telegram.

        Args:
            workflow: Workflow dictionary

        Returns:
            Formatted workflow string
        """
        name = workflow.get("name", "Workflow")
        steps = workflow.get("steps", [])

        if not steps:
            return f"*{name}*"

        # Format steps as numbered list
        formatted_steps = [f"*{name}:*"]
        for idx, step in enumerate(steps[:10], 1):  # Max 10 steps
            if isinstance(step, dict):
                step_text = step.get("description") or step.get("action", "Step")
            else:
                step_text = str(step)

            formatted_steps.append(f"{idx}. {step_text}")

        return "\n".join(formatted_steps)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escape special characters for Telegram Markdown.

        Telegram Markdown special chars: _ * [ ] ( ) ~ ` > # + - = | { } . !

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        # Only escape characters that break Markdown parsing
        # Common pattern: escape _ and * unless part of formatting
        escape_chars = [
            "_",
            "*",
            "[",
            "]",
            "(",
            ")",
            "~",
            "`",
            ">",
            "#",
            "+",
            "-",
            "=",
            "|",
            "{",
            "}",
            ".",
            "!",
        ]

        escaped = text
        for char in escape_chars:
            # Simple escape - precede with backslash
            escaped = escaped.replace(char, f"\\{char}")

        return escaped

    @staticmethod
    def format_thinking(thinking_text: str) -> str:
        """
        Format LLM thinking/reasoning for Telegram.

        Args:
            thinking_text: LLM reasoning text

        Returns:
            Formatted thinking (italic)
        """
        return f"_💭 {thinking_text}_"

    @staticmethod
    def format_tool_call(tool_name: str, tool_args: dict[str, Any] | None = None) -> str:
        """
        Format tool call notification for Telegram.

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
        Format error message for Telegram.

        Args:
            error_message: Error message

        Returns:
            Formatted error (bold + emoji)
        """
        return f"❌ *Errore:* {error_message}"

    @staticmethod
    def format_status(status: str) -> str:
        """
        Format status message for Telegram.

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
