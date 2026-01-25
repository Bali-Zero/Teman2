"""
Conversation Title Generator Service

Generates concise, meaningful titles for chat conversations using LLM.
Uses Anthropic Claude for title generation with cost optimization.

Cost: ~$0.000006 per title (Claude Haiku)
Latency: <2s (non-blocking async)

Author: Nuzantara Team
Date: 2026-01-22
"""

import logging
import os

import anthropic

logger = logging.getLogger(__name__)


async def generate_conversation_title(
    conversation_id: str, first_user_message: str, max_length: int = 50
) -> str | None:
    """
    Generate concise title from first user message.

    Uses Claude Haiku for cost-effective title generation.
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
        - Model: Claude Haiku ($0.25/$1.25 per MTok)
        - Total: ~$0.000006 per title

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

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping title generation")
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
        # Create Anthropic client
        client = anthropic.Anthropic(api_key=api_key)

        logger.info(f"Generating title for conversation {conversation_id}...")

        # Call Claude Haiku (cost-effective)
        message = client.messages.create(
            model="claude-haiku-4-20250514",  # Haiku for cost optimization
            max_tokens=30,  # Short output expected
            temperature=0.3,  # Low creativity for consistency
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract title
        title = message.content[0].text.strip()[:max_length]

        # Log success
        logger.info(
            f'✅ Generated title for conv {conversation_id}: "{title}" '
            f"(input: {message.usage.input_tokens} tokens, "
            f"output: {message.usage.output_tokens} tokens)"
        )

        return title

    except anthropic.APIError as e:
        logger.warning(f"Anthropic API error generating title for conv {conversation_id}: {e}")
        return None

    except Exception as e:
        logger.error(
            f"Unexpected error generating title for conv {conversation_id}: {e}", exc_info=True
        )
        return None
