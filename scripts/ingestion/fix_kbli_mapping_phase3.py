#!/usr/bin/env python3
"""
FASE 3: Fix ZOMBIE codes

ZOMBIE codes have PP28 sources but empty per_skala (no licensing requirements).

This script:
1. Fixes per_skala for aquaculture codes (03231, 03232, 03233)
2. Fixes per_skala for telecom code (61106)
3. Corrects WRONG mappings for archive codes (91121, 91122) → BPS_ONLY
4. Fixes per_skala for cultural heritage code (91300)

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
    / f"kbli_mapping_phase3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Aquaculture per_skala template (from 03221, 03222, 03223)
AQUACULTURE_PER_SKALA = [
    {
        "skala_usaha": ["Mikro", "Kecil"],
        "kategori_risiko": "Menengah Rendah",
        "perizinan": "NIB dan Sertifikat Standar",
        "persyaratan": [],
        "jangka_waktu": "Otomatis",
        "kewajiban": [
            "Laporan kegiatan usaha (LKU) dan",
            "Menerapkan cara budi daya ikan yang baik",
        ],
        "pb_umku": ["Sertifikat cara budi daya ikan yang baik"],
        "parameter": "1. Lokasi usaha berada di dalam satu daerah kabupaten/kota dan 2. Menggunakan teknologi sederhana, semi intensif, atau intensif",
        "kewenangan": "Bupati/Wali Kota",
        "sanksi_peringatan": "Peringatan tertulis",
        "sanksi_denda": "Denda administratif",
        "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
        "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
        "fiktif_positif": True,
    },
    {
        "skala_usaha": ["Menengah", "Besar"],
        "kategori_risiko": "Menengah Tinggi",
        "perizinan": "NIB dan Sertifikat Standar",
        "persyaratan": [
            "Rencana Usaha yang meliputi:",
            "Rencana kegiatan usaha",
            "Rencana tahapan kegiatan",
            "Rencana teknologi yang digunakan",
            "Sarana usaha yang dimiliki",
            "Rencana pengadaan sarana usaha",
            "Rencana volume produksi setiap tahapan kegiatan dan",
            "Rencana pembiayaan",
        ],
        "jangka_waktu": "3 Hari",
        "kewajiban": [
            "Standar proses produksi pembudidayaan air payau",
            "Laporan kegiatan usaha (LKU) dan",
            "Memiliki sertifikat cara budi daya ikan yang baik",
        ],
        "pb_umku": [],
        "parameter": "1. Lokasi usaha berada di lintas kabupaten/kota dalam satu provinsi atau lintas provinsi dan/atau 2. Menggunakan tenaga kerja asing",
        "kewenangan": "Bupati/Wali Kota",
        "sanksi_peringatan": "Peringatan tertulis",
        "sanksi_denda": "Denda administratif",
        "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
        "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
        "fiktif_positif": True,
    },
]

# IPTV per_skala template (from 61107 - telecom)
IPTV_PER_SKALA = [
    {
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
        "kategori_risiko": "Tinggi",
        "perizinan": "NIB dan Izin",
        "persyaratan": [
            "Menyampaikan komitmen layanan 5 (lima) tahun",
            "Memenuhi ketentuan konfigurasi teknis",
            "Menyampaikan daftar alat/perangkat dan sertifikat perangkat",
            "Memiliki bukti kepemilikan alat/perangkat",
            "Memiliki perjanjian kerja sama dengan penyelenggara lain",
            "Memiliki pusat kontak informasi layanan prajual dan purnajual",
            "Memperoleh surat penetapan IP Address dan AS Number",
            "Mengajukan permohonan uji laik operasi",
            "Memperoleh surat keterangan laik operasi",
        ],
        "jangka_waktu": "3 Hari",
        "kewajiban": [
            "Menggunakan alat telekomunikasi yang tersertifikasi",
            "Mengutamakan penggunaan alat produksi dalam negeri",
            "Memenuhi ketentuan Rencana Dasar Teknis Telekomunikasi Nasional",
            "Memenuhi pelayanan dan perlindungan pelanggan",
            "Memenuhi kewajiban pembayaran biaya hak penyelenggaraan telekomunikasi",
            "Memenuhi Kontribusi Kewajiban Pelayanan Universal (KPU/USO)",
            "Memenuhi standar kualitas layanan penyelenggaraan telekomunikasi",
            "Menyampaikan laporan penyelenggaraan telekomunikasi",
        ],
        "pb_umku": [],
        "parameter": "Seluruh",
        "kewenangan": "Menteri/ Kepala Badan",
        "sanksi_peringatan": "Peringatan tertulis",
        "sanksi_denda": "Denda administratif",
        "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
        "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
        "fiktif_positif": True,
    }
]

# Cultural heritage per_skala template (from 91222)
CULTURAL_PER_SKALA = [
    {
        "skala_usaha": ["Mikro", "Kecil", "Menengah", "Besar"],
        "kategori_risiko": "Menengah Rendah",
        "perizinan": "NIB dan Sertifikat Standar",
        "persyaratan": [],
        "jangka_waktu": "Otomatis",
        "kewajiban": [
            "Memiliki Dokumen Penilaian Mandiri Kesiapan Penerapan Standar usaha Konservasi Warisan Budaya",
            "Memenuhi standar pelestarian dan konservasi cagar budaya sesuai peraturan perundang-undangan",
        ],
        "pb_umku": [],
        "parameter": "Seluruh",
        "kewenangan": "Bupati/Walikota",
        "sanksi_peringatan": "Peringatan tertulis",
        "sanksi_denda": "Denda administratif",
        "sanksi_penghentian": "Penghentian sementara kegiatan usaha",
        "sanksi_pencabutan": "Pencabutan persyaratan dasar, PB, dan/atau PB UMKU",
        "fiktif_positif": True,
    }
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("FASE 3: Fix ZOMBIE codes")
    print("=" * 70)

    # Load data
    print("\n[1/4] Loading data...")
    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        items = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        items = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(items)} codes")

    # Create backup
    print("\n[2/4] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Apply fixes
    print("\n[3/4] Fixing ZOMBIE codes...")

    fixes = {"per_skala_added": [], "status_corrected": []}

    for item in items:
        code = item["kode_kbli_2025"]

        # Aquaculture codes - add per_skala
        if code in ["03231", "03232", "03233"]:
            old_per_skala = item.get("per_skala", [])
            item["per_skala"] = AQUACULTURE_PER_SKALA
            item["mapping_note"] = (
                "FASE 3: per_skala aggiunto da template acquacoltura (03221/03222/03223)"
            )
            fixes["per_skala_added"].append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "old_per_skala": old_per_skala,
                    "new_per_skala_count": len(AQUACULTURE_PER_SKALA),
                }
            )
            print(f"      ✓ {code}: per_skala aggiunto (acquacoltura)")

        # IPTV code - add per_skala
        elif code == "61106":
            old_per_skala = item.get("per_skala", [])
            item["per_skala"] = IPTV_PER_SKALA
            item["mapping_note"] = (
                "FASE 3: per_skala aggiunto da template telecom (61107)"
            )
            fixes["per_skala_added"].append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "old_per_skala": old_per_skala,
                    "new_per_skala_count": len(IPTV_PER_SKALA),
                }
            )
            print(f"      ✓ {code}: per_skala aggiunto (telecom)")

        # Archive codes - WRONG MAPPING → BPS_ONLY
        elif code in ["91121", "91122"]:
            old_pp28 = item.get("pp28_sources", [])
            old_status = item.get("status_mapping", "")

            # Correct the wrong mapping
            item["pp28_sources"] = []
            item["status_mapping"] = "BPS_ONLY"
            item["sektor_id"] = None
            item["kbli_2020_source"] = None
            item["licensing_status"] = "PENDING_REGULATION"
            item["licensing_note"] = (
                "Codice nuovo in KBLI 2025, non presente in PP 28/2025. Normativa in attesa."
            )
            item["mapping_note"] = (
                f"FASE 3: Corretto mapping errato {old_pp28} → BPS_ONLY (kearsipan non esisteva separato in KBLI 2020)"
            )

            fixes["status_corrected"].append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "old_pp28": old_pp28,
                    "old_status": old_status,
                    "new_status": "BPS_ONLY",
                    "reason": "Archives were combined with libraries in KBLI 2020 (91011/91012)",
                }
            )
            print(f"      ✓ {code}: mapping corretto {old_pp28} → BPS_ONLY")

        # Cultural heritage - add per_skala
        elif code == "91300":
            old_per_skala = item.get("per_skala", [])
            item["per_skala"] = CULTURAL_PER_SKALA
            item["mapping_note"] = (
                "FASE 3: per_skala aggiunto da template cultural heritage (91222)"
            )
            fixes["per_skala_added"].append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "old_per_skala": old_per_skala,
                    "new_per_skala_count": len(CULTURAL_PER_SKALA),
                }
            )
            print(f"      ✓ {code}: per_skala aggiunto (cultural heritage)")

    # Save
    print("\n[4/4] Saving...")
    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 3 - Fix ZOMBIE codes",
        "summary": {
            "per_skala_added": len(fixes["per_skala_added"]),
            "status_corrected": len(fixes["status_corrected"]),
            "total_fixed": len(fixes["per_skala_added"])
            + len(fixes["status_corrected"]),
        },
        "fixes": fixes,
    }
    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✓ per_skala aggiunto: {len(fixes['per_skala_added'])} codici")
    for f in fixes["per_skala_added"]:
        print(f"    {f['code']}: {f['judul'][:50]}")

    print(f"\n✓ Status corretto (→ BPS_ONLY): {len(fixes['status_corrected'])} codici")
    for f in fixes["status_corrected"]:
        print(f"    {f['code']}: {f['old_pp28']} → [] ({f['reason'][:40]}...)")

    print(f"\n✓ FASE 3 completata! Totale fix: {report['summary']['total_fixed']}")


if __name__ == "__main__":
    main()
