#!/usr/bin/env python3
"""
Universal KBLI PDF Parser (Platinum Edition)
============================================
Batch processor for converting Lampiran PDF files directly into structured JSON.
Uses 'pdfplumber' in stream mode as validated by 'test_pdf_extraction_v2.py'.

Usage:
    python universal_pdf_parser.py
"""

import pdfplumber
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR  # The PDFs are in the current directory
OUTPUT_JSON = BASE_DIR / "Global_KBLI_Masterpiece_Platinum.json"
OUTPUT_CSV = BASE_DIR / "Global_KBLI_Masterpiece_Platinum.csv"

# Standard columns for "Platinum" Schema
# Based on the columns detected in Lampiran I.C
COLUMN_NAMES = [
    "no",
    "kode_kbli",
    "judul_kbli",
    "ruang_lingkup",
    "skala_usaha",
    "tingkat_risiko",
    "perizinan_berusaha",
    "persyaratan",
    "jangka_waktu_penerbitan",
    "kewajiban",
    "pb_uu_ikm",
    "parameter",
    "kewenangan",
]


def clean_cell(text: str) -> str:
    """Cleans cell content."""
    if not text:
        return ""
    # Remove newlines and excess whitespace
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_kbli_code(text: str) -> Optional[str]:
    """
    Attempts to find a 5-digit KBLI code in a string.
    Handles standard "01234" and spaced "0 1 2 3 4".
    """
    if not text:
        return None
    # Standard 5-digit
    match = re.search(r"\b\d{5}\b", text)
    if match:
        return match.group(0)

    # Spaced digits (common in messy PDF extraction)
    # Looking for 5 digits separated by whitespace
    cleaned = re.sub(r"\s+", "", text)
    match_clean = re.search(r"\b\d{5}\b", cleaned)
    if match_clean:
        return match_clean.group(0)

    return None


def process_single_pdf(pdf_path: Path) -> List[Dict]:
    """Extracts data from a single PDF with enhanced strategies."""
    print(f"   ... Processing {pdf_path.name}")
    extracted_records = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"       -> {total_pages} pages detected")

            for i, page in enumerate(pdf.pages):
                # INTENTIONAL STRATEGY SWITCH:
                # We try 'lines' first (explicit borders), then 'text' (whitespace)
                # But Lampiran usually has borders. Let's try mixed.

                # Strategy: Primary (Text-based for whitespace tables)
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "snap_tolerance": 3,
                    }
                )

                # If primary strategy fails effectively (no data), simplistic approach:
                # We process the rows we got.

                if not tables:
                    # Fallback to lines?
                    tables = page.extract_tables(
                        table_settings={
                            "vertical_strategy": "lines",
                            "horizontal_strategy": "lines",
                        }
                    )

                if not tables:
                    continue

                for table in tables:
                    for row in table:
                        if not row or not any(row):
                            continue

                        # Clean row
                        cleaned_row = [clean_cell(cell) for cell in row]
                        row_text = " ".join(cleaned_row)

                        # Skip Headers
                        if "kode" in row_text.lower() and "judul" in row_text.lower():
                            continue

                        # AGGRESSIVE KBLI FINDER
                        kbli_code = None
                        kbli_idx = -1

                        # Scan ALL cells for a KBLI code
                        for idx, cell in enumerate(cleaned_row):
                            code = clean_kbli_code(cell)
                            if code:
                                kbli_code = code
                                kbli_idx = idx
                                break

                        if kbli_code:
                            # We found a code!
                            record = {}
                            record["kode_kbli"] = kbli_code
                            record["source_file"] = pdf_path.name
                            record["page"] = i + 1

                            # Alignment Logic:
                            # Typically Code is col 1 (0-indexed) or col 0.
                            # We shift our mapping based on where we found the code.
                            # Standard format: [No, Code, Title, Scope...] -> Code is index 1.
                            # So offset is kbli_idx - 1.

                            offset = kbli_idx - 1

                            for target_idx, col_name in enumerate(COLUMN_NAMES):
                                if col_name == "kode_kbli":
                                    continue

                                source_idx = target_idx + offset
                                if 0 <= source_idx < len(cleaned_row):
                                    val = cleaned_row[source_idx]
                                    # Anti-duplication cleanup
                                    if val and kbli_code in val and len(val) < 10:
                                        # If cell is JUST the code, don't map it to title
                                        val = ""
                                    record[col_name] = val
                                else:
                                    record[col_name] = ""

                            extracted_records.append(record)
                        else:
                            # Todo: Handle continuation rows (append to previous)
                            # For MVP Emergency, we focus on capturing the HEAD records.
                            pass

    except Exception as e:
        print(f"❌ Error processing {pdf_path.name}: {e}")

    print(f"       -> Extracted {len(extracted_records)} records")
    return extracted_records


def main():
    print("=" * 60)
    print("🚀  Nuzantara Universal KBLI PDF Parser")
    print("=" * 60)

    # Filter for Lampiran I.A - I.V files only
    # They seem to start with "2." and end with ".pdf"
    all_files = sorted([p for p in INPUT_DIR.glob("2.*Lampiran*.pdf")])

    if not all_files:
        print("❌ No Lampiran PDF files found matching pattern '2.*Lampiran*.pdf'")
        return

    print(f"Found {len(all_files)} files to process.")

    global_data = []

    for pdf_file in all_files:
        file_data = process_single_pdf(pdf_file)
        global_data.extend(file_data)

    print("-" * 60)
    print(f"TOTAL RECORDS ACROSS ALL SECTORS: {len(global_data)}")

    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "version": "Platinum Automated 1.0",
                    "total_records": len(global_data),
                    "generated_by": "universal_pdf_parser.py",
                },
                "data": global_data,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"✅ Saved Unified JSON: {OUTPUT_JSON}")

    # Save CSV (Bonus)
    if global_data:
        import csv

        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=global_data[0].keys())
            writer.writeheader()
            writer.writerows(global_data)
        print(f"✅ Saved CSV: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
