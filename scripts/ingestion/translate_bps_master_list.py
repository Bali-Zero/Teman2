#!/usr/bin/env python3
"""Traduce tutti i judul da BPS master list."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"

sys.path.insert(0, str(PROJECT_ROOT))
from scripts.ingestion.services.translation_service import get_translation_service


def translate_bps_master_list():
    """Traduce tutti i judul da BPS master list."""
    print("=" * 70)
    print("TRADUZIONE BPS MASTER LIST")
    print("=" * 70)
    print()
    
    # Carica master list
    bps_file = DATA_DIR / "bps_master_list_complete.json"
    if not bps_file.exists():
        print(f"❌ File non trovato: {bps_file}")
        return
    
    with open(bps_file) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    print(f"📊 KBLI da tradurre: {len(kbli_data)}")
    print()
    
    # Servizio traduzione
    service = get_translation_service()
    
    # Traduci tutti i judul
    translated_data = {}
    texts_to_translate = []
    
    for code, entry in kbli_data.items():
        judul = entry.get("judul", "")
        if judul:
            texts_to_translate.append(judul)
    
    print(f"🔄 Traduzione {len(texts_to_translate)} judul...")
    translations = service.translate_batch(texts_to_translate, save_interval=50)
    
    # Applica traduzioni
    for code, entry in kbli_data.items():
        judul = entry.get("judul", "")
        judul_en = translations.get(judul, judul)
        
        translated_entry = entry.copy()
        translated_entry["judul_en"] = judul_en
        translated_data[code] = translated_entry
    
    # Salva risultato
    output_data = {
        "metadata": data.get("metadata", {}),
        "kbli_data": translated_data
    }
    
    output_file = DATA_DIR / "bps_master_list_translated.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"✅ Traduzione completata")
    print(f"📁 File salvato: {output_file.name}")
    print("=" * 70)


if __name__ == "__main__":
    translate_bps_master_list()
