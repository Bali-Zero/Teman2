"""Backward-compat shim — all symbols moved to enrichment.py.

Note: generate_conversation_title is re-implemented here as a local wrapper
so that tests can patch _generate_via_ollama / _generate_via_gemini in this
module's namespace (original names used by the test suite).
"""
from __future__ import annotations

import logging

from backend.services.crm.enrichment import (  # noqa: F401
    _TITLE_PROMPT,  # noqa: F401
    _clean_title,
)
from backend.services.crm.enrichment import (
    _generate_title_via_gemini as _generate_via_gemini,
)
from backend.services.crm.enrichment import (
    _generate_title_via_ollama as _generate_via_ollama,
)

logger = logging.getLogger(__name__)


async def generate_conversation_title(
    conversation_id: str, first_user_message: str, max_length: int = 50,
) -> str | None:
    """Wrapper that delegates to module-local aliases so tests can patch them."""
    if not first_user_message or len(first_user_message.strip()) < 10:
        logger.info(
            f"Skipping title generation for conv {conversation_id}: "
            f"message too short ({len(first_user_message)} chars)",
        )
        return None

    prompt = _TITLE_PROMPT.format(max_length=max_length, message=first_user_message[:200])

    title = await _generate_via_ollama(conversation_id, prompt, max_length)
    if title:
        return title

    title = await _generate_via_gemini(conversation_id, prompt, max_length)
    if title:
        return title

    logger.warning(f"All title generation methods failed for conv {conversation_id}")
    return None
