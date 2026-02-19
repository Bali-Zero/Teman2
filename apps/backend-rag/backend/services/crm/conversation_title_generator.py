"""
Conversation Title Generator Service

Generates concise, meaningful titles for chat conversations using LLM.
Uses Google Gemini Flash for title generation.

Cost: ~$0.000003 per title (Gemini Flash)
Latency: <2s (non-blocking async)

Author: Nuzantara Team
Date: 2026-02-19
"""

import logging
import os

from backend.llm.genai_client import get_genai_client

logger = logging.getLogger(__name__)


async def generate_conversation_title(
    conversation_id: str, first_user_message: str, max_length: int = 50
) -> str | None:
    """
    Generate concise title from first user message.

    Uses Gemini Flash for cost-effective title generation.
    Fails gracefully - returns None if generation fails.

    Args:
        conversation_id: Conversation ID for logging
        first_user_message: First message from user
        max_length: Maximum title length (default 50 chars)

    Returns:
        Generated title string, or None if generation fails

    Cost Analysis:
        - Input: ~100 tokens (prompt + message)
        - Output: ~20 tokens (title)
        - Model: Gemini Flash (included in free tier / very low cost)
        - Total: ~$0.000003 per title

    Example:
        >>> title = await generate_conversation_title(
        ...     "conv_123",
        ...     "Come aprire una PT PMA a Bali?"
        ... )
        >>> # Returns: "Apertura PT PMA a Bali"
    """
    # Validate input
    if not first_user_message or len(first_user_message.strip()) < 10:
        logger.info(
            f"Skipping title generation for conv {conversation_id}: "
            f"message too short ({len(first_user_message)} chars)"
        )
        return None

    # Build prompt
    prompt = f"""Generate a concise, professional title (max {max_length} characters) for a conversation starting with this message:

"{first_user_message[:200]}"

Requirements:
- Professional and clear
- Under {max_length} characters
- No quotes or special formatting
- Capture main topic/intent
- Language: Match the input language (Italian, English, etc.)

Return ONLY the title text, nothing else."""

    try:
        client = get_genai_client()
        if not client or not client.is_available:
            logger.warning("GenAI client not available, skipping title generation")
            return None

        logger.info(f"Generating title for conversation {conversation_id}...")

        # Call Gemini Flash
        result = await client.generate_content(
            contents=prompt,
            model="gemini-2.0-flash-001",
            max_output_tokens=30,
            temperature=0.3,
        )

        if not result or not result.get("text"):
            logger.warning(f"Empty response from Gemini for conv {conversation_id}")
            return None

        # Extract title
        title = result["text"].strip()[:max_length]

        # Log success
        logger.info(f'✅ Generated title for conv {conversation_id}: "{title}"')

        return title

    except Exception as e:
        logger.warning(f"Error generating title for conv {conversation_id}: {e}")
        return None
