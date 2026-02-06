#!/usr/bin/env python3
"""
Fix truncated uraian descriptions for 5 KBLI codes.

Source: BPS KBLI 2025 official data (notebooklm_full_bps2025.json)

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
    / f"kbli_uraian_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Complete descriptions from BPS source
URAIAN_FIXES = {
    "28140": """Kelompok ini mencakup - pembuatan bola dan bantalan poros (ball and roller bearings), termasuk bola, bantalan guling, ring dan bagian-bagian lain dari bearings; - pembuatan gigi, roda gigi, kotak gigi dan pemindah kecepatan lainnya; - pembuatan kopling dan poros kopling; - pembuatan roda gendeng dan kerek/katrol; - pembuatan mata rantai bersambung; - pembuatan rantai transmisi tenaga (rantai keteng). Kelompok ini juga mencakup - pembuatan komponen dan suku cadang peralatan transmisi mekanik, antara lain cam shafts, poros engkol (crank shafts), engkol, kerangka bearing dan bearing poros sederhana, persneling, roda gigi, bantalan blok, kopling dan poros kopling, roda gendeng dan kerek/katrol, mata rantai bersambung, rantai transmisi tenaga (rantai keteng), dan sebagainya. Kelompok ini tidak mencakup - pembuatan rantai lainnya, lihat subgolongan 2595; - pembuatan peralatan transmisi hidrolik, lihat subgolongan 2812; - pembuatan transmisi hidrostatik, lihat subgolongan 2812; - pembuatan kopling untuk kendaraan bermotor, lihat subgolongan 2930; - pembuatan roda gigi, kotak roda gigi, dan sebagainya untuk kendaraan bermotor, lihat subgolongan 2930; - pembuatan sub rakitan peralatan transmisi tenaga yang cocok digunakan atau terutama dengan motor sebagai bagian dari kendaraan atau pesawat terbang, lihat golongan pokok 29 dan 30.""",
    "32120": """Kelompok ini mencakup - pembuatan perhiasan imitasi yang tidak mengandung mutiara (baik alami maupun hasil budi daya), batu mulia atau semimulia, atau (kecuali sebagai pelapisan atau sebagai bahan tambahan) logam mulia atau logam yang dilapisi logam mulia, seperti cincin, gelang, bros, anting, kalung dan barang-barang kecil sejenisnya, serta barang perhiasan pribadi yang dibuat dari logam dasar yang dilapisi logam mulia; dan perhiasan imitasi yang mengandung batu imitasi (seperti batu permata imitasi dan berlian imitasi); - pembuatan tali jam tangan dari logam (kecuali logam mulia). Kelompok ini tidak mencakup - pembuatan perhiasan yang dibuat dari logam mulia atau logam dasar yang dicampur logam mulia, lihat subgolongan 3211; - pembuatan perhiasan yang mengandung batu permata asli, lihat subgolongan 3211; - pembuatan tali jam tangan dari logam mulia, lihat subgolongan 3211.""",
    "52233": """Kelompok ini mencakup - pelayanan teknis dan operasional untuk mendukung operasional pesawat udara di darat untuk penumpang dan kargo (ground handling), termasuk pengisian bahan bakar, pengisian air, penanganan limbah, serta pemindahan pesawat; - pelayanan penumpang di bandara, seperti proses check-in, boarding, dan transit; - penanganan bagasi, kargo, dan pos, baik untuk proses muat maupun bongkar; - pemeriksaan barang muatan dalam kargo dan/atau peti kemas dengan menggunakan sumber radiasi pengion (zat radioaktif dan pembangkit radiasi pengion). Kelompok ini juga mencakup - layanan dokumentasi, penimbangan, pengamanan, serta penanganan khusus terhadap barang berbahaya atau bernilai tinggi.""",
    "90310": """Kelompok ini mencakup - pengoperasian fasilitas kesenian, seperti auditorium (hall) untuk pertunjukan konser dan teater, serta pusat kebudayaan/taman budaya; - pengoperasian fasilitas kesenian yang mendukung penciptaan karya seni rupa dan fasilitas kesenian lainnya. Kelompok ini juga mencakup - pengoperasian lokasi (venue) pertunjukan live music, klub musik, tempat seniman melakukan pertunjukan dan fasilitas yang sejenis. Kelompok ini tidak mencakup: - perdagangan eceran lukisan dan patung (aktivitas komersial galeri kesenian), lihat subgolongan 4769; - pengoperasian gedung bioskop, lihat subgolongan 5914; - pemesanan dan penjualan tiket pertunjukan teater, olahraga, serta aktivitas hiburan dan rekreasi lainnya, lihat subgolongan 7990; - pengoperasian fasilitas seni yang digunakan untuk kelompok seninya sendiri, lihat subgolongan 9020; - pengoperasian berbagai jenis museum, lihat subgolongan 9020; - pengoperasian lantai dansa dan ballroom, dengan penyajian minuman bukan sebagai aktivitas utama, lihat subgolongan 9329.""",
    "96210": """Kelompok ini mencakup - pencucian rambut, pemangkasan dan pemotongan, penataan, pengecatan, pewarnaan, pengeritingan, pelurusan dan aktivitas sejenisnya; - penataan rambut; - pencukuran dan perapihan jenggot, kumis, jambang. Kelompok ini tidak mencakup - pembuatan wig, lihat subgolongan 3290.""",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("FIX: Descrizioni uraian troncate")
    print("=" * 70)

    # Load data
    print("\n[1/3] Caricamento dati...")
    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        items = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        items = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(items)} codici")

    # Create backup
    print("\n[2/3] Creazione backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_uraian_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Fix descriptions
    print("\n[3/3] Correzione descrizioni...")

    fixed = []
    for item in items:
        code = item["kode_kbli_2025"]
        if code in URAIAN_FIXES:
            old_uraian = item.get("uraian", "")
            new_uraian = URAIAN_FIXES[code]
            item["uraian"] = new_uraian
            fixed.append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "old_length": len(old_uraian),
                    "new_length": len(new_uraian),
                }
            )
            print(f"      ✓ {code}: {len(old_uraian)} → {len(new_uraian)} caratteri")

    # Save
    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"\n      Aggiornato: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "fix": "Correzione descrizioni uraian troncate",
        "source": "BPS KBLI 2025 official (notebooklm_full_bps2025.json)",
        "fixed_codes": fixed,
    }
    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    print("\n" + "=" * 70)
    print(f"✓ Corretti {len(fixed)} codici con descrizioni complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
