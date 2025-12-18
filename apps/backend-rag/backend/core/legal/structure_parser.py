"""
Legal Structure Parser - Stage 3: The Architect
Recognizes hierarchical structure of Indonesian legal documents
"""

import logging
import re
from typing import Any

from .constants import (
    AYAT_PATTERN,
    BAB_PATTERN,
    BAGIAN_PATTERN,
    KONSIDERANS_MARKERS,
    PARAGRAF_PATTERN,
    PASAL_PATTERN,
    PENJELASAN_PATTERN,
)

logger = logging.getLogger(__name__)


class LegalStructureParser:
    """
    Parses the hierarchical structure of Indonesian legal documents.
    Recognizes: Konsiderans, BAB, Bagian, Paragraf, Pasal, Ayat, Penjelasan.
    """

    def __init__(self):
        """Initialize the structure parser"""
        logger.info("LegalStructureParser initialized")

    def parse(self, text: str) -> dict[str, Any]:
        """
        Parse legal document structure.

        Args:
            text: Cleaned legal document text

        Returns:
            Dictionary with parsed structure:
            {
                "konsiderans": str,      # Considerations section
                "batang_tubuh": list,    # List of BAB (chapters)
                "penjelasan": str,        # Elucidation section
                "pasal_list": list,      # List of all Pasal with their structure
            }
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to structure parser")
            return {}

        structure = {
            "konsiderans": None,
            "batang_tubuh": [],
            "penjelasan": None,
            "pasal_list": [],
        }

        # Step 1: Extract Konsiderans
        structure["konsiderans"], body_start_index = self._extract_konsiderans_with_index(text)

        # Step 2: Split document into sections
        penjelasan_match = PENJELASAN_PATTERN.search(text)
        penjelasan_start = penjelasan_match.start() if penjelasan_match else len(text)

        # Batang Tubuh starts after Konsiderans (or at 0 if no Konsiderans)
        start_index = body_start_index if body_start_index is not None else 0
        batang_tubuh_text = text[start_index:penjelasan_start]

        penjelasan_text = text[penjelasan_start:] if penjelasan_match else ""

        # Step 3: Parse Batang Tubuh (Body)
        structure["batang_tubuh"] = self._parse_batang_tubuh(batang_tubuh_text)

        # Step 4: Extract all Pasal
        structure["pasal_list"] = self._extract_pasal_list(batang_tubuh_text)

        # Step 5: Extract Penjelasan
        if penjelasan_text:
            structure["penjelasan"] = penjelasan_text.strip()

        logger.info(
            f"Parsed structure: {len(structure['batang_tubuh'])} BAB, "
            f"{len(structure['pasal_list'])} Pasal"
        )

        return structure

    def _extract_konsiderans_with_index(self, text: str) -> tuple[str | None, int | None]:
        """
        Extract Konsiderans and return its text and end index.

        Args:
            text: Document text

        Returns:
            Tuple (konsiderans_text, end_index)
        """
        konsiderans_start = None
        konsiderans_end = None

        # Find start of Konsiderans
        for marker in KONSIDERANS_MARKERS:
            match = re.search(rf"^{marker}", text, re.IGNORECASE | re.MULTILINE)
            if match:
                konsiderans_start = match.start()
                break

        if konsiderans_start is None:
            return None, None

        # Find end of Konsiderans (start of Batang Tubuh)
        # Usually marked by "MEMUTUSKAN:" or first "BAB" or first "Pasal"
        end_markers = [
            r"^MEMUTUSKAN:",
            r"^BAB\s+",
            r"^Pasal\s+\d+",
        ]

        for marker in end_markers:
            match = re.search(marker, text[konsiderans_start:], re.IGNORECASE | re.MULTILINE)
            if match:
                konsiderans_end = konsiderans_start + match.start()
                # If marker is MEMUTUSKAN, we want to include it in Konsiderans or skip it?
                # Usually MEMUTUSKAN: Menetapkan: ... is the bridge.
                # The actual body starts after "Menetapkan: ...".
                # But for simplicity, let's say body starts at the marker match if it's BAB or Pasal,
                # or after MEMUTUSKAN block if it's MEMUTUSKAN.

                # If marker is MEMUTUSKAN, let's try to find "Menetapkan:" and go after that.
                if "MEMUTUSKAN" in marker.upper() or "MEMUTUSKAN" in match.group(0).upper():
                    # Look for "Menetapkan" after this
                    menetapkan_match = re.search(
                        r"Menetapkan\s*:", text[konsiderans_start + match.start() :], re.IGNORECASE
                    )
                    if menetapkan_match:
                        # The body usually starts after the title of the law in Menetapkan.
                        # E.g. Menetapkan: UNDANG-UNDANG TENTANG ...
                        # Then BAB I.
                        # So we might want to look for the first BAB or Pasal after this.
                        pass
                break

        if konsiderans_end is None:
            # If no end marker, take first 2000 chars
            konsiderans_end = konsiderans_start + 2000

        konsiderans_text = text[konsiderans_start:konsiderans_end].strip()
        return konsiderans_text, konsiderans_end

    def _extract_konsiderans(self, text: str) -> str | None:
        """Wrapper for backward compatibility if needed"""
        content, _ = self._extract_konsiderans_with_index(text)
        return content

    def _parse_batang_tubuh(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Batang Tubuh (Body) into BAB (Chapters).

        Args:
            text: Batang Tubuh text

        Returns:
            List of BAB dictionaries with their structure
        """
        bab_list = []
        bab_matches = list(BAB_PATTERN.finditer(text))

        for i, bab_match in enumerate(bab_matches):
            bab_num = bab_match.group(1)
            bab_title = bab_match.group(2).strip()

            # Find end of this BAB (start of next BAB or end of text)
            start_pos = bab_match.end()
            end_pos = bab_matches[i + 1].start() if i + 1 < len(bab_matches) else len(text)

            bab_text = text[start_pos:end_pos]

            # Parse Bagian within this BAB
            bagian_list = self._parse_bagian(bab_text)

            # Parse Pasal within this BAB
            pasal_list = self._parse_pasal_in_section(bab_text)

            bab_dict = {
                "number": bab_num,
                "title": bab_title,
                "text": bab_text,
                "bagian": bagian_list,
                "pasal": pasal_list,
            }

            bab_list.append(bab_dict)

        return bab_list

    def _parse_bagian(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Bagian (Parts) within a BAB.

        Args:
            text: Text section (BAB or standalone)

        Returns:
            List of Bagian dictionaries
        """
        bagian_list = []
        bagian_matches = list(BAGIAN_PATTERN.finditer(text))

        for i, bagian_match in enumerate(bagian_matches):
            bagian_num = bagian_match.group(1)
            bagian_title = bagian_match.group(2).strip()

            start_pos = bagian_match.end()
            end_pos = bagian_matches[i + 1].start() if i + 1 < len(bagian_matches) else len(text)

            bagian_text = text[start_pos:end_pos]

            # Parse Paragraf within this Bagian
            paragraf_list = self._parse_paragraf(bagian_text)

            bagian_dict = {
                "number": bagian_num,
                "title": bagian_title,
                "text": bagian_text,
                "paragraf": paragraf_list,
            }

            bagian_list.append(bagian_dict)

        return bagian_list

    def _parse_paragraf(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Paragraf (Paragraphs) within a Bagian.

        Args:
            text: Text section

        Returns:
            List of Paragraf dictionaries
        """
        paragraf_list = []
        paragraf_matches = list(PARAGRAF_PATTERN.finditer(text))

        for i, paragraf_match in enumerate(paragraf_matches):
            paragraf_num = paragraf_match.group(1)
            paragraf_title = paragraf_match.group(2).strip()

            start_pos = paragraf_match.end()
            end_pos = (
                paragraf_matches[i + 1].start() if i + 1 < len(paragraf_matches) else len(text)
            )

            paragraf_text = text[start_pos:end_pos]

            paragraf_dict = {
                "number": paragraf_num,
                "title": paragraf_title,
                "text": paragraf_text,
            }

            paragraf_list.append(paragraf_dict)

        return paragraf_list

    def _parse_pasal_in_section(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Pasal (Articles) within a section.

        Args:
            text: Text section

        Returns:
            List of Pasal dictionaries with Ayat
        """
        pasal_list = []
        pasal_matches = list(PASAL_PATTERN.finditer(text))

        for pasal_match in pasal_matches:
            pasal_num = pasal_match.group(1)
            pasal_text = pasal_match.group(2).strip()

            # Parse Ayat within this Pasal
            ayat_list = self._parse_ayat(pasal_text)

            pasal_dict = {
                "number": pasal_num,
                "text": pasal_text,
                "ayat": ayat_list,
            }

            pasal_list.append(pasal_dict)

        return pasal_list

    def _parse_ayat(self, text: str) -> list[dict[str, Any]]:
        """
        Parse Ayat (Clauses) within a Pasal.

        Args:
            text: Pasal text

        Returns:
            List of Ayat dictionaries
        """
        ayat_list = []
        ayat_matches = list(AYAT_PATTERN.finditer(text))

        for ayat_match in ayat_matches:
            ayat_num = ayat_match.group(1)
            ayat_text = ayat_match.group(2).strip()

            ayat_dict = {
                "number": ayat_num,
                "text": ayat_text,
            }

            ayat_list.append(ayat_dict)

        return ayat_list

    def _extract_pasal_list(self, text: str) -> list[dict[str, Any]]:
        """
        Extract all Pasal from document with full context.

        Args:
            text: Document text

        Returns:
            List of Pasal with their hierarchical context
        """
        pasal_list = []
        pasal_matches = list(PASAL_PATTERN.finditer(text))

        for pasal_match in pasal_matches:
            pasal_num = pasal_match.group(1)
            pasal_text = pasal_match.group(2).strip()

            # Find which BAB this Pasal belongs to
            bab_context = self._find_bab_context(text, pasal_match.start())

            # Parse Ayat
            ayat_list = self._parse_ayat(pasal_text)

            pasal_dict = {
                "number": pasal_num,
                "text": pasal_text,
                "ayat": ayat_list,
                "bab_context": bab_context,
            }

            pasal_list.append(pasal_dict)

        return pasal_list

    def _find_bab_context(self, text: str, position: int) -> str | None:
        """
        Find which BAB a position belongs to.

        Args:
            text: Document text
            position: Character position

        Returns:
            BAB number/title or None
        """
        bab_matches = list(BAB_PATTERN.finditer(text))

        for bab_match in reversed(bab_matches):
            if bab_match.start() < position:
                return f"BAB {bab_match.group(1)} - {bab_match.group(2).strip()}"

        return None
