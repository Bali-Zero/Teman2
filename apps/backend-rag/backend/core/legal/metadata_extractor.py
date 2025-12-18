"""
Legal Metadata Extractor - Stage 2: The Librarian
Extracts structured metadata from Indonesian legal documents
"""

import logging
import re
from typing import Any

from .constants import (
    LEGAL_TYPE_ABBREV,
    LEGAL_TYPE_PATTERN,
    NUMBER_PATTERN,
    STATUS_PATTERNS,
    TOPIC_PATTERN,
    YEAR_PATTERN,
)

logger = logging.getLogger(__name__)


class LegalMetadataExtractor:
    """
    Extracts metadata from Indonesian legal documents before processing.
    Identifies document type, number, year, topic, and status.
    """

    def __init__(self):
        """Initialize the metadata extractor"""
        logger.info("LegalMetadataExtractor initialized")

    def extract(self, text: str) -> dict[str, Any]:
        """
        Extract all metadata from legal document text.

        Args:
            text: Cleaned legal document text

        Returns:
            Dictionary with extracted metadata:
            {
                "type": str,           # "UNDANG-UNDANG", "PERATURAN PEMERINTAH", etc.
                "type_abbrev": str,    # "UU", "PP", etc.
                "number": str,         # "12", "12A", etc.
                "year": str,           # "2024"
                "topic": str,          # Topic text after "TENTANG"
                "status": str,         # "berlaku", "dicabut", or None
                "full_title": str,     # Full document title
            }
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to metadata extractor")
            return {}

        metadata = {}

        # Extract document type
        type_match = LEGAL_TYPE_PATTERN.search(text)
        if type_match:
            doc_type = type_match.group(1).upper()
            metadata["type"] = doc_type
            metadata["type_abbrev"] = LEGAL_TYPE_ABBREV.get(doc_type, doc_type)
            logger.debug(f"Extracted type: {doc_type} ({metadata['type_abbrev']})")
        else:
            logger.warning("Could not extract document type")
            metadata["type"] = "UNKNOWN"
            metadata["type_abbrev"] = "UNKNOWN"

        # Extract document number
        number_match = NUMBER_PATTERN.search(text)
        if number_match:
            metadata["number"] = number_match.group(1)
            logger.debug(f"Extracted number: {metadata['number']}")
        else:
            logger.warning("Could not extract document number")
            metadata["number"] = "UNKNOWN"

        # Extract year
        year_match = YEAR_PATTERN.search(text)
        if year_match:
            metadata["year"] = year_match.group(1)
            logger.debug(f"Extracted year: {metadata['year']}")
        else:
            logger.warning("Could not extract year")
            metadata["year"] = "UNKNOWN"

        # Extract topic (text after "TENTANG")
        topic_match = TOPIC_PATTERN.search(text)
        if topic_match:
            topic = topic_match.group(1).strip()
            # Clean up topic text
            topic = re.sub(r"\s+", " ", topic)  # Normalize whitespace
            topic = topic[:200]  # Limit length
            metadata["topic"] = topic
            logger.debug(f"Extracted topic: {topic[:50]}...")
        else:
            logger.warning("Could not extract topic")
            metadata["topic"] = "UNKNOWN"

        # Extract status (berlaku/dicabut)
        status = None
        for status_key, pattern in STATUS_PATTERNS.items():
            if pattern.search(text):
                status = status_key
                break

        metadata["status"] = status
        if status:
            logger.debug(f"Extracted status: {status}")

        # Build full title
        metadata["full_title"] = self._build_full_title(metadata)

        logger.info(
            f"Extracted metadata: {metadata['type_abbrev']} No {metadata['number']} "
            f"Tahun {metadata['year']} - {metadata['topic'][:50]}"
        )

        return metadata

    def _build_full_title(self, metadata: dict[str, Any]) -> str:
        """
        Build full document title from metadata.

        Args:
            metadata: Extracted metadata dictionary

        Returns:
            Full title string
        """
        parts = []

        if metadata.get("type_abbrev") and metadata["type_abbrev"] != "UNKNOWN":
            parts.append(metadata["type_abbrev"])

        if metadata.get("number") and metadata["number"] != "UNKNOWN":
            parts.append(f"No {metadata['number']}")

        if metadata.get("year") and metadata["year"] != "UNKNOWN":
            parts.append(f"Tahun {metadata['year']}")

        if metadata.get("topic") and metadata["topic"] != "UNKNOWN":
            parts.append(f"Tentang {metadata['topic']}")

        return " ".join(parts) if parts else "Unknown Legal Document"

    def is_legal_document(self, text: str) -> bool:
        """
        Check if text appears to be an Indonesian legal document.

        Args:
            text: Text to check

        Returns:
            True if text contains legal document markers
        """
        if not text:
            return False

        # Check for legal type pattern
        if LEGAL_TYPE_PATTERN.search(text):
            return True

        # Check for common legal document markers
        legal_markers = [
            "Pasal",
            "Menimbang",
            "Mengingat",
            "DENGAN RAHMAT TUHAN",
            "PRESIDEN REPUBLIK INDONESIA",
        ]

        marker_count = sum(1 for marker in legal_markers if marker in text)
        return marker_count >= 2  # At least 2 markers suggest legal document
