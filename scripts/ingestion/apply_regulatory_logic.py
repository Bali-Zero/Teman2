#!/usr/bin/env python3
"""Applica logica regolamentaria PP 28/2025 (PMA defaults, risk level, etc.)."""

import json
import sys
from pathlib import Path
from typing import Dict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"

sys.path.insert(0, str(PROJECT_ROOT))
from scripts.ingestion.templates.kbli_templates import SKALA_USAHA_DEFAULTS


def apply_regulatory_logic():
    """Applica logica regolamentaria."""
    print("=" * 70)
    print("APPLICAZIONE LOGICA REGOLAMENTARIA")
    print("=" * 70)
    print()
    
    # Carica dati arricchiti
    enriched_file = DATA_DIR / "kbli_enriched_master_list.json"
    if not enriched_file.exists():
        print(f"❌ File non trovato: {enriched_file}")
        return
    
    with open(enriched_file) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    print(f"📊 KBLI da processare: {len(kbli_data)}")
    
    # Carica dati PMA
    pma_file = DATA_DIR / "pma_complete_with_defaults.json"
    pma_data = {}
    if pma_file.exists():
        with open(pma_file) as f:
            pma_json = json.load(f)
            pma_data = pma_json.get("pma_data", {})
        print(f"📊 Dati PMA caricati: {len(pma_data)} KBLI")
    else:
        print("⚠️  File PMA non trovato, applicando defaults")
    
    # Applica logica
    updated_count = 0
    
    for code, entry in kbli_data.items():
        updated = False
        
        # 1. Applica PMA defaults se mancante
        if "pma_allowed" not in entry or entry.get("pma_allowed") is None:
            if code in pma_data:
                pma_info = pma_data[code]
                entry["pma_allowed"] = pma_info.get("pma_allowed", True)
                entry["pma_max_percentage"] = pma_info.get("pma_max_percentage", "100%")
            else:
                # Default: 100% PMA (Positive Investment List)
                entry["pma_allowed"] = True
                entry["pma_max_percentage"] = "100%"
            updated = True
        
        # 2. Applica skala usaha defaults se mancante
        if "skala_usaha" not in entry or not entry.get("skala_usaha"):
            entry["skala_usaha"] = SKALA_USAHA_DEFAULTS["allowed_scales"]
            updated = True
        
        # 3. Applica risk level default se mancante
        if "tingkat_risiko" not in entry or not entry.get("tingkat_risiko"):
            entry["tingkat_risiko"] = "Tidak diatur"
            updated = True
        
        if updated:
            updated_count += 1
    
    print()
    print(f"✅ Logica regolamentaria applicata:")
    print(f"   KBLI aggiornati: {updated_count}/{len(kbli_data)}")
    
    # Salva risultato
    output_data = {
        "metadata": {
            **data.get("metadata", {}),
            "regulatory_logic_applied": datetime.now().isoformat(),
            "updated_count": updated_count
        },
        "kbli_data": kbli_data
    }
    
    output_file = DATA_DIR / "kbli_enriched_master_list.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"📁 File aggiornato: {output_file.name}")
    print("=" * 70)


if __name__ == "__main__":
    apply_regulatory_logic()
