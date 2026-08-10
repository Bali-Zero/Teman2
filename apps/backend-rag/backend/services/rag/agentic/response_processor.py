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

from backend.services.communication import (
    detect_language,
    has_emotional_content,
    is_procedural_question,
)
from backend.services.response.cleaner import clean_response

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

    # No verb list for this language -> do not reformat. Running the ENGLISH
    # list over a Russian answer is not a neutral default, it is a guess about
    # a language we have no vocabulary for.
    verbs = action_verbs.get(language)
    if not verbs:
        return text

    # Word-boundary, not substring (superscar #3): bare `in` makes the
    # Indonesian "isi" fire inside "revisi", "efisiensi", "administrasi".
    verb_re = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in verbs) + r")\w*", re.IGNORECASE)
    # No length floor. The old `len(s) > 20` was a proxy for "is this a real
    # step", and combined with the conservation guard below it turns a short
    # but genuine step ("Find the office", 15 chars) into a dropped sentence,
    # which then declines a list that is entirely steps. The "every sentence
    # must be actionable" rule is the real filter; a length is not.
    actionable_sentences = [s for s in sentences if verb_re.search(s)]

    # CONSERVATION GUARD. This function used to return ONLY the sentences it
    # liked, silently discarding every other sentence of a correct answer.
    # Measured 2026-08-10 on a 5-sentence procedural answer, in all three
    # supported languages: 56% / 57% / 61% of the answer deleted, and what
    # went with it was the Bali Zero service fee and the overstay penalty —
    # while the client received a tidy numbered list that reads COMPLETE.
    # Formatting may reorder nothing and drop nothing: if any substantive
    # sentence is not part of the list, leave the answer alone.
    substantive = [s for s in sentences if s.strip()]
    if len(actionable_sentences) != len(substantive):
        logger.debug(
            "[post_process] declining to renumber: %d of %d sentences are not steps, "
            "reformatting would drop the rest",
            len(substantive) - len(actionable_sentences),
            len(substantive),
        )
        return text

    if len(actionable_sentences) >= 2:
        # Format as numbered list
        return "\n".join([f"{i + 1}. {s.strip()}" for i, s in enumerate(actionable_sentences)])

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

    # Same five keys `detect_language()` emits, mirroring _APOLOGY_TEXTS /
    # _ACK_TEXTS in wa_outbox_worker. The table used to carry three and fall
    # back to English, so a Russian answer was searched for English keywords,
    # never matched, and was therefore always judged to be missing its
    # acknowledgment.
    acknowledgment_keywords = {
        "it": ["capisco", "tranquillo", "aiuto", "soluzione", "possibilità"],
        "en": ["understand", "don't worry", "help", "solution", "possible"],
        "id": ["mengerti", "tenang", "bantuan", "solusi", "kemungkinan"],
        "ru": ["понимаю", "не волнуйтесь", "помощь", "решение", "возможно"],
        "uk": ["розумію", "не хвилюйтеся", "допомога", "рішення", "можливо"],
    }

    keywords = acknowledgment_keywords.get(language)
    if not keywords:
        # Unknown language: we cannot tell whether the acknowledgment is there,
        # and claiming it is missing is what makes the caller prepend one.
        return True
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
        "ru": "Понимаю ваше беспокойство, но не волнуйтесь - почти для любой ситуации есть решение. ",
        "uk": "Розумію ваше занепокоєння, але не хвилюйтеся - майже для кожної ситуації є рішення. ",
    }

    # `detect_language()` also returns "auto" when no marker matched — a value
    # its own Literal did not admit until this diff. The old default was
    # ITALIAN, so an unrecognised language got an Italian sentence grafted onto
    # the front of its answer; measured reachable end-to-end on a Russian
    # message (lang='ru', emotional=True) before "ru" was added below. There is
    # no safe language to guess: prepend nothing rather than the wrong tongue.
    acknowledgment = acknowledgments.get(language)
    if not acknowledgment:
        return text

    # Don't add if already present
    if acknowledgment.lower()[:20] not in text.lower()[:200]:
        return acknowledgment + text

    return text
