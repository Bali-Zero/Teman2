#!/usr/bin/env python3
"""Merge master list BPS con dati Lampiran I (arricchimento intelligente)."""

import json
from pathlib import Path
from typing import Dict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def merge_master_with_lampiran():
    """Merge master list BPS con dati Lampiran I."""
    print("=" * 70)
    print("MERGE MASTER LIST BPS + DATI LAMPIRAN I")
    print("=" * 70)
    print()
    
    # Carica master list BPS
    bps_file = DATA_DIR / "bps_master_list_complete.json"
    if not bps_file.exists():
        print(f"❌ File BPS non trovato: {bps_file}")
        return
    
    with open(bps_file) as f:
        bps_data = json.load(f)
    
    bps_kbli = bps_data.get("kbli_data", {})
    print(f"📊 Master list BPS: {len(bps_kbli)} KBLI")
    
    # Carica dati Lampiran I
    lampiran_files = sorted(DATA_DIR.glob("kbli_complete_final_*.json"), 
                           key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not lampiran_files:
        print("⚠️  Nessun file Lampiran I trovato")
        lampiran_kbli = {}
    else:
        with open(lampiran_files[0]) as f:
            lampiran_data = json.load(f)
        lampiran_kbli = lampiran_data.get("kbli_data", {})
        print(f"📊 Dati Lampiran I: {len(lampiran_kbli)} KBLI")
    
    # Merge intelligente
    merged_kbli = {}
    
    for code, bps_entry in bps_kbli.items():
        # Inizia con dati BPS (base)
        merged_entry = {
            "kode": code,
            "judul": bps_entry.get("judul", ""),
            "source": "BPS_7_2025",
            "data_quality": "minimal"  # Solo dati base
        }
        
        # Arricchisci con dati Lampiran I se disponibili
        if code in lampiran_kbli:
            lampiran_entry = lampiran_kbli[code]
            
            # Merge campi Lampiran I
            merged_entry.update({
                "judul": lampiran_entry.get("judul", merged_entry["judul"]),
                "sektor": lampiran_entry.get("sektor"),
                "tingkat_risiko": lampiran_entry.get("tingkat_risiko"),
                "skala_usaha": lampiran_entry.get("skala_usaha"),
                "ruang_lingkup": lampiran_entry.get("ruang_lingkup"),
                "pma_allowed": lampiran_entry.get("pma_allowed"),
                "pma_max_percentage": lampiran_entry.get("pma_max_percentage"),
                "pb_umku": lampiran_entry.get("pb_umku", []),
                "source": "BPS_7_2025 + PP_28_2025_Lampiran_I",
                "data_quality": "complete"
            })
        
        merged_kbli[code] = merged_entry
    
    # Statistiche
    with_complete_data = sum(1 for e in merged_kbli.values() if e.get("data_quality") == "complete")
    with_minimal_data = len(merged_kbli) - with_complete_data
    
    print()
    print(f"✅ Merge completato:")
    print(f"   Totale KBLI: {len(merged_kbli)}")
    print(f"   Con dati completi: {with_complete_data} ({with_complete_data/len(merged_kbli)*100:.1f}%)")
    print(f"   Solo dati base: {with_minimal_data} ({with_minimal_data/len(merged_kbli)*100:.1f}%)")
    
    # Salva risultato
    output_data = {
        "metadata": {
            "merge_date": datetime.now().isoformat(),
            "total_kbli": len(merged_kbli),
            "with_complete_data": with_complete_data,
            "with_minimal_data": with_minimal_data,
            "sources": ["BPS_7_2025", "PP_28_2025_Lampiran_I"]
        },
        "kbli_data": merged_kbli
    }
    
    output_file = DATA_DIR / "kbli_enriched_master_list.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"📁 File salvato: {output_file.name}")
    print("=" * 70)


if __name__ == "__main__":
    merge_master_with_lampiran()
