#!/usr/bin/env python3
"""
FASE 1C: Apply manual mappings from AI agents for remaining 67 problematic codes.
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
    / f"kbli_mapping_phase1c_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Mappings from AI agents
AGENT_MAPPINGS = {
    # === BATCH 1: Finance/Tech (Agent 1) ===
    "64191": {
        "kbli_2020": "64190",
        "title_2020": "Perantara moneter lainnya",
        "confidence": "high",
    },
    "64320": {
        "kbli_2020": "64300",
        "title_2020": "Trust, Pendanaan dan Entitas Keuangan Sejenis",
        "confidence": "high",
    },
    "64330": {
        "kbli_2020": "64300",
        "title_2020": "Trust, Pendanaan dan Entitas Keuangan Sejenis",
        "confidence": "high",
    },
    "64910": {
        "kbli_2020": "64911",
        "title_2020": "Perusahaan Pembiayaan Konvensional",
        "confidence": "high",
    },
    "64955": {
        "kbli_2020": "64992",
        "title_2020": "Perusahaan Pembiayaan Sekunder Perumahan",
        "confidence": "medium",
    },
    "64993": {
        "kbli_2020": "66112",
        "title_2020": "Lembaga Kliring dan Penjaminan Efek",
        "confidence": "high",
    },
    "64994": {
        "kbli_2020": "66142",
        "title_2020": "Perantara Pedagang Efek (Broker Dealer)",
        "confidence": "high",
    },
    "66127": {
        "kbli_2020": "66159",
        "title_2020": "Perantara Perdagangan Berjangka Komoditi Lainnya",
        "confidence": "medium",
    },
    "66129": {
        "kbli_2020": "66152",
        "title_2020": "Pialang Perdagangan Berjangka",
        "confidence": "high",
    },
    "66133": {
        "kbli_2020": "66191",
        "title_2020": "Biro Administrasi Efek",
        "confidence": "high",
    },
    "66161": {
        "kbli_2020": "64951",
        "title_2020": "Fintech P2P Lending Konvensional",
        "confidence": "high",
    },
    "66162": {
        "kbli_2020": "64952",
        "title_2020": "Fintech P2P Lending Syariah",
        "confidence": "high",
    },
    "66196": {
        "kbli_2020": "66141",
        "title_2020": "Penjamin Emisi Efek (Underwriter)",
        "confidence": "high",
    },
    "66198": {
        "kbli_2020": "66292",
        "title_2020": "Aktivitas Pemeringkat UMKM dan Koperasi",
        "confidence": "high",
    },
    "66301": {
        "kbli_2020": "66311",
        "title_2020": "Manajer Investasi",
        "confidence": "high",
    },
    # === BATCH 2: Industry (Agent 2) ===
    "10111": {
        "kbli_2020": "10110",
        "title_2020": "Kegiatan Rumah Potong Dan Pengepakan Daging Bukan Unggas",
        "confidence": "high",
    },
    "10112": {
        "kbli_2020": "10110",
        "title_2020": "Kegiatan Rumah Potong Dan Pengepakan Daging Bukan Unggas",
        "confidence": "high",
    },
    "10218": {
        "kbli_2020": "10219",
        "title_2020": "Industri Pengolahan Dan Pengawetan Lainnya untuk Ikan",
        "confidence": "high",
    },
    "10504": {
        "kbli_2020": "10532",
        "title_2020": "Industri Pengolahan Es Sejenisnya Yang Dapat Dimakan",
        "confidence": "high",
    },
    "10797": {
        "kbli_2020": "10762",
        "title_2020": "Industri Pengolahan Herbal (herb infusion)",
        "confidence": "high",
    },
    "10798": {
        "kbli_2020": "10298",
        "title_2020": "Industri pengolahan rumput laut",
        "confidence": "high",
    },
    "20235": {
        "kbli_2020": "20232",
        "title_2020": "Industri Kosmetik Untuk Manusia, Termasuk Pasta Gigi",
        "confidence": "high",
    },
    "22129": {
        "kbli_2020": "22199",
        "title_2020": "Industri Barang Dari Karet Lainnya Ytdl",
        "confidence": "medium",
    },
    "23935": {
        "kbli_2020": "23923",
        "title_2020": "Industri Peralatan Saniter Dari Porselen",
        "confidence": "high",
    },
    "23992": {
        "kbli_2020": "23990",
        "title_2020": "Industri Barang Galian Bukan Logam Lainnya Ytdl",
        "confidence": "high",
    },
    "26191": {
        "kbli_2020": "26110",
        "title_2020": "Industri Tabung Elektron Dan Konektor Elektronik",
        "confidence": "high",
    },
    "26519": {
        "kbli_2020": "26513",
        "title_2020": "Industri Alat Ukur Dan Alat Uji Elektronik",
        "confidence": "medium",
    },
    "30301": {
        "kbli_2020": "30300",
        "title_2020": "Industri Pesawat Terbang Dan Perlengkapannya",
        "confidence": "high",
    },
    "30302": {
        "kbli_2020": "30300",
        "title_2020": "Industri Pesawat Terbang Dan Perlengkapannya",
        "confidence": "high",
    },
    "32908": {
        "kbli_2020": "32909",
        "title_2020": "Industri Pengolahan Lainnya YTDL",
        "confidence": "high",
    },
    # === BATCH 3: Transport/Logistics (Agent 3) ===
    "49119": {
        "kbli_2020": "49110",
        "title_2020": "Angkutan Jalan Rel untuk Penumpang",
        "confidence": "high",
    },
    "50124": {
        "kbli_2020": "50135",
        "title_2020": "Angkutan Laut Dalam Negeri Pelayaran Rakyat",
        "confidence": "high",
    },
    "50127": {
        "kbli_2020": "50143",
        "title_2020": "Angkutan Laut Luar Negeri Pelayaran Rakyat",
        "confidence": "high",
    },
    "50149": {
        "kbli_2020": "50229",
        "title_2020": "Angkutan Penyeberangan Lainnya untuk Barang",
        "confidence": "medium",
    },
    "52226": {
        "kbli_2020": "52229",
        "title_2020": "Aktivitas Penunjang Angkutan Perairan Lainnya",
        "confidence": "high",
    },
    "52233": {
        "kbli_2020": "52231",
        "title_2020": "Aktivitas Kebandarudaraan",
        "confidence": "high",
    },
    "52234": {
        "kbli_2020": "52296",
        "title_2020": "Jasa Penunjang Angkutan Udara",
        "confidence": "high",
    },
    "52313": {
        "kbli_2020": "52294",
        "title_2020": "Aktivitas Ekspedisi Muatan Pesawat Udara (EMPU)",
        "confidence": "high",
    },
    "52319": {
        "kbli_2020": "52291",
        "title_2020": "Jasa Pengurusan Transportasi (JPT)",
        "confidence": "high",
    },
    "52323": {
        "kbli_2020": "52296",
        "title_2020": "Jasa Penunjang Angkutan Udara",
        "confidence": "high",
    },
    "53301": {
        "kbli_2020": "53201",
        "title_2020": "Aktivitas Kurir",
        "confidence": "medium",
    },
    "53309": {
        "kbli_2020": "53202",
        "title_2020": "Aktivitas Agen Kurir",
        "confidence": "medium",
    },
    # === BATCH 4: Real Estate/Services (Agent 4) ===
    "01615": {
        "kbli_2020": "01612",
        "title_2020": "Jasa Pemupukan, Penanaman Bibit/Benih Dan Pengendalian Hama",
        "confidence": "high",
    },
    "01700": {
        "kbli_2020": "01711",
        "title_2020": "Perburuan dan Penangkapan Primata",
        "confidence": "high",
    },
    "05102": {
        "kbli_2020": "05100",
        "title_2020": "Pertambangan Batu Bara",
        "confidence": "high",
    },
    "46739": {
        "kbli_2020": "46639",
        "title_2020": "Perdagangan Besar Bahan Konstruksi Lainnya",
        "confidence": "medium",
    },
    "58211": {
        "kbli_2020": "58200",
        "title_2020": "Penerbitan piranti lunak (Software)",
        "confidence": "high",
    },
    "58219": {
        "kbli_2020": "58200",
        "title_2020": "Penerbitan piranti lunak (Software)",
        "confidence": "high",
    },
    "60103": {
        "kbli_2020": "60102",
        "title_2020": "Penyiaran Radio Oleh Swasta",
        "confidence": "medium",
    },
    "60203": {
        "kbli_2020": "60202",
        "title_2020": "Aktivitas Penyiaran dan Pemrograman Televisi Oleh Swasta",
        "confidence": "medium",
    },
    "61107": {
        "kbli_2020": "61924",
        "title_2020": "Jasa Interkoneksi Internet (NAP)",
        "confidence": "high",
    },
    "68123": {
        "kbli_2020": "68130",
        "title_2020": "Kawasan Industri",
        "confidence": "medium",
    },
    "68126": {
        "kbli_2020": "52101",
        "title_2020": "Pergudangan dan Penyimpanan",
        "confidence": "high",
    },
    "68127": {
        "kbli_2020": "68111",
        "title_2020": "Real Estat Yang Dimiliki Sendiri Atau Disewa",
        "confidence": "high",
    },
    "68129": {
        "kbli_2020": "68111",
        "title_2020": "Real Estat Yang Dimiliki Sendiri Atau Disewa",
        "confidence": "high",
    },
    "68291": {
        "kbli_2020": "68200",
        "title_2020": "Real Estat Atas Dasar Balas Jasa",
        "confidence": "high",
    },
    "68292": {
        "kbli_2020": "68200",
        "title_2020": "Real Estat Atas Dasar Balas Jasa",
        "confidence": "high",
    },
    "71109": {
        "kbli_2020": "71102",
        "title_2020": "Aktivitas Keinsinyuran dan Konsultasi Teknis YBDI",
        "confidence": "high",
    },
    "82921": {
        "kbli_2020": "82920",
        "title_2020": "Aktivitas Pengepakan",
        "confidence": "high",
    },
    "82922": {
        "kbli_2020": "82920",
        "title_2020": "Aktivitas Pengepakan",
        "confidence": "high",
    },
    "82923": {
        "kbli_2020": "82920",
        "title_2020": "Aktivitas Pengepakan",
        "confidence": "high",
    },
    "82924": {
        "kbli_2020": "82920",
        "title_2020": "Aktivitas Pengepakan",
        "confidence": "high",
    },
    "82925": {
        "kbli_2020": "82920",
        "title_2020": "Aktivitas Pengepakan",
        "confidence": "high",
    },
    "85324": {
        "kbli_2020": "85230",
        "title_2020": "Pendidikan Menengah Kejuruan",
        "confidence": "medium",
    },
    "85330": {
        "kbli_2020": "85499",
        "title_2020": "Pendidikan Lainnya YTDL",
        "confidence": "low",
    },
    "91300": {
        "kbli_2020": "91039",
        "title_2020": "Aktivitas Kawasan Alam Lainnya",
        "confidence": "medium",
    },
    "93196": {
        "kbli_2020": "93244",
        "title_2020": "Kolam Pemancingan",
        "confidence": "high",
    },
    "93197": {
        "kbli_2020": "93192",
        "title_2020": "Olahragawan, Juri dan Wasit Profesional",
        "confidence": "high",
    },
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
    print("FASE 1C: Apply AI agent mappings")
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
    print(f"      Agent mappings: {len(AGENT_MAPPINGS)} codes")

    # Create backup
    print("\n[2/4] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase1c_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Apply mappings
    print("\n[3/4] Applying agent mappings...")
    applied = []
    not_found = []

    for code_2025, mapping in AGENT_MAPPINGS.items():
        # Find the item
        item = next((i for i in items if i["kode_kbli_2025"] == code_2025), None)
        if not item:
            not_found.append(code_2025)
            continue

        old_pp28 = item.get("pp28_sources", [])
        old_status = item.get("status_mapping", "")

        # Apply fix
        item["pp28_sources"] = [mapping["kbli_2020"]]
        item["status_mapping"] = "CODICE_RINUMERATO"
        item["kbli_2020_source"] = mapping["kbli_2020"]
        item["mapping_note"] = (
            f"Agent mapping: {mapping['kbli_2020']} ({mapping['title_2020'][:30]}...) [{mapping['confidence']}]"
        )
        if "needs_review" in item:
            del item["needs_review"]

        applied.append(
            {
                "code_2025": code_2025,
                "old_pp28": old_pp28,
                "new_pp28": [mapping["kbli_2020"]],
                "kbli_2020_title": mapping["title_2020"],
                "confidence": mapping["confidence"],
            }
        )

    print(f"      Applied: {len(applied)}")
    print(f"      Not found: {len(not_found)}")

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
        "phase": "FASE 1C - Apply AI agent mappings",
        "summary": {
            "total_mappings": len(AGENT_MAPPINGS),
            "applied": len(applied),
            "not_found": len(not_found),
            "by_confidence": {
                "high": len([a for a in applied if a["confidence"] == "high"]),
                "medium": len([a for a in applied if a["confidence"] == "medium"]),
                "low": len([a for a in applied if a["confidence"] == "low"]),
            },
        },
        "applied": applied,
        "not_found": not_found,
    }
    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✓ Applied: {len(applied)} mappings")
    print(f"  - High confidence: {report['summary']['by_confidence']['high']}")
    print(f"  - Medium confidence: {report['summary']['by_confidence']['medium']}")
    print(f"  - Low confidence: {report['summary']['by_confidence']['low']}")

    if not_found:
        print(f"\n⚠ Not found in KBLI 2025: {not_found}")

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
