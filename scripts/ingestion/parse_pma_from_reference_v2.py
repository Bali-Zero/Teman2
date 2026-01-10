#!/usr/bin/env python3
"""
Estrae informazioni PMA dal documento consolidato - Versione migliorata
Gestisce tabelle markdown, sezioni testuali e esempi specifici
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REFERENCE_FILE = Path("/Users/antonellosiano/Desktop/KB/nuzantara_laws/apps/scraper/data/raw_laws_local/Company&Licenses/kbli/KBLI_SECTORS_FOREIGN_OWNERSHIP_COMPLETE_REFERENCE_2025.md")
OUTPUT_FILE = Path("reports/kbli_extraction/pma_data_from_reference_v2.json")


def parse_percentage(text: str) -> Optional[Tuple[bool, str]]:
    """
    Estrae percentuale PMA da testo.
    Restituisce (pma_allowed, percentage) o None.
    """
    text_lower = text.lower()
    
    # Cerca percentuale esplicita PRIMA di controllare "closed"
    # Questo evita che "100%" venga matchato come "0%" (perché contiene "0%")
    percentage_match = re.search(r'(\d+)%', text)
    if percentage_match:
        percentage = int(percentage_match.group(1))
        if percentage == 0:
            return (False, "0%")
        return (True, f"{percentage}%")
    
    # Chiuso (solo se non abbiamo trovato percentuale)
    if "closed" in text_lower or "tidak diizinkan" in text_lower:
        return (False, "0%")
    
    # 100% permesso (fallback)
    if "100%" in text or "open" in text_lower or "allowed" in text_lower:
        return (True, "100%")
    
    # Varia o sconosciuto
    if "varies" in text_lower or "varia" in text_lower:
        return None
    
    return None


def parse_pma_from_reference() -> Dict[str, Dict]:
    """
    Estrae informazioni PMA dal documento di riferimento.
    """
    if not REFERENCE_FILE.exists():
        print(f"❌ File non trovato: {REFERENCE_FILE}")
        return {}
    
    print(f"📄 Leggendo: {REFERENCE_FILE.name}")
    
    with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    pma_data = {}
    
    # 1. Parse tabelle markdown con KBLI codes
    # Cerca righe di tabella che contengono KBLI codes e Foreign Ownership
    lines = content.split('\n')
    in_table = False
    header_found = False
    ownership_col_idx = None
    
    for i, line in enumerate(lines):
        # Rileva intestazione tabella con "Foreign Ownership"
        if '|' in line and 'Foreign Ownership' in line:
            in_table = True
            header_found = True
            # Trova indice colonna Foreign Ownership
            headers = [h.strip().lower() for h in line.split('|')[1:-1]]
            try:
                ownership_col_idx = headers.index('foreign ownership')
            except ValueError:
                ownership_col_idx = None
            continue
        
        # Se siamo in una tabella e abbiamo trovato l'intestazione
        if in_table and header_found and ownership_col_idx is not None:
            if '|' in line and '---' not in line:
                # È una riga dati
                columns = [c.strip() for c in line.split('|')[1:-1]]
                
                if len(columns) > ownership_col_idx:
                    # Cerca KBLI code nella prima colonna
                    first_col = columns[0]
                    code_match = re.search(r'\*\*(\d{5})\*\*', first_col)
                    
                    if code_match:
                        code = code_match.group(1)
                        ownership = columns[ownership_col_idx].strip()
                        
                        pma_info = parse_percentage(ownership)
                        if pma_info:
                            pma_allowed, pma_max = pma_info
                            pma_data[code] = {
                                "kode": code,
                                "pma_allowed": pma_allowed,
                                "pma_max_percentage": pma_max,
                                "pma_notes": ownership,
                                "source": "table"
                            }
            elif line.strip() == '' or not line.strip().startswith('|'):
                # Fine tabella
                in_table = False
                header_found = False
                ownership_col_idx = None
    
    # 2. Parse sezioni "**Foreign Ownership**: ..."
    # Cerca pattern come "**Foreign Ownership**: 100%" seguito da lista di KBLI
    ownership_section_pattern = r'\*\*Foreign Ownership\*\*[:\s]*(.*?)(?=\*\*|##|$)'
    sections = re.finditer(ownership_section_pattern, content, re.DOTALL | re.IGNORECASE)
    
    for section_match in sections:
        section_text = section_match.group(1)
        
        # Cerca KBLI codes nella sezione
        kbli_codes_in_section = re.finditer(r'(\d{5})[:\s]*[^\n]*(?:CLOSED|closed|100%|\d+%)', section_text)
        
        for code_match in kbli_codes_in_section:
            code = code_match.group(1)
            line = code_match.group(0)
            
            if code not in pma_data:
                pma_info = parse_percentage(line)
                if pma_info:
                    pma_allowed, pma_max = pma_info
                    pma_data[code] = {
                        "kode": code,
                        "pma_allowed": pma_allowed,
                        "pma_max_percentage": pma_max,
                        "pma_notes": line[:200],
                        "source": "foreign_ownership_section"
                    }
        
        # Cerca anche pattern come "- **Alcohol manufacturing** (11010, 11020, 11031): **CLOSED**"
        list_pattern = r'[-•]\s*\*\*[^\*]+\*\*\s*\(([^)]+)\)[:\s]*\*\*([^\*]+)\*\*'
        list_matches = re.finditer(list_pattern, section_text)
        
        for list_match in list_matches:
            codes_str = list_match.group(1)  # "11010, 11020, 11031"
            status = list_match.group(2).strip()  # "CLOSED"
            
            codes = [c.strip() for c in codes_str.split(',')]
            pma_info = parse_percentage(status)
            
            if pma_info:
                pma_allowed, pma_max = pma_info
                for code in codes:
                    if code.isdigit() and len(code) == 5:
                        if code not in pma_data:
                            pma_data[code] = {
                                "kode": code,
                                "pma_allowed": pma_allowed,
                                "pma_max_percentage": pma_max,
                                "pma_notes": f"{status} - {list_match.group(0)[:100]}",
                                "source": "list_item"
                            }
    
    # 3. Parse sezioni specifiche KBLI (es: "### KBLI 55111:")
    kbli_section_pattern = r'###\s*KBLI\s*(\d{5})[:\s]*.*?\*\*Foreign Ownership\*\*[:\s]*([^\n]+)'
    kbli_sections = re.finditer(kbli_section_pattern, content, re.DOTALL | re.IGNORECASE)
    
    for kbli_match in kbli_sections:
        code = kbli_match.group(1)
        ownership = kbli_match.group(2).strip()
        
        if code not in pma_data:
            pma_info = parse_percentage(ownership)
            if pma_info:
                pma_allowed, pma_max = pma_info
                pma_data[code] = {
                    "kode": code,
                    "pma_allowed": pma_allowed,
                    "pma_max_percentage": pma_max,
                    "pma_notes": ownership,
                    "source": "kbli_section"
                }
    
    # 4. Settori chiusi espliciti (dalla sezione "6 Sectors Fully CLOSED")
    closed_sectors = [
        ("11010", "Alcoholic Beverage Industry (spirits) - CLOSED (Perpres 49/2021)"),
        ("11020", "Wine Industry - CLOSED (Perpres 49/2021)"),
        ("11031", "Malt Beverage Industry (beer) - CLOSED (Perpres 49/2021)"),
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
                "source": "closed_sectors_list"
            }
    
    # 5. Categorie con regole generali (es: "47xxx": **CLOSED**)
    # Mappiamo categorie a codici specifici se possibile
    category_rules = {
        "47xxx": (False, "0%", "Retail trade - CLOSED to foreigners"),
        "46xxx": (True, "100%", "Wholesale trade - 100% with IDR 10B minimum"),
        "41xxx-43xxx": (None, None, "Construction - No percentage limit but partnership required"),
        "61xxx": (True, "67%", "Telecommunications - 67% maximum"),
        "86101": (True, "67%", "Hospitals - 67% maximum"),
        "05100": (True, "49%", "Coal mining - 49% maximum"),
        "06xxx": (True, "95%", "Oil & Gas - 95% maximum via PSC"),
    }
    
    # Per ora non mappiamo categorie a codici specifici (richiederebbe lista completa KBLI)
    # Ma aggiungiamo le regole come riferimento
    
    print(f"✅ Estratti {len(pma_data)} KBLI con informazioni PMA")
    
    return pma_data


def main():
    """Main function"""
    print("=" * 70)
    print("ESTRAZIONE INFORMAZIONI PMA DAL DOCUMENTO DI RIFERIMENTO V2")
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
        for i, (code, info) in enumerate(list(pma_data.items())[:10], 1):
            print(f"   {i}. {code}: PMA={info.get('pma_allowed')}, Max={info.get('pma_max_percentage', 'N/A')}, Source={info.get('source')}")


if __name__ == "__main__":
    main()
