"""
Context Window Manager - Intelligent conversation history management
Prevents context overflow by keeping only recent messages with automatic summarization
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContextWindowManager:
    """
    Manages conversation history to prevent context overflow

    Strategy:
    - Keep last 10-15 messages in full detail
    - Summarize older messages into context summary
    - Total context stays within safe limits
    """

    def __init__(self, max_messages: int = 10, summary_threshold: int = 15):
        """
        Initialize context window manager

        Args:
            max_messages: Maximum number of recent messages to keep in full
            summary_threshold: Number of messages that triggers summarization
        """
        self.max_messages = max_messages
        self.summary_threshold = summary_threshold
        # Use ZANTARA AI for summarization (via ZantaraAIClient)
        try:
            from llm.zantara_ai_client import ZantaraAIClient

            self.zantara_client = ZantaraAIClient()
        except Exception as e:
            logger.warning(f"⚠️ ZANTARA AI not available for summarization: {e}")
            self.zantara_client = None
        logger.info(
            f"✅ ContextWindowManager initialized (max: {max_messages}, threshold: {summary_threshold})"
        )

    def trim_conversation_history(
        self, conversation_history: list[dict], current_summary: str | None = None
    ) -> dict:
        """
        Trim conversation history to prevent context overflow

        Args:
            conversation_history: Full conversation history
            current_summary: Existing summary of older messages (if any)

        Returns:
            {
                "trimmed_messages": List[Dict],  # Recent messages to include
                "needs_summarization": bool,      # Whether old messages should be summarized
                "messages_to_summarize": List[Dict],  # Messages that should be summarized
                "context_summary": str            # Current summary (if exists)
            }
        """
        if not conversation_history:
            return {
                "trimmed_messages": [],
                "needs_summarization": False,
                "messages_to_summarize": [],
                "context_summary": current_summary or "",
            }

        total_messages = len(conversation_history)

        # CASE 1: Short conversation - keep everything
        if total_messages <= self.max_messages:
            logger.info(f"📊 [Context] Conversation short ({total_messages} msgs) - keeping all")
            return {
                "trimmed_messages": conversation_history,
                "needs_summarization": False,
                "messages_to_summarize": [],
                "context_summary": current_summary or "",
            }

        # CASE 2: Medium conversation - approaching limit
        elif total_messages <= self.summary_threshold:
            logger.info(
                f"📊 [Context] Conversation medium ({total_messages} msgs) - approaching limit"
            )
            # Keep recent messages, but warn
            recent_messages = conversation_history[-self.max_messages :]
            return {
                "trimmed_messages": recent_messages,
                "needs_summarization": False,
                "messages_to_summarize": [],
                "context_summary": current_summary or "",
            }

        # CASE 3: Long conversation - needs summarization
        else:
            logger.info(
                f"📊 [Context] Conversation long ({total_messages} msgs) - triggering summarization"
            )

            # Keep last max_messages in full
            recent_messages = conversation_history[-self.max_messages :]

            # Older messages need summarization
            older_messages = conversation_history[: -self.max_messages]

            return {
                "trimmed_messages": recent_messages,
                "needs_summarization": True,
                "messages_to_summarize": older_messages,
                "context_summary": current_summary or "",
            }

    def build_summarization_prompt(self, messages: list[dict]) -> str:
        """
        Build prompt for summarizing older messages

        Args:
            messages: Messages to summarize

        Returns:
            Prompt for AI to generate summary
        """
        # Format messages for summarization
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted_messages.append(
                f"{role.upper()}: {content[:200]}..."
            )  # Truncate long messages

        conversation_text = "\n\n".join(formatted_messages)

        prompt = f"""Summarize the following conversation history concisely (2-3 sentences):

{conversation_text}

Focus on:
- Main topics discussed
- Key decisions or conclusions
- Important context for future messages

