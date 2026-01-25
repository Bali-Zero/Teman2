#!/usr/bin/env python3
"""
Universal KBLI RTF Parser (Platinum Edition)
============================================
Batch processor for converting multiple Lampiran RTF files into a single structured Masterpiece.
Based on the successful logic of 'extract_kbli_from_rtf.py'.

Usage:
    1. Place all your converted .rtf files in a folder (e.g., 'rtf_source/')
    2. Run: python universal_kbli_parser.py
"""

import json
import re
from pathlib import Path
from typing import List, Dict

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "rtf_source"  # Where user puts the RTF files
OUTPUT_JSON = BASE_DIR / "Global_KBLI_Masterpiece_Platinum.json"
OUTPUT_CSV = BASE_DIR / "Global_KBLI_Masterpiece_Platinum.csv"

# Standard columns for "Platinum" Schema
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


# --- CORE RTF CLEANING (The "Secret Sauce") ---
def clean_rtf_text(text: str) -> str:
    """Standardizes RTF text removal to extract clean content."""
    if not text:
        return ""

    # 1. Remove common RTF control words
    text = re.sub(r"\\[a-z]+\d*\s*", " ", text)  # \cf0, \fs21, etc.
    text = re.sub(r"\\pard[^\\]*", " ", text)
    text = re.sub(r"\\itap\d+", " ", text)
    text = re.sub(r"\\tx\d+", " ", text)
    text = re.sub(r"\\cell\s*", " ", text)
    text = re.sub(r"\\row\s*", " ", text)
    text = re.sub(r"\\lastrow", " ", text)
    text = re.sub(r"\\trowd[^\\]*", " ", text)
    text = re.sub(r"\\cl[a-z]+\d*[^\\]*", " ", text)
    text = re.sub(r"\\cellx\d+", " ", text)

    # 2. Remove formatting groups
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = re.sub(r"\\[{}]", " ", text)

    # 3. Fix broken words (hyphen at EOL)
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    text = re.sub(r"(\w+)-\s*\\\s*(\w+)", r"\1\2", text)

    # 4. Remove residual garbage (specific to Lampiran RTF export artifacts)
    text = re.sub(r"\b[tT]\d+[tTlL]\s*", " ", text)  # t2t, t7l
    text = re.sub(r"\((\d+)[tTlL]", r"\1", text)  # (1t
    text = re.sub(r"\b\d+[rR]\d+[lL]\s*", " ", text)
    text = re.sub(r"\b-108\b", " ", text)

    # 5. Clean whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\.,;:()\[\]\/\-\+\=\&\%\$\#\@\!]", "", text)
    return text.strip()


def extract_table_rows(rtf_content: str) -> List[str]:
    """Isolates table rows using regex on raw RTF tags."""
    # Pattern: \itap1\trowd ... \row
    return re.findall(r"\\itap1\\trowd.*?(?:\\lastrow)?\\row", rtf_content, re.DOTALL)


def extract_cells_from_row(row_content: str) -> List[str]:
    """Splits a row into cells based on the \cell delimiter."""
    cells = []
    # Split by \cell, ignoring \cellx definitions
    parts = re.split(r"\\cell(?![x\d])(?:\s+|\\lastrow|\\row|$)", row_content)

    for part in parts:
        if not part.strip() or "\\clvertalt" in part or "\\cellx" in part:
            continue
        cleaned = clean_rtf_text(part)
        if len(cleaned) > 1:
            cells.append(cleaned)
    return cells


def is_header_row(cells: List[str]) -> bool:
    """Detects if a row is just column headers."""
    if not cells:
        return True
    text = " ".join(cells[:6]).lower()
    keywords = [
        "kode",
        "kbli",
        "judul",
        "lingkup",
        "skala",
        "usaha",
        "risiko",
        "perizinan",
    ]
    return sum(1 for k in keywords if k in text) >= 3


# --- INTELLIGENT PARSER ---
def process_single_file(rtf_path: Path, source_id: str) -> List[Dict]:
    print(f"   ... Processing {rtf_path.name}")
    try:
        with open(rtf_path, "r", encoding="cp1252") as f:
            content = f.read()
    except:
        with open(rtf_path, "r", encoding="latin-1") as f:
            content = f.read()

    rows = extract_table_rows(content)
    extracted = []

    current_kbli_code = None

    for row in rows:
        cells = extract_cells_from_row(row)

        # Skip empty or headers
        if not cells or len(cells) < 3 or is_header_row(cells):
            continue

        # NORMALIZE CELL COUNT
        # Some rows might identify sub-requirements without repeating KBLI code
        # We need at least 13 slots
        while len(cells) < 13:
            cells.append("")
        cells = cells[:13]

        # FIND KBLI CODE
        # 1. Regex Search in first 3 cells
        found_code = None
        code_idx = -1

        for i in range(3):
            # Strict 5 digit
            match = re.search(r"\b(\d{5})\b", cells[i])
            if match:
                found_code = match.group(1)
                code_idx = i
                break

        # 2. Logic: New Record or Continuation?
        record = {}
        if found_code:
            current_kbli_code = found_code

            # Map columns based on where code was found
            # Ideal: [No, Code, Title, Scope...] -> code at idx 1
            offset = code_idx - 1

            # Special case: Code is first cell (idx 0) -> [Code, Title, Scope...]
            # Special case: Code is second cell (idx 1) -> [No, Code, Title...]

            record["kode_kbli"] = found_code

            # Try to align other columns relative to code
            # Standard Map: No(0) Code(1) Title(2) -> Code is at 1
            # If code is at 0, subtract 1 from target index

            for target_idx, col_name in enumerate(COLUMN_NAMES):
                if col_name == "kode_kbli":
                    continue

                source_idx = target_idx + offset
                if 0 <= source_idx < len(cells):
                    val = cells[source_idx]
                    # Clean code out of the value if it leaked
                    if col_name == "judul_kbli":
                        val = val.replace(found_code, "").strip()
                    record[col_name] = val
                else:
                    record[col_name] = ""

            record["source_file"] = source_id
            extracted.append(record)

        else:
            # No code found. This might be a "merged cell" continuation (e.g. Risk Level splits)
            # Strategy: Append to previous record if it exists
            # For now, let's just log it or strict mode?
            # User wants "Platinum". Let's try to grab useful info if it looks like data
            pass

    return extracted


# --- MAIN LOOP ---
def main():
    print("=" * 60)
    print("🚀  Nuzantara Universal KBLI Parser (Platinum)")
    print("=" * 60)

    if not INPUT_DIR.exists():
        print(f"Creating input directory: {INPUT_DIR}")
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        print("⚠️  PLEASE PUT YOUR .RTF FILES IN 'rtf_source/' AND RERUN.")
        return

    all_files = list(INPUT_DIR.glob("*.rtf"))
    if not all_files:
        print("❌ No .rtf files found in 'rtf_source/'.")
        print("   Please convert your PDFs to RTF and move them there.")
        return

    global_data = []

    for rtf_file in sorted(all_files):
        print(f"📂 Found: {rtf_file.name}")
        file_data = process_single_file(rtf_file, rtf_file.stem)
        global_data.extend(file_data)
        print(f"   -> Extracted {len(file_data)} records")

    print("-" * 60)
    print(f"TOTAL RECORDS: {len(global_data)}")

    # Save
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "version": "Platinum 1.0",
                    "total_records": len(global_data),
                    "sources": [f.name for f in all_files],
                },
                "data": global_data,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"✅ Saved Unified JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
