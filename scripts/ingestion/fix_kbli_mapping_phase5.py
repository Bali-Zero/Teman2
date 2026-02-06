#!/usr/bin/env python3
"""
FASE 5: Tandai status PMA untuk kode BPS_ONLY

Kode BPS_ONLY adalah kode baru di KBLI 2025 yang tidak ada di KBLI 2020.
Perpres 10/2021, 49/2021, 14/2024 menggunakan kode KBLI 2020.
Jadi status PMA untuk kode BPS_ONLY belum diatur dalam Perpres.

Script ini menambahkan catatan untuk kode BPS_ONLY yang ditandai TERBUKA.

Author: Zantara AI
Date: 2026-02-04
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
    / f"kbli_mapping_phase5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("FASE 5: Tandai status PMA untuk kode BPS_ONLY")
    print("=" * 70)

    # Load data
    print("\n[1/4] Memuat data...")
    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        items = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        items = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(items)} kode")

    # Create backup
    print("\n[2/4] Membuat backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Update PMA notes for BPS_ONLY codes
    print("\n[3/4] Memperbarui catatan PMA untuk kode BPS_ONLY...")

    updated_terbuka = []
    updated_tertutup = []
    unchanged = []

    for item in items:
        code = item["kode_kbli_2025"]
        status = item.get("status_mapping", "")
        pma = item.get("pma_status", "")

        if status == "BPS_ONLY":
            if pma == "TERBUKA":
                # Add note that this is presumed TERBUKA pending new Perpres
                item["pma_nota"] = (
                    "Kode baru KBLI 2025, belum diatur dalam Perpres DNI/DPI. Status TERBUKA bersifat sementara menunggu penetapan resmi."
                )
                item["pma_verification"] = "PENDING"
                updated_terbuka.append(
                    {"code": code, "judul": item.get("judul", "")[:50]}
                )
            elif pma == "TERTUTUP":
                # Government codes - TERTUTUP is logical
                item["pma_nota"] = (
                    "Kegiatan pemerintah/lembaga negara, tertutup untuk investasi asing."
                )
                item["pma_verification"] = "CONFIRMED"
                updated_tertutup.append(
                    {"code": code, "judul": item.get("judul", "")[:50]}
                )
        else:
            unchanged.append(code)

    print(f"      BPS_ONLY TERBUKA (ditandai PENDING): {len(updated_terbuka)}")
    print(f"      BPS_ONLY TERTUTUP (dikonfirmasi): {len(updated_tertutup)}")
    print(f"      Kode lainnya (tidak diubah): {len(unchanged)}")

    # Save
    print("\n[4/4] Menyimpan...")
    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"      Diperbarui: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 5 - Tandai status PMA untuk kode BPS_ONLY",
        "summary": {
            "bps_only_terbuka_pending": len(updated_terbuka),
            "bps_only_tertutup_confirmed": len(updated_tertutup),
            "unchanged": len(unchanged),
        },
        "updated_terbuka": updated_terbuka,
        "updated_tertutup": updated_tertutup,
    }
    save_json(report, REPORT_PATH)
    print(f"      Laporan: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("RINGKASAN")
    print("=" * 70)

    print(f"\n✓ BPS_ONLY TERBUKA: {len(updated_terbuka)} kode")
    print("  Ditambahkan:")
    print("  - pma_nota: 'Kode baru KBLI 2025, belum diatur dalam Perpres...'")
    print("  - pma_verification: 'PENDING'")

    print(f"\n✓ BPS_ONLY TERTUTUP: {len(updated_tertutup)} kode")
    print("  Ditambahkan:")
    print("  - pma_nota: 'Kegiatan pemerintah/lembaga negara...'")
    print("  - pma_verification: 'CONFIRMED'")

    print("\n✓ FASE 5 selesai!")


if __name__ == "__main__":
    main()
