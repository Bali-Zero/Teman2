"""
Legal Document Cleaner - Stage 1: The Washer
Removes non-content artifacts from Indonesian legal documents
"""

import logging
import re

from .constants import NOISE_PATTERNS, WHITESPACE_FIXES

logger = logging.getLogger(__name__)


class LegalCleaner:
    """
    Cleans Indonesian legal documents by removing headers, footers,
    page numbers, and other non-content artifacts.
    """

    def __init__(self):
        """Initialize the legal cleaner"""
        logger.info("LegalCleaner initialized")

    def clean(self, text: str) -> str:
        """
        Clean legal document text by removing noise patterns.

        Args:
            text: Raw extracted text from PDF/HTML

        Returns:
            Cleaned text with noise removed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to cleaner")
            return text

        cleaned = text

        # Step 1: Remove noise patterns
        for pattern in NOISE_PATTERNS:
            matches_before = len(re.findall(pattern, cleaned))
            cleaned = pattern.sub("", cleaned)
            if matches_before > 0:
                logger.debug(f"Removed {matches_before} matches of pattern: {pattern.pattern[:50]}")

        # Step 2: Normalize whitespace
        for pattern, replacement in WHITESPACE_FIXES:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Step 3: Remove "Salinan sesuai dengan aslinya" footer (more aggressive)
        cleaned = re.sub(
            r"Salinan sesuai dengan aslinya.*?(?=\n|$)",
            "",
            cleaned,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )

        # Step 4: Normalize Pasal spacing (ensure consistent format)
        cleaned = re.sub(r"Pasal\s+(\d+[A-Z]?)", r"Pasal \1", cleaned, flags=re.IGNORECASE)

        # Step 5: Remove standalone page numbers (lines with only numbers)
        cleaned = re.sub(r"^\s*\d+\s*$", "", cleaned, flags=re.MULTILINE)

        # Step 6: Final cleanup - remove excessive blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # Step 7: Trim whitespace
        cleaned = cleaned.strip()

        original_length = len(text)
        cleaned_length = len(cleaned)
        reduction = original_length - cleaned_length

        if reduction > 0:
            logger.info(
                f"Cleaned text: {original_length} → {cleaned_length} chars "
                f"({reduction} removed, {reduction / original_length * 100:.1f}%)"
            )

        return cleaned

    def clean_headers_footers(self, text: str) -> str:
        """
        Specifically target headers and footers (more aggressive cleaning).

        Args:
            text: Text to clean

        Returns:
            Text with headers/footers removed
        """
        # Remove common header patterns
        header_patterns = [
            r"^PRESIDEN REPUBLIK INDONESIA.*?\n",
            r"^MENTERI.*?\n",
            r"^GUBERNUR.*?\n",
            r"^BUPATI.*?\n",
            r"^WALIKOTA.*?\n",
        ]

        cleaned = text
        for pattern in header_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

        return cleaned.strip()
