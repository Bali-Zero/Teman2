#!/usr/bin/env python3
"""
FASE 5B: Prediksi kemungkinan PMA untuk kode BPS_ONLY

Berdasarkan analisis pattern PMA di setiap sektor, script ini
menambahkan prediksi kemungkinan status PMA untuk kode baru.

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
    / f"kbli_mapping_phase5b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Special rules for certain sectors/codes
SPECIAL_RULES = {
    # Government - always TERTUTUP
    "84": {
        "prediksi": "TERTUTUP",
        "probabilitas": "SANGAT_TINGGI",
        "alasan": "Kegiatan pemerintah dan lembaga negara selalu tertutup untuk PMA",
    },
    # Gambling - always TERTUTUP (prohibited)
    "92": {
        "prediksi": "TERTUTUP",
        "probabilitas": "SANGAT_TINGGI",
        "alasan": "Perjudian dilarang di Indonesia",
    },
    # International organizations - TERTUTUP
    "99": {
        "prediksi": "TERTUTUP",
        "probabilitas": "SANGAT_TINGGI",
        "alasan": "Badan internasional bukan subjek investasi domestik/asing",
    },
    # Fisheries - some restrictions possible
    "03": {
        "prediksi": "TERBUKA",
        "probabilitas": "TINGGI",
        "alasan": "Sektor perikanan umumnya terbuka, namun beberapa kegiatan penangkapan memiliki batasan kemitraan",
    },
    # Travel agencies - some restrictions
    "79": {
        "prediksi": "TERBUKA",
        "probabilitas": "TINGGI",
        "alasan": "Agen perjalanan umumnya terbuka, namun mungkin memerlukan sertifikasi khusus untuk PMA",
    },
}

# Sensitive activities that might have restrictions
SENSITIVE_KEYWORDS = {
    "media": "Kegiatan media mungkin memiliki batasan kepemilikan asing",
    "siaran": "Penyiaran mungkin memiliki batasan kepemilikan asing",
    "pers": "Media pers mungkin memiliki batasan kepemilikan asing",
    "pertahanan": "Sektor pertahanan tertutup untuk PMA",
    "senjata": "Sektor persenjataan tertutup untuk PMA",
    "nuklir": "Sektor nuklir memiliki pengaturan khusus",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_sector_patterns(items):
    """Calculate PMA patterns for each sector."""
    sector_stats = {}

    for item in items:
        sector = item["kode_kbli_2025"][:2]
        pma = item.get("pma_status", "")
        status = item.get("status_mapping", "")

        # Only count non-BPS_ONLY codes for pattern analysis
        if status != "BPS_ONLY":
            if sector not in sector_stats:
                sector_stats[sector] = {
                    "TERBUKA": 0,
                    "TERBATAS": 0,
                    "TERTUTUP": 0,
                    "total": 0,
                }

            sector_stats[sector]["total"] += 1
            if pma in ["TERBUKA", "TERBATAS", "TERTUTUP"]:
                sector_stats[sector][pma] += 1

    return sector_stats


def predict_pma(item, sector_stats):
    """Predict PMA status for a BPS_ONLY code."""
    code = item["kode_kbli_2025"]
    sector = code[:2]
    judul = item.get("judul", "").upper()

    # Check special rules first
    if sector in SPECIAL_RULES:
        rule = SPECIAL_RULES[sector]
        return {
            "pma_prediksi": rule["prediksi"],
            "pma_probabilitas": rule["probabilitas"],
            "pma_alasan_prediksi": rule["alasan"],
        }

    # Check sensitive keywords
    for keyword, reason in SENSITIVE_KEYWORDS.items():
        if keyword.upper() in judul:
            return {
                "pma_prediksi": "TERBATAS",
                "pma_probabilitas": "SEDANG",
                "pma_alasan_prediksi": reason,
            }

    # Use sector pattern
    if sector in sector_stats and sector_stats[sector]["total"] > 0:
        stats = sector_stats[sector]
        total = stats["total"]

        pct_terbuka = stats["TERBUKA"] / total * 100
        pct_terbatas = stats["TERBATAS"] / total * 100
        pct_tertutup = stats["TERTUTUP"] / total * 100

        if pct_terbuka >= 95:
            return {
                "pma_prediksi": "TERBUKA",
                "pma_probabilitas": "SANGAT_TINGGI",
                "pma_alasan_prediksi": f"Sektor {sector} memiliki {pct_terbuka:.0f}% kode TERBUKA, kemungkinan besar kode baru juga TERBUKA",
            }
        elif pct_terbuka >= 80:
            return {
                "pma_prediksi": "TERBUKA",
                "pma_probabilitas": "TINGGI",
                "pma_alasan_prediksi": f"Sektor {sector} memiliki {pct_terbuka:.0f}% kode TERBUKA",
            }
        elif pct_terbuka >= 50:
            return {
                "pma_prediksi": "TERBUKA",
                "pma_probabilitas": "SEDANG",
                "pma_alasan_prediksi": f"Sektor {sector} memiliki campuran status PMA, kemungkinan TERBUKA",
            }
        elif pct_tertutup >= 80:
            return {
                "pma_prediksi": "TERTUTUP",
                "pma_probabilitas": "TINGGI",
                "pma_alasan_prediksi": f"Sektor {sector} memiliki {pct_tertutup:.0f}% kode TERTUTUP",
            }
        else:
            return {
                "pma_prediksi": "TERBATAS",
                "pma_probabilitas": "SEDANG",
                "pma_alasan_prediksi": f"Sektor {sector} memiliki campuran status PMA, mungkin ada pembatasan",
            }

    # Default - no data to predict
    return {
        "pma_prediksi": "TERBUKA",
        "pma_probabilitas": "RENDAH",
        "pma_alasan_prediksi": "Tidak cukup data sektor untuk prediksi, diasumsikan TERBUKA berdasarkan prinsip keterbukaan investasi",
    }


def main():
    print("=" * 70)
    print("FASE 5B: Prediksi kemungkinan PMA untuk kode BPS_ONLY")
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

    # Calculate sector patterns
    print("\n[2/4] Menganalisis pattern PMA per sektor...")
    sector_stats = calculate_sector_patterns(items)
    print(f"      Sektor dianalisis: {len(sector_stats)}")

    # Create backup
    print("\n[3/4] Membuat backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase5b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Add predictions
    print("\n[4/4] Menambahkan prediksi PMA...")

    predictions = {"SANGAT_TINGGI": [], "TINGGI": [], "SEDANG": [], "RENDAH": []}

    for item in items:
        if (
            item.get("status_mapping") == "BPS_ONLY"
            and item.get("pma_verification") == "PENDING"
        ):
            pred = predict_pma(item, sector_stats)
            item.update(pred)
            predictions[pred["pma_probabilitas"]].append(
                {
                    "code": item["kode_kbli_2025"],
                    "judul": item.get("judul", "")[:40],
                    "prediksi": pred["pma_prediksi"],
                    "alasan": pred["pma_alasan_prediksi"][:50],
                }
            )

    print(f"      Probabilitas SANGAT_TINGGI: {len(predictions['SANGAT_TINGGI'])}")
    print(f"      Probabilitas TINGGI: {len(predictions['TINGGI'])}")
    print(f"      Probabilitas SEDANG: {len(predictions['SEDANG'])}")
    print(f"      Probabilitas RENDAH: {len(predictions['RENDAH'])}")

    # Save
    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"\n      Diperbarui: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 5B - Prediksi kemungkinan PMA",
        "summary": {
            "sangat_tinggi": len(predictions["SANGAT_TINGGI"]),
            "tinggi": len(predictions["TINGGI"]),
            "sedang": len(predictions["SEDANG"]),
            "rendah": len(predictions["RENDAH"]),
        },
        "predictions": predictions,
    }
    save_json(report, REPORT_PATH)
    print(f"      Laporan: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("RINGKASAN PREDIKSI")
    print("=" * 70)

    print("\n=== SANGAT TINGGI (>95% yakin) ===")
    for p in predictions["SANGAT_TINGGI"][:5]:
        print(f"  {p['code']} | {p['prediksi']:8} | {p['judul']}")
    if len(predictions["SANGAT_TINGGI"]) > 5:
        print(f"  ... dan {len(predictions['SANGAT_TINGGI']) - 5} lainnya")

    print("\n=== TINGGI (80-95% yakin) ===")
    for p in predictions["TINGGI"][:5]:
        print(f"  {p['code']} | {p['prediksi']:8} | {p['judul']}")
    if len(predictions["TINGGI"]) > 5:
        print(f"  ... dan {len(predictions['TINGGI']) - 5} lainnya")

    print("\n=== SEDANG (50-80% yakin) ===")
    for p in predictions["SEDANG"][:5]:
        print(f"  {p['code']} | {p['prediksi']:8} | {p['judul']}")

    print("\n✓ FASE 5B selesai!")


if __name__ == "__main__":
    main()
