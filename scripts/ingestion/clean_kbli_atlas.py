#!/usr/bin/env python3
"""
KBLI Atlas Cleaner
Removes OCR-corrupted fields from risk_data while preserving clean structured data.
"""

import json
import re
from pathlib import Path

# Fields that are typically OCR-corrupted and should be nullified
OCR_CORRUPTED_FIELDS = [
    "ruang_lingkup",
    "persyaratan",
    "kewajiban",
    "timeline",
    "pb_umku",
]

# OCR garbage patterns that indicate corruption
OCR_GARBAGE_PATTERNS = [
    r"Kcw[a-z]*",  # Kewajiban OCR fail
    r"Pcr[a-z]*",  # Persyaratan OCR fail
    r"Ruer?g",     # Ruang OCR fail
    r"Llrg|Ltug|Lfng",  # Lingkup OCR fail
    r"IIMI|UUXU|UMKT",  # UMKU OCR fail
    r"t8t|t8I|\(et|\(el",  # Random OCR artifacts
    r"Pcacrbl|Peacrbl|Pencrbl",  # Penerbitan OCR fail
    r"Jengle|Jengtr|Jeaglr",  # Jangka OCR fail
    r"\{1U|\{101|lrol|llrl",  # Number artifacts
    r"agricttlture|agianlfire|agricalfure",  # agriculture OCR fail
]

# Fields to KEEP (clean structured data)
CLEAN_FIELDS = [
    "judul",
    "judul_official",
    "skala_usaha",
    "tingkat_risiko",
    "sektor",
    "source_lampiran",
    "legal_notices",
    "deskripsi_bps",
    "sanksi_administratif",
    "checklists_umku",
    "intelligence_tags",
    "pma_allowed",
    "pma_max_percentage",
    "_source_file",
]


def is_corrupted(text: str) -> bool:
    """Check if text contains OCR corruption patterns."""
    if not text or not isinstance(text, str):
        return False

    for pattern in OCR_GARBAGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # Also check for excessive repetition (sign of bad OCR)
    words = text.split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:  # Less than 30% unique words
            return True

    return False


def clean_risk_data(risk_data: dict) -> tuple:
    """Clean risk_data by nullifying corrupted fields."""
    if not risk_data:
        return risk_data, 0

    cleaned = {}
    nullified_count = 0

    for key, value in risk_data.items():
        if key in OCR_CORRUPTED_FIELDS:
            if isinstance(value, str) and is_corrupted(value):
                cleaned[key] = None
                nullified_count += 1
            else:
                cleaned[key] = value
        else:
            cleaned[key] = value

    # Also clean authority if it's just "Badan Badan" or similar garbage
    if cleaned.get("authority") in ["Badan Badan", "Badan", ""]:
        cleaned["authority"] = None

    return cleaned, nullified_count


def clean_atlas(input_path: str, output_path: str) -> dict:
    """Clean the entire KBLI atlas."""

    print(f"Loading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        atlas = json.load(f)

    data = atlas.get("data", atlas)  # Handle both formats
    meta = atlas.get("meta", {})

    stats = {
        "total_entries": 0,
        "entries_with_risk_data": 0,
        "fields_nullified": 0,
        "entries_cleaned": 0,
    }

    cleaned_data = {}

    for kbli_code, entry in data.items():
        stats["total_entries"] += 1

        if entry.get("risk_data"):
            stats["entries_with_risk_data"] += 1
            cleaned_risk, nullified = clean_risk_data(entry["risk_data"])
            entry["risk_data"] = cleaned_risk

            if nullified > 0:
                stats["fields_nullified"] += nullified
                stats["entries_cleaned"] += 1

        cleaned_data[kbli_code] = entry

    # Build output
    output = {
        "meta": {
            **meta,
            "cleaning_stats": stats,
            "cleaned_fields": OCR_CORRUPTED_FIELDS,
        },
        "data": cleaned_data,
    }

    print(f"\nSaving cleaned atlas to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("CLEANING COMPLETE")
    print("="*50)
    print(f"Total entries:        {stats['total_entries']:,}")
    print(f"With risk_data:       {stats['entries_with_risk_data']:,}")
    print(f"Entries cleaned:      {stats['entries_cleaned']:,}")
    print(f"Fields nullified:     {stats['fields_nullified']:,}")
    print(f"\nOutput: {output_path}")

    return stats


if __name__ == "__main__":
    base_path = Path(__file__).parent.parent.parent / "reports" / "kbli_extraction"

    input_file = base_path / "kbli_universal_atlas_polished.json"
    output_file = base_path / "kbli_universal_atlas_clean.json"

    clean_atlas(str(input_file), str(output_file))
