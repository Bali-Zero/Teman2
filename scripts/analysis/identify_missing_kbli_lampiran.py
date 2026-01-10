#!/usr/bin/env python3
"""
Identifica quali KBLI della master list BPS mancano da Lampiran I
e dove potrebbero essere trovati (altri Lampiran, sezioni PP 28/2025, etc.).
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def load_gap_analysis() -> Dict:
    """Carica il report di gap analysis."""
    gap_file = DATA_DIR / "kbli_complete_gap_analysis.json"
    
    if not gap_file.exists():
        print(f"❌ File gap analysis non trovato: {gap_file}")
        print("   Esegui prima: python3 scripts/analysis/analyze_kbli_complete_gap.py")
        sys.exit(1)
    
    with open(gap_file) as f:
        return json.load(f)


def load_bps_master_list() -> Dict[str, Dict]:
    """Carica master list BPS."""
    bps_file = DATA_DIR / "bps_master_list_complete.json"
    
    if not bps_file.exists():
        print(f"❌ File BPS master list non trovato: {bps_file}")
        sys.exit(1)
    
    with open(bps_file) as f:
        data = json.load(f)
        return data.get("kbli_data", {})


def identify_missing_sources():
    """Identifica dove potrebbero essere i KBLI mancanti."""
    print("=" * 70)
    print("🔍 IDENTIFICAZIONE KBLI MANCANTI DA LAMPIRAN I")
    print("=" * 70)
    print()
    
    # Carica dati
    gap_data = load_gap_analysis()
    bps_kbli = load_bps_master_list()
    
    missing_codes = gap_data["gap_analysis"]["missing_from_lampiran"]
    missing_count = gap_data["gap_analysis"]["missing_from_lampiran_count"]
    
    print(f"📊 KBLI mancanti da Lampiran I: {missing_count}")
    print()
    
    # Analisi per prefisso
    print("1️⃣  ANALISI PER PREFISSO:")
    prefix_groups = defaultdict(list)
    
    for code in missing_codes:
        prefix = code[:2]
        prefix_groups[prefix].append(code)
    
    print("\n   Top 15 prefissi con più KBLI mancanti:")
    sorted_prefixes = sorted(prefix_groups.items(), key=lambda x: -len(x[1]))[:15]
    
    for prefix, codes in sorted_prefixes:
        print(f"      {prefix}xx: {len(codes)} KBLI")
        # Mostra alcuni esempi
        sample = sorted(codes)[:5]
        sample_titles = [bps_kbli.get(c, {}).get("judul", "N/A")[:50] for c in sample]
        print(f"         Esempi: {', '.join(sample)}")
        for code, title in zip(sample, sample_titles):
            print(f"            {code}: {title}...")
    
    print()
    
    # Analisi per categoria (basata su prefisso)
    print("2️⃣  CATEGORIZZAZIONE PER SETTORE:")
    
    sector_mapping = {
        "01": "Pertanian, Kehutanan, Perikanan",
        "02": "Pertambangan dan Penggalian",
        "03": "Industri Pengolahan",
        "05": "Pengadaan Listrik, Gas, Uap/Air Panas",
        "06": "Pengadaan Air",
        "07": "Konstruksi",
        "08": "Perdagangan",
        "09": "Transportasi dan Pergudangan",
        "10": "Penyediaan Akomodasi dan Makan Minum",
        "11": "Informasi dan Komunikasi",
        "13": "Jasa Keuangan",
        "14": "Real Estate",
        "15": "Jasa Profesional",
        "16": "Jasa Pendidikan",
        "17": "Jasa Kesehatan",
        "18": "Kesenian, Hiburan, Rekreasi",
        "19": "Jasa Lainnya",
        "20": "Industri Pengolahan",
        "46": "Perdagangan Besar",
        "47": "Perdagangan Eceran",
        "52": "Penyimpanan dan Pergudangan",
        "64": "Jasa Keuangan",
        "66": "Jasa Keuangan",
        "85": "Jasa Pendidikan",
        "84": "Administrasi Pemerintahan"
    }
    
    sector_counts = defaultdict(int)
    sector_codes = defaultdict(list)
    
    for code in missing_codes:
        prefix = code[:2]
        sector = sector_mapping.get(prefix, "Lainnya")
        sector_counts[sector] += 1
        sector_codes[sector].append(code)
    
    print("\n   Distribuzione per settore:")
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"      {sector}: {count} KBLI")
    
    print()
    
    # Identificazione potenziali fonti
    print("3️⃣  POTENZIALI FONTI PER KBLI MANCANTI:")
    print()
    print("   📄 Lampiran II, III, IV di PP 28/2025:")
    print("      - Potrebbero contenere KBLI con permessi di supporto (PB UMKU)")
    print("      - Non tutti i KBLI hanno permessi di supporto")
    print()
    print("   📄 Sezioni PP 28/2025:")
    print("      - Alcuni KBLI potrebbero essere menzionati nel testo principale")
    print("      - Non tutti i KBLI sono regolamentati in PP 28/2025")
    print()
    print("   📄 Altri documenti:")
    print("      - Perpres 10/2021 (PMA)")
    print("      - Peraturan lainnya")
    print()
    
    # Raccomandazioni
    print("4️⃣  RACCOMANDAZIONI:")
    print()
    
    # KBLI che potrebbero essere in altri Lampiran
    high_priority_prefixes = ["01", "10", "85", "66"]  # Settori comuni
    high_priority_codes = [c for c in missing_codes if c[:2] in high_priority_prefixes]
    
    print(f"   🔴 Priorità ALTA ({len(high_priority_codes)} KBLI):")
    print(f"      Settori comuni (01xx, 10xx, 85xx, 66xx)")
    print(f"      Verificare in altri Lampiran o sezioni PP 28/2025")
    print()
    
    # KBLI che probabilmente non sono regolamentati
    low_priority_codes = [c for c in missing_codes if c[:2] not in high_priority_prefixes]
    
    print(f"   🟡 Priorità MEDIA ({len(low_priority_codes)} KBLI):")
    print(f"      Altri settori - potrebbero non essere regolamentati in PP 28/2025")
    print(f"      Usare solo dati BPS + template/defaults")
    print()
    
    # Output report
    report = {
        "analysis_date": datetime.now().isoformat(),
        "total_missing": missing_count,
        "missing_codes": sorted(missing_codes),
        "prefix_distribution": {prefix: len(codes) for prefix, codes in prefix_groups.items()},
        "sector_distribution": dict(sector_counts),
        "high_priority_codes": sorted(high_priority_codes),
        "low_priority_codes": sorted(low_priority_codes),
        "recommendations": {
            "high_priority": {
                "count": len(high_priority_codes),
                "action": "Verificare in altri Lampiran o sezioni PP 28/2025",
                "prefixes": high_priority_prefixes
            },
            "low_priority": {
                "count": len(low_priority_codes),
                "action": "Usare solo dati BPS + template/defaults",
                "note": "Potrebbero non essere regolamentati in PP 28/2025"
            }
        }
    }
    
    report_file = DATA_DIR / "kbli_missing_lampiran_identification.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Report salvato: {report_file.name}")
    print()
    
    print("=" * 70)
    print("📊 RIEPILOGO")
    print("=" * 70)
    print(f"   Totale KBLI mancanti: {missing_count}")
    print(f"   Priorità ALTA: {len(high_priority_codes)}")
    print(f"   Priorità MEDIA: {len(low_priority_codes)}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    identify_missing_sources()
