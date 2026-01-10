#!/usr/bin/env python3
"""Genera algoritmo correlazione KBLI (prefisso, sektor, supply chain)."""

import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def generate_correlations():
    """Genera correlazioni tra KBLI."""
    print("=" * 70)
    print("GENERAZIONE CORRELAZIONI KBLI")
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
    print(f"📊 KBLI totali: {len(kbli_data)}")
    
    correlations = {}
    
    # 1. Correlazione per prefisso (22xx → altri 22xx)
    print("\n1️⃣  Correlazione per prefisso...")
    prefix_groups = defaultdict(list)
    
    for code in kbli_data.keys():
        prefix_2 = code[:2]
        prefix_3 = code[:3]
        prefix_groups[prefix_2].append(code)
        prefix_groups[prefix_3].append(code)
    
    for code in kbli_data.keys():
        prefix_2 = code[:2]
        prefix_3 = code[:3]
        
        # Correlati stesso prefisso 2 cifre (max 5)
        same_prefix_2 = [c for c in prefix_groups[prefix_2] if c != code][:5]
        
        # Correlati stesso prefisso 3 cifre (max 3)
        same_prefix_3 = [c for c in prefix_groups[prefix_3] if c != code][:3]
        
        # Combina e deduplica
        related = list(dict.fromkeys(same_prefix_3 + same_prefix_2))[:5]
        
        correlations[code] = {
            "serupa": related[:3],  # Stesso prefisso 3 cifre
            "sub_kategori": related[3:5] if len(related) > 3 else []  # Stesso prefisso 2 cifre
        }
    
    print(f"   ✅ Correlazioni generate per {len(correlations)} KBLI")
    
    # 2. Correlazione supply chain (produksi → perdagangan)
    print("\n2️⃣  Correlazione supply chain...")
    
    # Mapping settori produzione → perdagangan
    production_prefixes = ["20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32"]
    trading_prefixes = ["46", "47"]
    
    supply_chain_count = 0
    for code in kbli_data.keys():
        prefix_2 = code[:2]
        
        if prefix_2 in production_prefixes:
            # Trova KBLI perdagangan correlati
            trading_related = []
            for trading_code in kbli_data.keys():
                if trading_code[:2] in trading_prefixes:
                    trading_related.append(trading_code)
                    if len(trading_related) >= 2:
                        break
            
            if trading_related:
                if code not in correlations:
                    correlations[code] = {"serupa": [], "sub_kategori": [], "supply_chain": []}
                elif "supply_chain" not in correlations[code]:
                    correlations[code]["supply_chain"] = []
                
                correlations[code]["supply_chain"] = trading_related[:2]
                supply_chain_count += 1
    
    print(f"   ✅ {supply_chain_count} KBLI con correlazioni supply chain")
    
    # Salva risultato
    output = {
        "metadata": {
            "total_kbli": len(kbli_data),
            "correlations_generated": len(correlations)
        },
        "correlations": correlations
    }
    
    output_file = DATA_DIR / "kbli_correlations.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"✅ Correlazioni generate")
    print(f"📁 File salvato: {output_file.name}")
    print("=" * 70)


if __name__ == "__main__":
    generate_correlations()
