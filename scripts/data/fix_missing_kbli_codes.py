#!/usr/bin/env python3
"""
Fix Missing KBLI Codes - Quick Patch
=====================================
Adds missing KBLI codes that were lost during PDF extraction.
Source: Official BPS KBLI 2020 + PP 28/2025

Usage:
    python scripts/data/fix_missing_kbli_codes.py
"""

import json
import os
from datetime import datetime

# Missing codes identified from official sources
MISSING_CODES = {
    "55190": {
        "kode": "55190",
        "judul": "Jasa Manajemen Hotel",
        "deskripsi": (
            "Kelompok ini mencakup kegiatan usaha jasa manajemen hotel yang "
            "memberikan layanan pengelolaan operasional hotel atas nama pihak lain. "
            "Mencakup manajemen operasional, pemasaran, sumber daya manusia, "
            "keuangan, dan pengembangan bisnis hotel."
        ),
        "sektor": "Pariwisata",
        "tingkat_risiko": "Rendah",
        "kepemilikan_asing": {
            "pma_diizinkan": True,
            "maksimum": "100%",
            "catatan": "Terbuka untuk investasi asing",
        },
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
        "perizinan_berusaha": {
            "dokumen_wajib": [
                "NIB (Nomor Induk Berusaha)",
                "Sertifikat Standar Usaha Pariwisata",
                "Dokumen Penilaian Mandiri",
            ],
            "kewenangan": "Bupati/Walikota (Lokal), Menteri (PMA)",
        },
        "source": "BPS_KBLI_2020 + PP_28_2025",
        "added_by": "fix_missing_kbli_codes.py",
        "added_at": datetime.now().isoformat(),
    }
}


def load_existing_kbli(filepath: str) -> dict:
    """Load existing KBLI JSON file."""
    if not os.path.exists(filepath):
        return {"metadata": {}, "kbli_codes": {}}

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_missing_codes(existing: dict, missing: dict) -> dict:
    """Merge missing codes into existing dataset."""
    codes = existing.get("kbli_codes", {})

    added = []
    for code, info in missing.items():
        if code not in codes:
            codes[code] = info
            added.append(code)
            print(f"✅ Added: {code} - {info['judul']}")
        else:
            print(f"⏭️ Skipped (exists): {code}")

    existing["kbli_codes"] = codes

    # Update metadata
    if "metadata" not in existing:
        existing["metadata"] = {}
    existing["metadata"]["last_fix_applied"] = datetime.now().isoformat()
    existing["metadata"]["codes_added"] = added
    existing["metadata"]["total_codes"] = len(codes)

    return existing


def main():
    # Find the KBLI JSON file
    possible_paths = [
        "apps/kb/data/04_aziende/kbli/KBLI_2025_ULTIMATE_COMPLETE.json",
        "data/kbli/kbli_complete.json",
        "apps/backend-rag/data/kbli.json",
    ]

    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    target_file = None
    for path in possible_paths:
        full_path = os.path.join(base_dir, path)
        if os.path.exists(full_path):
            target_file = full_path
            break

    if not target_file:
        # Create new file in data directory
        target_file = os.path.join(base_dir, "data/kbli/kbli_complete.json")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        print(f"Creating new KBLI file: {target_file}")

    print(f"Target file: {target_file}")

    # Load and merge
    existing = load_existing_kbli(target_file)
    updated = merge_missing_codes(existing, MISSING_CODES)

    # Save
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Fixed! Total codes: {updated['metadata']['total_codes']}")
    print(f"📁 Saved to: {target_file}")

    # Also output for direct Qdrant ingestion
    print("\n--- For direct Qdrant upsert ---")
    for code, info in MISSING_CODES.items():
        context = f"[CONTEXT: KBLI 2025 - PP 28/2025 - SEKTOR {info['sektor']} - KODE {code} - RISIKO {info['tingkat_risiko']}]"
        content = f"""
{context}

# KBLI {code}: {info["judul"]}

## Deskripsi
{info["deskripsi"]}

## Informasi PP 28/2025
- **Tingkat Risiko**: {info["tingkat_risiko"]}
- **Investasi Asing (PMA)**: {"✅ Diizinkan" if info["kepemilikan_asing"]["pma_diizinkan"] else "❌ Tidak Diizinkan"}
- **Batas Maksimum PMA**: {info["kepemilikan_asing"]["maksimum"]}
- **Skala Usaha**: {", ".join(info["skala_usaha"])}

## Perizinan
- **Dokumen Wajib**: {", ".join(info["perizinan_berusaha"]["dokumen_wajib"])}
- **Kewenangan**: {info["perizinan_berusaha"]["kewenangan"]}

---
Sumber: {info["source"]}
"""
        print(content)


if __name__ == "__main__":
    main()
