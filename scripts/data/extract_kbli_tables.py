#!/usr/bin/env python3
"""
KBLI Table-Aware Extractor
===========================
Uses PyMuPDF's table detection to properly extract KBLI codes from PDF tables.
Falls back to Gemini Vision for complex layouts.

This fixes the issue where pypdf.extract_text() produces fragmented text
like "ss900 Penye- diaan Akomo-" instead of proper structured data.

Requirements:
    pip install pymupdf google-generativeai

Usage:
    python scripts/data/extract_kbli_tables.py --pdf <path> [--use-vision]
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import required libraries
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️ PyMuPDF not available. Install with: pip install pymupdf")

try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class KBLITableExtractor:
    """
    Extracts KBLI codes from PDF tables using multiple strategies:
    1. PyMuPDF table detection (fitz.find_tables)
    2. Regex-based extraction from raw text
    3. Gemini Vision for complex layouts
    """

    def __init__(self, use_vision: bool = False):
        self.use_vision = use_vision
        self.extracted_codes = {}
        self.errors = []

        if use_vision and GENAI_AVAILABLE:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.vision_model = genai.GenerativeModel("gemini-1.5-flash")
            else:
                print("⚠️ GOOGLE_API_KEY not set. Vision mode disabled.")
                self.use_vision = False

    def extract_from_pdf(self, pdf_path: str) -> dict:
        """Main extraction method."""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required. Install with: pip install pymupdf")

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        print(f"\n📄 Processing: {pdf_path.name}")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        for page_num, page in enumerate(doc):
            print(f"  Page {page_num + 1}/{total_pages}...", end="\r")

            # Strategy 1: Table detection
            tables_found = self._extract_tables_from_page(page, page_num)

            # Strategy 2: If no tables, try text extraction with improved regex
            if not tables_found:
                self._extract_from_text(page, page_num)

            # Strategy 3: Vision fallback for difficult pages
            if self.use_vision and not tables_found:
                self._extract_with_vision(page, page_num)

        doc.close()

        print(f"\n✅ Extracted {len(self.extracted_codes)} unique KBLI codes")
        return self.extracted_codes

    def _extract_tables_from_page(self, page, page_num: int) -> bool:
        """Extract KBLI codes from detected tables."""
        try:
            tables = page.find_tables()
            if not tables:
                return False

            found_any = False

            for table in tables:
                rows = table.extract()
                if not rows:
                    continue

                # Find the column that contains KBLI codes
                code_col_idx = self._find_code_column(rows[0] if rows else [])

                for row in rows:
                    if not row or len(row) <= code_col_idx:
                        continue

                    # Extract code
                    raw_code = (
                        str(row[code_col_idx]).strip() if row[code_col_idx] else ""
                    )
                    code = self._clean_kbli_code(raw_code)

                    if not code:
                        continue

                    # Extract title (usually next column)
                    title = ""
                    if len(row) > code_col_idx + 1:
                        title = (
                            str(row[code_col_idx + 1]).strip()
                            if row[code_col_idx + 1]
                            else ""
                        )

                    # Extract other columns as metadata
                    metadata = self._extract_row_metadata(row, code_col_idx)

                    self._add_code(code, title, metadata, page_num, "table")
                    found_any = True

            return found_any

        except Exception as e:
            self.errors.append(f"Table extraction error on page {page_num}: {e}")
            return False

    def _find_code_column(self, header_row: list) -> int:
        """Find which column contains KBLI codes."""
        if not header_row:
            return 0

        for i, cell in enumerate(header_row):
            cell_str = str(cell).lower() if cell else ""
            if any(kw in cell_str for kw in ["kode", "kbli", "code"]):
                return i

        # Default to first column
        return 0

    def _extract_from_text(self, page, page_num: int):
        """Extract from raw text when table detection fails."""
        text = page.get_text()
        if not text:
            return

        # Pattern: 5-digit code followed by title
        # Handles: "55190 Jasa Manajemen Hotel" or "55190  Jasa Manajemen Hotel"
        pattern = r"(?:^|\s)(\d{5})\s+([A-Z][^\n\d]{3,80})"

        for match in re.finditer(pattern, text, re.MULTILINE):
            code = match.group(1)
            title = match.group(2).strip()

            # Clean up common OCR issues
            title = self._clean_title(title)

            if code and title and len(title) > 3:
                self._add_code(code, title, {}, page_num, "text")

    def _extract_with_vision(self, page, page_num: int):
        """Use Gemini Vision for complex layouts."""
        if not self.use_vision:
            return

        try:
            # Render page to image
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")

            prompt = """
            Extract all KBLI codes from this table image.
            KBLI codes are 5-digit numbers (like 55110, 55190, 56101).

            For each code, extract:
            - kode: the 5-digit code
            - judul: the title/name of the business activity
            - tingkat_risiko: risk level if shown (Rendah/Menengah/Tinggi)

            Return as JSON array:
            [{"kode": "55190", "judul": "Jasa Manajemen Hotel", "tingkat_risiko": "Rendah"}, ...]

            Only return valid JSON. If no KBLI codes found, return [].
            """

            response = self.vision_model.generate_content([prompt, img_bytes])
            result_text = response.text

            # Parse JSON from response
            json_match = re.search(r"\[.*\]", result_text, re.DOTALL)
            if json_match:
                codes = json.loads(json_match.group())
                for item in codes:
                    code = item.get("kode", "")
                    title = item.get("judul", "")
                    if self._clean_kbli_code(code) and title:
                        self._add_code(
                            self._clean_kbli_code(code),
                            title,
                            {"tingkat_risiko": item.get("tingkat_risiko", "")},
                            page_num,
                            "vision",
                        )

        except Exception as e:
            self.errors.append(f"Vision extraction error on page {page_num}: {e}")

    def _clean_kbli_code(self, raw: str) -> Optional[str]:
        """Clean and validate KBLI code."""
        if not raw:
            return None

        # Remove common OCR errors
        cleaned = raw.strip()
        cleaned = cleaned.replace("O", "0").replace("o", "0")
        cleaned = cleaned.replace("l", "1").replace("I", "1")
        cleaned = cleaned.replace("S", "5").replace("s", "5")

        # Validate: must be exactly 5 digits
        if re.fullmatch(r"\d{5}", cleaned):
            return cleaned

        return None

    def _clean_title(self, title: str) -> str:
        """Clean up extracted title."""
        # Fix hyphenation from line breaks
        title = re.sub(r"(\w)- +(\w)", r"\1\2", title)
        # Remove excessive whitespace
        title = " ".join(title.split())
        return title

    def _extract_row_metadata(self, row: list, code_col: int) -> dict:
        """Extract additional metadata from table row."""
        metadata = {}

        # Common column patterns in KBLI tables
        for i, cell in enumerate(row):
            if i == code_col or not cell:
                continue

            cell_str = str(cell).strip().lower()

            # Risk level
            if any(r in cell_str for r in ["rendah", "menengah", "tinggi"]):
                if "tinggi" in cell_str:
                    metadata["tingkat_risiko"] = "Tinggi"
                elif "menengah tinggi" in cell_str:
                    metadata["tingkat_risiko"] = "Menengah Tinggi"
                elif "menengah rendah" in cell_str:
                    metadata["tingkat_risiko"] = "Menengah Rendah"
                elif "menengah" in cell_str:
                    metadata["tingkat_risiko"] = "Menengah"
                elif "rendah" in cell_str:
                    metadata["tingkat_risiko"] = "Rendah"

            # PMA status
            if "pma" in cell_str or "asing" in cell_str:
                metadata["pma_note"] = str(cell).strip()

        return metadata

    def _add_code(self, code: str, title: str, metadata: dict, page: int, source: str):
        """Add or update a KBLI code."""
        if code in self.extracted_codes:
            # Merge with existing - keep longer title
            existing = self.extracted_codes[code]
            if len(title) > len(existing.get("judul", "")):
                existing["judul"] = title
            existing["metadata"].update(metadata)
            existing["pages"].add(page)
            existing["sources"].add(source)
        else:
            self.extracted_codes[code] = {
                "kode": code,
                "judul": title,
                "metadata": metadata,
                "pages": {page},
                "sources": {source},
            }

    def to_json(self) -> dict:
        """Convert to JSON-serializable format."""
        result = {
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "total_codes": len(self.extracted_codes),
                "errors": self.errors,
            },
            "kbli_codes": {},
        }

        for code, data in sorted(self.extracted_codes.items()):
            result["kbli_codes"][code] = {
                "kode": code,
                "judul": data["judul"],
                "tingkat_risiko": data["metadata"].get("tingkat_risiko", ""),
                "sektor": data["metadata"].get("sektor", ""),
                "extraction_sources": list(data["sources"]),
                "found_on_pages": sorted(data["pages"]),
            }

        return result


def main():
    parser = argparse.ArgumentParser(description="Extract KBLI codes from PDF tables")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument(
        "--use-vision",
        action="store_true",
        help="Use Gemini Vision for complex layouts",
    )

    args = parser.parse_args()

    extractor = KBLITableExtractor(use_vision=args.use_vision)
    codes = extractor.extract_from_pdf(args.pdf)

    result = extractor.to_json()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
