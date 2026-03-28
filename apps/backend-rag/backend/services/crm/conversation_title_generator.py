"""
Conversation Title Generator Service

Generates concise, meaningful titles for chat conversations.
Primary: Local Ollama qwen3.5:9b (free, <0.5s)
Fallback: Google Gemini Flash (API, ~$0.000003 per title)

Author: Nuzantara Team
Date: 2026-02-19
Updated: 2026-03-08 — Ollama-first with Gemini fallback
"""

import logging

from backend.llm.ollama_client import MODEL_FAST, ollama_chat

logger = logging.getLogger(__name__)

# Shared prompt template
_TITLE_PROMPT = """Generate a concise, professional title (max {max_length} characters) for a conversation starting with this message:

"{message}"

Requirements:
- Professional and clear
- Under {max_length} characters
- No quotes or special formatting
- Capture main topic/intent
- Language: Match the input language (Italian, English, etc.)

Return ONLY the title text, nothing else."""


async def generate_conversation_title(
    conversation_id: str, first_user_message: str, max_length: int = 50,
) -> str | None:
    """
    Generate concise title from first user message.

    Tries local Ollama first (free, fast), falls back to Gemini Flash.
    Fails gracefully - returns None if both fail.

    Args:
        conversation_id: Conversation ID for logging
        first_user_message: First message from user
        max_length: Maximum title length (default 50 chars)

    Returns:
        Generated title string, or None if generation fails
    """
    # Validate input
    if not first_user_message or len(first_user_message.strip()) < 10:
        logger.info(
            f"Skipping title generation for conv {conversation_id}: "
            f"message too short ({len(first_user_message)} chars)",
        )
        return None

    prompt = _TITLE_PROMPT.format(
        max_length=max_length,
        message=first_user_message[:200],
    )

    # --- Try 1: Local Ollama (free, <0.5s) ---
    title = await _generate_via_ollama(conversation_id, prompt, max_length)
    if title:
        return title

    # --- Try 2: Gemini Flash API fallback ---
    title = await _generate_via_gemini(conversation_id, prompt, max_length)
    if title:
        return title

    logger.warning(f"All title generation methods failed for conv {conversation_id}")
    return None


async def _generate_via_ollama(conversation_id: str, prompt: str, max_length: int) -> str | None:
    """Generate title using local Ollama qwen3.5:9b."""
    try:
        logger.info(f"Generating title for conv {conversation_id} via Ollama ({MODEL_FAST})...")

        result = await ollama_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_FAST,
            temperature=0.3,
            max_tokens=60,
            timeout=10.0,
        )

        if not result:
            logger.debug(f"Ollama unavailable for conv {conversation_id}, trying Gemini")
            return None

        title = _clean_title(result, max_length)
        logger.info(f'✅ Generated title for conv {conversation_id} via Ollama: "{title}"')
        return title

    except Exception as e:
        logger.warning(f"Ollama title generation error for conv {conversation_id}: {e}")
        return None


async def _generate_via_gemini(conversation_id: str, prompt: str, max_length: int) -> str | None:
    """Fallback: Generate title using Gemini Flash API."""
    try:
        from backend.llm.genai_client import get_genai_client

        client = get_genai_client()
        if not client or not client.is_available:
            logger.warning("GenAI client not available, skipping Gemini fallback")
            return None

        logger.info(f"Generating title for conv {conversation_id} via Gemini Flash...")

        result = await client.generate_content(
            contents=prompt,
            model="gemini-2.0-flash-lite",
            max_output_tokens=30,
            temperature=0.3,
        )

        if not result or not result.get("text"):
            logger.warning(f"Empty response from Gemini for conv {conversation_id}")
            return None

        title = _clean_title(result["text"], max_length)
        logger.info(f'✅ Generated title for conv {conversation_id} via Gemini: "{title}"')
        return title

    except Exception as e:
        logger.warning(f"Gemini title generation error for conv {conversation_id}: {e}")
        return None


def _clean_title(raw: str, max_length: int) -> str:
    """Clean and truncate generated title."""
    title = raw.strip().strip('"').strip("'").strip()
    # Remove thinking tags if model outputs them
    if "<think>" in title:
        title = title.split("</think>")[-1].strip()
    return title[:max_length]