Summary:"""

        return prompt

    def get_context_status(self, conversation_history: list[dict]) -> dict:
        """
        Get current context window status

        Args:
            conversation_history: Current conversation history

        Returns:
            Status information about context window
        """
        total_messages = len(conversation_history)

        # Calculate usage percentage
        usage_percentage = (total_messages / self.summary_threshold) * 100

        # Determine status
        if total_messages <= self.max_messages:
            status = "healthy"
            color = "green"
        elif total_messages <= self.summary_threshold:
            status = "approaching_limit"
            color = "yellow"
        else:
            status = "needs_summarization"
            color = "red"

        return {
            "total_messages": total_messages,
            "max_messages": self.max_messages,
            "summary_threshold": self.summary_threshold,
            "usage_percentage": round(usage_percentage, 1),
            "status": status,
            "color": color,
            "messages_until_summarization": max(0, self.summary_threshold - total_messages),
        }

    def inject_summary_into_history(self, recent_messages: list[dict], summary: str) -> list[dict]:
        """
        Inject summary of older messages at the beginning of conversation

        Args:
            recent_messages: Recent messages to keep
            summary: Summary of older messages

        Returns:
            Messages with summary injected
        """
        if not summary:
            return recent_messages

        # Create summary message
        summary_message = {
            "role": "system",
            "content": f"[Earlier conversation summary]: {summary}",
        }

        # Inject at beginning
        return [summary_message] + recent_messages

    async def generate_summary(
        self, messages: list[dict], existing_summary: str | None = None
    ) -> str:
        """
        Generate conversation summary using ZANTARA AI (fast & cheap)

        Args:
            messages: Messages to summarize
            existing_summary: Previous summary to build upon (optional)

        Returns:
            Summary text (2-3 sentences)
        """
        if not self.zantara_client:
            logger.warning("⚠️ [Summary] ZANTARA AI client not available, cannot generate summary")
            return existing_summary or "Earlier conversation covered various topics."

        # Build summarization prompt
        prompt = self.build_summarization_prompt(messages)

        # If there's an existing summary, mention it for continuity
        if existing_summary:
            prompt = f"""Previous summary: {existing_summary}

{prompt}

Update the summary to include both the previous context and new messages."""

        # Call ZANTARA AI for fast summarization
        try:
            logger.info(f"📝 [Summary] Generating summary for {len(messages)} messages...")

            summary = await self.zantara_client.generate_text(
                prompt=prompt, max_tokens=150, temperature=0.3
            )

            logger.info(f"✅ [Summary] Generated ({len(summary)} chars)")
            return summary.strip()

        except Exception as e:
            logger.error(f"❌ [Summary] Generation failed: {e}")
            return (
                existing_summary
                or "Previous conversation context (summary generation unavailable)."
            )

    def format_summary_for_display(self, summary: str, stats: dict[str, int]) -> dict[str, Any]:
        """
        Format summary for frontend display

        Args:
            summary: Summary text
            stats: Conversation statistics (total_messages, messages_in_context, etc.)

        Returns:
            Formatted summary object:
            {
                "summary": str,
                "stats": {...},
                "timestamp": str
            }
        """
        from datetime import datetime

        return {
            "summary": summary,
            "stats": {
                "total_messages": stats.get("total_messages", 0),
                "messages_in_context": stats.get("messages_in_context", 0),
                "summary_active": bool(summary),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class AdvancedContextWindowManager:
    """
    Advanced context manager with token-based trimming and summarization.
    """

    def __init__(
        self,
        max_tokens: int = 6000,
        recent_window_tokens: int = 3000,
        summary_max_tokens: int = 500,
    ):
        self.max_tokens = max_tokens
        self.recent_window_tokens = recent_window_tokens
        self.summary_max_tokens = summary_max_tokens
        try:
            # import tiktoken
            # self.tokenizer = tiktoken.get_encoding("cl100k_base")
            self.tokenizer = None # Force fallback to character estimation to prevent crashes
        except ImportError:
            self.tokenizer = None
            logger.warning("⚠️ tiktoken not found, using character estimation")

    def count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text) // 4  # Rough estimation

    async def process_conversation_history(
        self, conversation_history: list[dict], system_prompt: str, current_query: str
    ) -> dict:
        """
        Process history to fit within token limits.
        """
        if not conversation_history:
            return {
                "messages": [],
                "formatted_context": "",
                "stats": {"total_messages": 0, "tokens": 0},
            }

        # Calculate available tokens
        system_tokens = self.count_tokens(system_prompt)
        query_tokens = self.count_tokens(current_query)
        available_tokens = self.max_tokens - system_tokens - query_tokens - 500  # Buffer

        current_tokens = 0
        kept_messages = []

        # Process from newest to oldest
        for msg in reversed(conversation_history):
            content = msg.get("content", "")
            msg_tokens = self.count_tokens(content)

            if current_tokens + msg_tokens > available_tokens:
                break

            kept_messages.insert(0, msg)
            current_tokens += msg_tokens

        # Format context string
        formatted_context = ""
        for msg in kept_messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            formatted_context += f"{role}: {content}\n\n"

        return {
            "messages": kept_messages,
            "formatted_context": formatted_context,
            "stats": {
                "total_messages": len(conversation_history),
                "messages_in_context": len(kept_messages),
                "tokens": current_tokens,
            },
        }
