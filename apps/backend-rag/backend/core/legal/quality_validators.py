"""
Quality Validation Utilities
Functions for OCR quality assessment and ayat validation
"""

import hashlib
import re
from typing import Any


def calculate_text_fingerprint(text: str) -> str:
    """
    Generate SHA256 hash of normalized text for OCR dedup.

    Normalization removes:
    - Case differences (lowercase)
    - Extra whitespace (collapse to single space)
    - Line breaks (normalize to spaces)

    Args:
        text: Raw text

    Returns:
        16-char hex fingerprint
    """
    # Normalize: lowercase, collapse whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())

    # SHA256 hash, take first 16 chars
    fingerprint = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    return fingerprint


def detect_placeholders(text: str) -> bool:
    """
    Detect OCR placeholders indicating incomplete text.

    Common patterns:
    - ". . ." (3+ dots with spaces)
    - "…" (ellipsis character)
    - "[...]"
    - "____" (4+ underscores)

    Args:
        text: Text to check

    Returns:
        True if placeholders found
    """
    placeholder_patterns = [
        r'\.\s+\.\s+\.',  # . . .
        r'…',             # ellipsis
        r'\[\.{3,}\]',    # [...]
        r'_{4,}',         # ____
    ]

    for pattern in placeholder_patterns:
        if re.search(pattern, text):
            return True

    return False


def count_broken_words(text: str) -> int:
    """
    Count words broken by hard line breaks (OCR artifact).

    Pattern: lowercase letter + newline + space + lowercase letter
    Examples:
    - "kepad\\n a" → broken "kepada"
    - "penug\\n asan" → broken "penugasan"

    Args:
        text: Text to check

    Returns:
        Count of broken words
    """
    # Pattern: lowercase letter, optional comma/period, newline, space(s), lowercase 1-2 letter fragment
    pattern = r'[a-z][,.]?\n\s+[a-z]{1,2}(?:\s|$)'

    matches = re.findall(pattern, text, re.IGNORECASE)

    return len(matches)


def calculate_ocr_quality_score(text: str) -> float:
    """
    Calculate OCR quality score 0.0-1.0.

    Factors:
    - Placeholders: -0.3
    - Broken words: -0.05 each (max -0.5)
    - High newline density: -0.2 (if >1 newline per 50 chars)

    Args:
        text: Text to assess

    Returns:
        Quality score (1.0 = perfect, 0.0 = garbage)
    """
    score = 1.0

    # Penalty for placeholders
    if detect_placeholders(text):
        score -= 0.3

    # Penalty for broken words
    broken = count_broken_words(text)
    score -= min(0.5, broken * 0.05)

    # Penalty for excessive newlines (OCR often adds spurious line breaks)
    newline_count = text.count('\n')
    char_count = len(text)
    if char_count > 0:
        newline_density = newline_count / char_count
        if newline_density > 0.02:  # More than 1 newline per 50 chars
            score -= 0.2

    return max(0.0, score)


def extract_ayat_numbers(pasal_text: str) -> list[int]:
    """
    Extract ayat numbers from Pasal text.

    Pattern: (1), (2), (3), etc. at start of line or after newline

    Args:
        pasal_text: Text of Pasal

    Returns:
        List of ayat numbers found (may have duplicates or gaps)
    """
    # Pattern: (digit+) at line start or after newline
    pattern = r'(?:^|\n)\s*\((\d+)\)'

    matches = re.findall(pattern, pasal_text, re.MULTILINE)

    return [int(m) for m in matches]


def validate_ayat_sequence(ayat_numbers: list[int]) -> dict[str, Any]:
    """
    Validate ayat sequence for completeness and correctness.

    Checks:
    - Unique numbers (no duplicates like [1,2,2,3])
    - Sequential from 1 to N (no gaps)
    - Count matches max

    Args:
        ayat_numbers: List of ayat numbers extracted

    Returns:
        {
            "ayat_count_detected": int,
            "ayat_max_detected": int,
            "ayat_sequence_valid": bool,
            "ayat_validation_error": str | None,
            "ayat_numbers": list[int]
        }
    """
    if not ayat_numbers:
        return {
            "ayat_count_detected": 0,
            "ayat_max_detected": 0,
            "ayat_sequence_valid": True,  # Empty is valid
            "ayat_validation_error": None,
            "ayat_numbers": [],
        }

    ayat_max = max(ayat_numbers)
    ayat_count = len(ayat_numbers)
    ayat_unique = len(set(ayat_numbers))

    # Check for valid sequence: [1, 2, 3, ..., N]
    expected = list(range(1, ayat_max + 1))
    is_valid = (ayat_numbers == expected)

    # Generate error message
    error = None
    if not is_valid:
        if ayat_unique < ayat_count:
            # Find duplicates
            duplicates = [n for n in set(ayat_numbers) if ayat_numbers.count(n) > 1]
            error = f"Duplicate ayat numbers: {duplicates}"
        elif set(ayat_numbers) != set(expected):
            # Find missing
            missing = set(expected) - set(ayat_numbers)
            error = f"Missing ayat numbers: {sorted(missing)}"
        elif ayat_numbers != expected:
            # Out of order
            error = f"Ayat numbers out of order: expected {expected}, got {ayat_numbers}"

    return {
        "ayat_count_detected": ayat_count,
        "ayat_max_detected": ayat_max,
        "ayat_sequence_valid": is_valid,
        "ayat_validation_error": error,
        "ayat_numbers": ayat_numbers,
    }


def assess_document_quality(text: str, ayat_numbers: list[int] | None = None) -> dict[str, Any]:
    """
    Complete quality assessment for a document/chunk.

    Args:
        text: Document text
        ayat_numbers: Optional ayat numbers (if None, will extract)

    Returns:
        {
            "text_fingerprint": str,
            "is_incomplete": bool,
            "ocr_quality_score": float,
            "needs_reextract": bool,
            "broken_words_count": int,
            "ayat_validation": dict | None
        }
    """
    fingerprint = calculate_text_fingerprint(text)
    is_incomplete = detect_placeholders(text)
    broken_count = count_broken_words(text)
    quality_score = calculate_ocr_quality_score(text)

    # Needs reextract if quality is poor
    needs_reextract = (quality_score < 0.7) or is_incomplete

    result = {
        "text_fingerprint": fingerprint,
        "is_incomplete": is_incomplete,
        "ocr_quality_score": quality_score,
        "needs_reextract": needs_reextract,
        "broken_words_count": broken_count,
    }

    # Ayat validation if numbers provided or extractable
    if ayat_numbers is None:
        ayat_numbers = extract_ayat_numbers(text)

    if ayat_numbers:
        result["ayat_validation"] = validate_ayat_sequence(ayat_numbers)
    else:
        result["ayat_validation"] = None

    return result
