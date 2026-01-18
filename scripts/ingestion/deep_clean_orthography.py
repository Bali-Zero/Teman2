#!/usr/bin/env python3
"""
Deep Clean Orthography
Advanced text repair for KBLI Atlas: fixes OCR typos, normalization, and formatting.
"""

import json
import re
import os

ATLAS_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_polished.json"

# Common OCR Typos in Indonesian Regulatory Text
TYPO_CORRECTIONS = {
    r"\bda1am\b": "dalam",
    r"\blndustri\b": "Industri",
    r"\bPerdagangarr\b": "Perdagangan",
    r"\bPertanianr\b": "Pertanian",
    r"\bsen1diri\b": "sendiri",
    r"\bpema1saran\b": "pemasaran",
    r"\bBupat\b": "Bupati",
    r"\bWalikota\b": "Wali Kota",  # Standardizing to Baku
    r"\bSertifkkat\b": "Sertifikat",
    r"\bSertifkat\b": "Sertifikat",
    r"\bStandarr\b": "Standar",
    r"\bOtomaits\b": "Otomatis",
    r"\bOtomatls\b": "Otomatis",
    r"\bOtomatisS\b": "Otomatis",
    r"\bVerifkasi\b": "Verifikasi",
    r"\bVeriflkasi\b": "Verifikasi",
    r"\bMenengahh\b": "Menengah",
    r"\bRenda\b": "Rendah",  # Use caution
    r"\bNlB\b": "NIB",
    r"\bN IB\b": "NIB",
    r"\bU MKU\b": "UMKU",
    r"\bPerizinan Berusaha Untuk Menunjang Kegiatan Usaha\b": "PB-UMKU",  # Shorten
}

# Regex for formatting
SPACE_BEFORE_PUNCT = r"\s+([,.;:])"  # "Word ," -> "Word,"
MULTIPLE_SPACES = r"\s{2,}"  # "  " -> " "


def fix_typos(text):
    if not isinstance(text, str):
        return text

    # Apply standard whitespace fixes first
    text = re.sub(MULTIPLE_SPACES, " ", text).strip()
    text = re.sub(SPACE_BEFORE_PUNCT, r"\1", text)

    # Specific Dictionary Repairs
    for pattern, replacement in TYPO_CORRECTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Formatting Lists: Ensure "1. " spacing
    text = re.sub(r"(?<!\d)(\d+)\.(?!\d)\s*", r"\1. ", text)

    return text


def deep_clean():
    print("🧹 Starting Deep Orthography Clean...")

    if not os.path.exists(ATLAS_PATH):
        print("❌ Atlas not found!")
        return

    data = json.load(open(ATLAS_PATH))
    records = data["data"]

    cleaned_count = 0

    for code, record in records.items():
        original_record = json.dumps(record)

        # Clean basic fields
        if record.get("title"):
            record["title"] = fix_typos(record["title"])
        if record.get("sektor"):
            record["sektor"] = fix_typos(record["sektor"])

        # Clean Risk Data
        risk_data = record.get("risk_data")
        if risk_data:
            for k, v in risk_data.items():
                if isinstance(v, str):
                    risk_data[k] = fix_typos(v)
                elif isinstance(v, list):
                    risk_data[k] = [fix_typos(i) for i in v]

        # If changed, count it
        if json.dumps(record) != original_record:
            cleaned_count += 1

    # Save In-Place
    with open(ATLAS_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✨ Cleaned {cleaned_count} records.")
    print("💾 Atlas Updated In-Place.")


if __name__ == "__main__":
    deep_clean()
