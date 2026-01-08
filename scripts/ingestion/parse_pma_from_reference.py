#!/usr/bin/env python3
"""
Estrae informazioni PMA dal documento consolidato KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

REFERENCE_FILE = Path("/Users/antonellosiano/Desktop/KB/nuzantara_laws/apps/scraper/data/raw_laws_local/Company&Licenses/kbli/KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md")
OUTPUT_FILE = Path("reports/kbli_extraction/pma_data_from_reference.json")


def parse_pma_from_reference() -> Dict[str, Dict]:
    """
    Estrae informazioni PMA dal documento di riferimento.
    Restituisce dict con kode KBLI come chiave.
    """
    if not REFERENCE_FILE.exists():
        print(f"❌ File non trovato: {REFERENCE_FILE}")
        return {}
    
    print(f"📄 Leggendo: {REFERENCE_FILE.name}")
    
    with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    pma_data = {}
    
    # Pattern per trovare KBLI con informazioni PMA
    # Cerca pattern come "**Foreign Ownership**: 100%" o "**CLOSED**" o "95% maximum"
    
    # Sezioni con tabelle di Foreign Ownership
    ownership_sections = re.findall(
        r'\*\*Foreign Ownership\*\*[:\s]*(.*?)(?=\*\*|##|$)',
        content,
        re.DOTALL | re.IGNORECASE
    )
    
    # Cerca KBLI codes con percentuali PMA
    # Pattern: KBLI code seguito da informazioni PMA
    kbli_pattern = r'(\d{5})[:\s]*.*?(?:Foreign Ownership|PMA)[:\s]*([^\n]+)'
    matches = re.finditer(kbli_pattern, content, re.IGNORECASE)
    
    for match in matches:
        code = match.group(1)
        ownership_info = match.group(2).strip()
        
        pma_info = {
            "kode": code,
            "pma_allowed": None,
            "pma_max_percentage": None,
            "pma_notes": ownership_info,
            "source": "KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md"
        }
        
        # Determina se PMA è permesso
        ownership_lower = ownership_info.lower()
        if "closed" in ownership_lower or "0%" in ownership_info:
            pma_info["pma_allowed"] = False
            pma_info["pma_max_percentage"] = "0%"
        elif "100%" in ownership_info:
            pma_info["pma_allowed"] = True
            pma_info["pma_max_percentage"] = "100%"
        elif re.search(r'\d+%', ownership_info):
            percentage_match = re.search(r'(\d+)%', ownership_info)
            if percentage_match:
                percentage = int(percentage_match.group(1))
                pma_info["pma_allowed"] = percentage > 0
                pma_info["pma_max_percentage"] = f"{percentage}%"
        elif "open" in ownership_lower or "allowed" in ownership_lower:
            pma_info["pma_allowed"] = True
        
        pma_data[code] = pma_info
    
    # Cerca anche nelle tabelle
    # Pattern per tabelle con KBLI e Foreign Ownership
    table_pattern = r'\|\s*(\d{5})\s*\|\s*[^\|]+\s*\|\s*([^\|]+)\s*\|\s*[^\|]*\s*\|'
    table_matches = re.finditer(table_pattern, content)
    
    for match in table_matches:
        code = match.group(1)
        ownership = match.group(2).strip()
        
        if code not in pma_data:
            pma_info = {
                "kode": code,
                "pma_allowed": None,
                "pma_max_percentage": None,
                "pma_notes": ownership,
                "source": "KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md"
            }
            
            ownership_lower = ownership.lower()
            if "closed" in ownership_lower or "0%" in ownership:
                pma_info["pma_allowed"] = False
                pma_info["pma_max_percentage"] = "0%"
            elif "100%" in ownership:
                pma_info["pma_allowed"] = True
                pma_info["pma_max_percentage"] = "100%"
            elif re.search(r'\d+%', ownership):
                percentage_match = re.search(r'(\d+)%', ownership)
                if percentage_match:
                    percentage = int(percentage_match.group(1))
                    pma_info["pma_allowed"] = percentage > 0
                    pma_info["pma_max_percentage"] = f"{percentage}%"
            
            pma_data[code] = pma_info
    
    # Cerca settori chiusi (6 settori + 3 alcolici)
    closed_sectors = [
        ("11010", "Alcoholic Beverage Industry (spirits) - CLOSED"),
        ("11020", "Wine Industry - CLOSED"),
        ("11031", "Malt Beverage Industry (beer) - CLOSED"),
        ("08930", "Extraction and utilization of coral - CLOSED"),
        ("20200", "Chemical weapons industry - CLOSED"),
        ("20130", "Ozone-depleting chemical industry - CLOSED"),
    ]
    
    for code, note in closed_sectors:
        if code not in pma_data:
            pma_data[code] = {
                "kode": code,
                "pma_allowed": False,
                "pma_max_percentage": "0%",
                "pma_notes": note,
                "source": "KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md"
            }
    
    # Cerca pattern per categorie (es: "47xxx": **CLOSED**)
    category_pattern = r'(\d{2,3}xxx)[:\s]*\*\*([^\*]+)\*\*'
    category_matches = re.finditer(category_pattern, content, re.IGNORECASE)
    
    for match in category_matches:
        category = match.group(1)  # es: "47xxx"
        status = match.group(2).strip()
        
        if "closed" in status.lower():
            # Questa categoria è chiusa, ma non possiamo mappare a codici specifici
            # senza conoscere tutti i codici della categoria
            pass
    
    print(f"✅ Estratti {len(pma_data)} KBLI con informazioni PMA")
    
    return pma_data


def main():
    """Main function"""
    print("=" * 70)
    print("ESTRAZIONE INFORMAZIONI PMA DAL DOCUMENTO DI RIFERIMENTO")
    print("=" * 70)
    
    pma_data = parse_pma_from_reference()
    
    # Salva risultati
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "source": "KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md",
            "total_kbli": len(pma_data),
            "pma_data": pma_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Salvato in: {OUTPUT_FILE}")
    
    # Statistiche
    allowed = sum(1 for v in pma_data.values() if v.get("pma_allowed") is True)
    closed = sum(1 for v in pma_data.values() if v.get("pma_allowed") is False)
    unknown = sum(1 for v in pma_data.values() if v.get("pma_allowed") is None)
    
    print(f"\n📊 Statistiche:")
    print(f"   PMA permesso: {allowed}")
    print(f"   PMA chiuso: {closed}")
    print(f"   PMA sconosciuto: {unknown}")
    
    # Mostra alcuni esempi
    if pma_data:
        print(f"\n📋 Esempi:")
        for i, (code, info) in enumerate(list(pma_data.items())[:5], 1):
            print(f"   {i}. {code}: PMA={info.get('pma_allowed')}, Max={info.get('pma_max_percentage', 'N/A')}")


if __name__ == "__main__":
    main()
