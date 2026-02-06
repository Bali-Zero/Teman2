#!/usr/bin/env python3
"""
FASE 1 FINAL: Fix the 14 remaining mapping errors found by verification agents.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
KBLI_2025_PATH = BASE_DIR / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
REPORT_PATH = (
    BASE_DIR
    / "reports"
    / f"kbli_mapping_phase1_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Final fixes from verification agents
FINAL_FIXES = {
    # HOTEL
    "55201": {"kbli_2020": "55130", "title": "Pondok Wisata", "confidence": "high"},
    "55106": {"kbli_2020": "55120", "title": "Hotel Melati", "confidence": "high"},
    # FINANCE
    "64124": {
        "kbli_2020": "64122",
        "title": "Bank Umum Syariah",
        "confidence": "medium",
    },
    "64310": {
        "kbli_2020": "64300",
        "title": "Trust, Pendanaan dan Entitas Keuangan Sejenis",
        "confidence": "medium",
    },
    "64920": {
        "kbli_2020": "64991",
        "title": "Lembaga Pembiayaan Ekspor Indonesia",
        "confidence": "high",
    },
    "64930": {
        "kbli_2020": "64911",
        "title": "Perusahaan Pembiayaan Konvensional",
        "confidence": "high",
    },
    "64940": {
        "kbli_2020": "64992",
        "title": "Perusahaan Pembiayaan Sekunder Perumahan",
        "confidence": "high",
    },
    "64959": {
        "kbli_2020": "64951",
        "title": "Fintech P2P Lending Konvensional",
        "confidence": "medium",
    },
    # INDUSTRY
    "13139": {
        "kbli_2020": "13132",
        "title": "Industri Penyempurnaan Kain",
        "confidence": "high",
    },
    "20229": {
        "kbli_2020": "20221",
        "title": "Industri Cat dan Tinta Cetak",
        "confidence": "high",
    },
    "20297": {
        "kbli_2020": "19291",
        "title": "Industri Produk Dari Hasil Kilang Minyak Bumi",
        "confidence": "high",
    },
    "23991": {
        "kbli_2020": "23990",
        "title": "Industri Barang Galian Bukan Logam Lainnya",
        "confidence": "high",
    },
    "23993": {
        "kbli_2020": "23990",
        "title": "Industri Barang Galian Bukan Logam Lainnya",
        "confidence": "medium",
    },
    "26703": {
        "kbli_2020": "26792",
        "title": "Industri Teropong Dan Instrumen Optik",
        "confidence": "high",
    },
}


def main():
    print("=" * 70)
    print("FASE 1 FINAL: Fix remaining 14 mapping errors")
    print("=" * 70)

    # Load
    print("\n[1/4] Loading data...")
    with open(KBLI_2025_PATH, "r") as f:
        raw = json.load(f)

    items = raw.get("data", raw) if isinstance(raw, dict) else raw
    is_wrapped = isinstance(raw, dict) and "data" in raw
    print(f"      Loaded {len(items)} codes")

    # Backup
    print("\n[2/4] Creating backup...")
    backup = KBLI_2025_PATH.with_suffix(
        f".backup_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup)
    print(f"      Backup: {backup.name}")

    # Apply fixes
    print("\n[3/4] Applying final fixes...")
    applied = []

    for item in items:
        code = item.get("kode_kbli_2025", "")
        if code in FINAL_FIXES:
            fix = FINAL_FIXES[code]
            old_pp28 = item.get("pp28_sources", [])

            item["pp28_sources"] = [fix["kbli_2020"]]
            item["status_mapping"] = "CODICE_RINUMERATO"
            item["kbli_2020_source"] = fix["kbli_2020"]
            item["mapping_note"] = (
                f"Final fix: {fix['kbli_2020']} ({fix['title']}) [{fix['confidence']}]"
            )

            applied.append(
                {
                    "code": code,
                    "old": old_pp28,
                    "new": [fix["kbli_2020"]],
                    "title_2020": fix["title"],
                }
            )
            print(f"      ✓ {code}: {old_pp28} → [{fix['kbli_2020']}]")

    # Save
    print("\n[4/4] Saving...")
    if is_wrapped:
        raw["data"] = items

    with open(KBLI_2025_PATH, "w") as f:
        json.dump(raw if is_wrapped else items, f, ensure_ascii=False, indent=2)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 1 FINAL",
        "fixes_applied": applied,
        "total": len(applied),
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"      Report: {REPORT_PATH.name}")

    print(f"\n✓ Applied {len(applied)} final fixes")


if __name__ == "__main__":
    main()
