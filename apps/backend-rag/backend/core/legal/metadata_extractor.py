"""
Legal Metadata Extractor - Stage 2: The Librarian
Extracts structured metadata from Indonesian legal documents
"""

import logging
import re
from typing import Any

from backend.core.legal.constants import (
    CITATION_SEARCH_OFFSET,
    CITATION_START_PATTERN,
    LEGAL_TITLE_PATTERN,
    LEGAL_TYPE_ABBREV,
    LEGAL_TYPE_PATTERN,
    NUMBER_PATTERN,
    TITLE_BLOCK_FALLBACK_CHARS,
    TOPIC_PATTERN,
    YEAR_PATTERN,
)

logger = logging.getLogger(__name__)

# `1` is read as `I` or `l` and `0` as `O` on scanned title pages. Perpres
# 157/2024 reaches the extractor as "NOMOR I57 TAHUN 2024".
_OCR_DIGIT_MAP = str.maketrans({"I": "1", "l": "1", "O": "0"})

# "40/2007" fuses number and year; only the leading part is the number.
_NUMBER_FUSED_WITH_YEAR = re.compile(r"^(\d{1,4}[A-Za-z]?)[/-]\d{2,4}$")

# A token made only of digits and their OCR look-alikes, optionally suffixed by
# a single letter ("12A"). Anything else -- notably a ministerial number like
# "M.IP-19.GR.01.01" -- must be left alone.
_NUMBER_OCR_CONFUSABLE = re.compile(r"^[0-9IlO]{1,4}[A-Za-z]?$")


def normalize_document_number(raw: str) -> str | None:
    """Interpret a captured `NOMOR ...` token, or return None if it is not one.

    Three shapes occur in the real corpus and each needs different handling:

    * ``40``, ``12A``        plain, optionally with a letter suffix;
    * ``40/2007``            number and year fused -- only ``40`` is the number;
    * ``M.IP-19.GR.01.01``   ministerial decrees are numbered alphanumerically,
      and must be kept VERBATIM: applying the OCR correction here would turn
      ``M.IP`` into ``M.1P``.

    Returns None when the token carries no digit at all, so the caller falls
    back rather than minting an identity out of a stray word.
    """
    token = raw.strip().rstrip("./-")
    if not token:
        return None

    fused = _NUMBER_FUSED_WITH_YEAR.match(token)
    if fused:
        token = fused.group(1)

    if _NUMBER_OCR_CONFUSABLE.match(token):
        token = token.translate(_OCR_DIGIT_MAP)

    if not any(character.isdigit() for character in token):
        return None
    return token.upper()


def _title_block(text: str) -> str:
    """The text that precedes the citation list, i.e. the document's own title."""
    match = CITATION_START_PATTERN.search(text, CITATION_SEARCH_OFFSET)
    if match:
        return text[: match.start()]
    return text[:TITLE_BLOCK_FALLBACK_CHARS]


def extract_title_identity(text: str) -> dict[str, str] | None:
    """Return type/number/year taken from ONE co-located title match, or None.

    The title block is preferred; the whole document is a second pass, because a
    co-located match anywhere still beats three independent first-hits.
    """
    for scope in (_title_block(text), text):
        for match in LEGAL_TITLE_PATTERN.finditer(scope):
            number = normalize_document_number(match.group("number"))
            if number is None:
                continue
            doc_type = match.group("type").upper()
            return {
                "type": doc_type,
                "type_abbrev": LEGAL_TYPE_ABBREV.get(doc_type, doc_type),
                "number": number,
                "year": match.group("year"),
            }
    return None


class LegalMetadataExtractor:
    """
    Extracts metadata from Indonesian legal documents before processing.
    Identifies document type, number, year, and topic.

    Does NOT identify current legal status (in force / revoked) — that
    derivation was retired 2026-08-25 (see constants.py's tombstone comment
    above `# Status indicators`). No text-pattern mechanism reading only a
    document's own body can answer that question correctly for the revoked
    direction: revocation is always stated in a LATER, different instrument.
    """

    def __init__(self) -> None:
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
                "full_title": str,     # Full document title
            }
            No "status" key — retired 2026-08-25, see class docstring.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to metadata extractor")
            return {}

        metadata: dict[str, Any] = {}

        # PREFERRED: all three fields from ONE co-located title match, so they
        # cannot be assembled out of three different laws the document cites.
        identity = extract_title_identity(text)
        if identity:
            metadata.update(identity)
            logger.debug(
                "Extracted co-located identity: %s %s/%s",
                identity["type_abbrev"],
                identity["number"],
                identity["year"],
            )

        # FALLBACK: the independent whole-document searches, per field, only for
        # what the title match could not supply. These are what mint a wrong
        # identity when a document's own title block did not survive parsing --
        # kept because a scavenged field still beats UNKNOWN for retrieval, but
        # deliberately demoted to second place.
        if "type" not in metadata:
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

        if "number" not in metadata:
            number_match = NUMBER_PATTERN.search(text)
            if number_match:
                metadata["number"] = number_match.group(1)
                logger.debug(f"Extracted number: {metadata['number']}")
            else:
                logger.warning("Could not extract document number")
                metadata["number"] = "UNKNOWN"

        if "year" not in metadata:
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

        # Status (berlaku/dicabut) extraction was RETIRED here 2026-08-25 — see
        # constants.py's tombstone comment above `# Status indicators`. `metadata`
        # deliberately carries no "status" key; `legal_ingestion_service.py` no
        # longer writes a `legal_status` payload field for new ingests, which
        # makes the field genuinely ABSENT (not a lingering `None`) — the same
        # shape 15,756 legacy points already carry (kb/inventory/immigration.yaml
        # LANE-A-1), so this introduces no new payload state.

        # Build full title
        metadata["full_title"] = self._build_full_title(metadata)

        logger.info(
            f"Extracted metadata: {metadata['type_abbrev']} No {metadata['number']} "
            f"Tahun {metadata['year']} - {metadata['topic'][:50]}",
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
