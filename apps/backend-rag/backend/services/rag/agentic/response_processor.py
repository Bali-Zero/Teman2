"""
Response Post-Processing for Agentic RAG

This module handles cleaning and formatting of AI responses:
- Clean internal reasoning patterns (THOUGHT:, ACTION:, Observation:)
- Enforce language detection
- Format procedural questions as numbered lists
- Add emotional acknowledgment when needed
- Verify responses against source context

Key Features:
- Integration with response cleaner service
- Communication rules enforcement
- Emotional attunement
- Format detection and transformation
"""

import logging
import re

from services.communication import (
    detect_language,
    has_emotional_content,
    is_procedural_question,
)
from services.response.cleaner import clean_response

logger = logging.getLogger(__name__)


def post_process_response(response: str, query: str) -> str:
    """
    Post-process response to enforce communication rules:
    - Clean internal reasoning patterns
    - Ensure correct language
    - Format procedural questions as numbered lists
    - Add emotional acknowledgment if needed

    Args:
        response: Raw AI response
        query: Original user query

    Returns:
        Cleaned and formatted response
    """
    # Step 1: Clean internal reasoning patterns
    cleaned = clean_response(response)

    # Step 2: Detect query characteristics
    detected_language = detect_language(query)
    is_procedural = is_procedural_question(query)
    has_emotional = has_emotional_content(query)

    # Step 3: Check if response needs procedural formatting
    if is_procedural and not _has_numbered_list(cleaned):
        cleaned = _format_as_numbered_list(cleaned, detected_language)

    # Step 4: Check if response needs emotional acknowledgment
    if has_emotional and not _has_emotional_acknowledgment(cleaned, detected_language):
        cleaned = _add_emotional_acknowledgment(cleaned, detected_language)

    return cleaned.strip()


def _has_numbered_list(text: str) -> bool:
    """Check if text already contains a numbered list"""
    # Look for patterns like "1.", "2.", "1)", "2)", etc.
    pattern = r"\b[1-9][\.\)]\s+"
    return bool(re.search(pattern, text))


def _format_as_numbered_list(text: str, language: str) -> str:
    """
    Format text as numbered list if it contains steps.

    Args:
        text: Text to format
        language: Language code (it, en, id)

    Returns:
        Formatted text with numbered steps
    """
    # Try to detect sentences that look like steps
    sentences = re.split(r"[.!?]\s+", text)

    # Filter sentences that look actionable (contain verbs like "prepare", "find", "apply", etc.)
    action_verbs = {
        "it": ["prepara", "trova", "applica", "compila", "invia", "attendi", "ritira"],
        "en": ["prepare", "find", "apply", "fill", "submit", "wait", "collect"],
        "id": ["siapkan", "cari", "ajukan", "isi", "kirim", "tunggu", "ambil"],
    }

    verbs = action_verbs.get(language, action_verbs["en"])
    actionable_sentences = [
        s for s in sentences if any(verb in s.lower() for verb in verbs) and len(s) > 20
    ]

    if len(actionable_sentences) >= 2:
        # Format as numbered list
        formatted = "\n".join([f"{i + 1}. {s.strip()}" for i, s in enumerate(actionable_sentences)])
        return formatted

    return text


def _has_emotional_acknowledgment(text: str, language: str) -> bool:
    """
    Check if text starts with emotional acknowledgment.

    Args:
        text: Text to check
        language: Language code (it, en, id)

    Returns:
        True if emotional acknowledgment is present
    """
    text_lower = text.lower()[:200]  # Check first 200 chars

    acknowledgment_keywords = {
        "it": ["capisco", "tranquillo", "aiuto", "soluzione", "possibilità"],
        "en": ["understand", "don't worry", "help", "solution", "possible"],
        "id": ["mengerti", "tenang", "bantuan", "solusi", "kemungkinan"],
    }

    keywords = acknowledgment_keywords.get(language, acknowledgment_keywords["en"])
    return any(keyword in text_lower for keyword in keywords)


def _add_emotional_acknowledgment(text: str, language: str) -> str:
    """
    Add emotional acknowledgment at the beginning of response.

    Args:
        text: Text to enhance
        language: Language code (it, en, id)

    Returns:
        Text with emotional acknowledgment prepended
    """
    acknowledgments = {
        "it": "Capisco la frustrazione, ma tranquillo - quasi ogni situazione ha una soluzione. ",
        "en": "I understand the frustration, but don't worry - almost every situation has a solution. ",
        "id": "Saya mengerti frustrasinya, tapi tenang - hampir setiap situasi ada solusinya. ",
    }

    acknowledgment = acknowledgments.get(language, acknowledgments["it"])

    # Don't add if already present
    if acknowledgment.lower()[:20] not in text.lower()[:200]:
        return acknowledgment + text

    return text
