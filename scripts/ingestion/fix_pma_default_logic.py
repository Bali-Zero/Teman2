#!/usr/bin/env python3
"""
Applica logica PMA di default secondo Perpres 10/2021:
- Tutti i KBLI sono PMA=100% di default (Positive Investment List)
- Solo quelli esplicitamente limitati hanno restrizioni
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Set

PROJECT_ROOT = Path(__file__).parent.parent.parent
BPS_KBLI_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "bps_kbli.json"
PMA_DATA_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "pma_data_from_reference_v2.json"
OUTPUT_FILE = PROJECT_ROOT / "reports" / "kbli_extraction" / "pma_complete_with_defaults.json"

# KBLI esplicitamente chiusi o limitati
CLOSED_KBLI: Set[str] = {
    "11010", "11020", "11031",  # Alcolici (Perpres 49/2021)
    "08930",  # Estrazione corallo
    "20200",  # Armi chimiche
    "20130",  # Sostanze che danneggiano ozono
}

# Categorie con restrizioni (da mappare a codici specifici)
RESTRICTED_CATEGORIES = {
    "47xxx": (False, "0%", "Retail trade - CLOSED"),  # Eccetto 47919 (e-commerce)
    "92xxx": (False, "0%", "Gambling - CLOSED"),
    "03xxx": (None, None, "Fishing - alcune restrizioni"),  # Da verificare per codice specifico
}

# KBLI con percentuali specifiche
SPECIFIC_PMA_LIMITS: Dict[str, tuple[bool, str]] = {
    "47919": (True, "100%"),  # E-commerce retail (eccezione)
    "63122": (True, "100%"),  # E-commerce platforms
    "62020": (True, "100%"),  # IT Consulting (con investimento minimo)
    "86101": (True, "67%"),  # Hospitals
    "05100": (True, "49%"),  # Coal mining
    # Aggiungere altri se trovati nel documento
}


def is_kbli_in_category(code: str, category_pattern: str) -> bool:
    """Verifica se un KBLI appartiene a una categoria (es: 47xxx)."""
    if category_pattern.endswith("xxx"):
        prefix = category_pattern[:2]
        return code.startswith(prefix)
    return False


def apply_pma_defaults() -> Dict[str, Dict]:
    """
    Applica logica PMA di default:
    - Tutti i KBLI sono PMA=100% di default
    - Solo quelli esplicitamente limitati hanno restrizioni
    """
    print("=" * 70)
    print("APPLICAZIONE LOGICA PMA DI DEFAULT")
    print("=" * 70)
    
    # Load BPS data
    if not BPS_KBLI_FILE.exists():
        print(f"❌ File BPS non trovato: {BPS_KBLI_FILE}")
        return {}
    
    with open(BPS_KBLI_FILE) as f:
        bps_data = json.load(f)
    
    print(f"📋 KBLI totali in BPS: {len(bps_data)}")
    
    # Load PMA espliciti dal documento
    pma_explicit = {}
    if PMA_DATA_FILE.exists():
        with open(PMA_DATA_FILE) as f:
            pma_json = json.load(f)
            pma_explicit = pma_json.get("pma_data", {})
    
    print(f"📋 KBLI con PMA esplicito: {len(pma_explicit)}")
    
    # Applica logica
    pma_complete = {}
    
    for code, kbli_info in bps_data.items():
        pma_info = {
            "kode": code,
            "pma_allowed": True,  # Default: aperto
            "pma_max_percentage": "100%",  # Default: 100%
            "pma_notes": "Default: Positive Investment List (Perpres 10/2021)",
            "source": "default_positive_list"
        }
        
        # 1. Verifica se è esplicitamente chiuso
        if code in CLOSED_KBLI:
            pma_info["pma_allowed"] = False
            pma_info["pma_max_percentage"] = "0%"
            pma_info["pma_notes"] = "CLOSED - Explicitly restricted"
            pma_info["source"] = "closed_list"
        
        # 2. Verifica se ha limite specifico
        elif code in SPECIFIC_PMA_LIMITS:
            allowed, percentage = SPECIFIC_PMA_LIMITS[code]
            pma_info["pma_allowed"] = allowed
            pma_info["pma_max_percentage"] = percentage
            pma_info["pma_notes"] = f"Specific limit: {percentage}"
            pma_info["source"] = "specific_limit"
        
        # 3. Verifica categorie con restrizioni
        elif code.startswith("47") and code != "47919":
            # Retail trade chiuso (eccetto e-commerce)
            pma_info["pma_allowed"] = False
            pma_info["pma_max_percentage"] = "0%"
            pma_info["pma_notes"] = "Retail trade - CLOSED (except e-commerce)"
            pma_info["source"] = "category_restriction"
        
        elif code.startswith("92"):
            # Gambling chiuso
            pma_info["pma_allowed"] = False
            pma_info["pma_max_percentage"] = "0%"
            pma_info["pma_notes"] = "Gambling - CLOSED"
            pma_info["source"] = "category_restriction"
        
        # 4. Se abbiamo dati espliciti dal documento, usali (hanno priorità)
        elif code in pma_explicit:
            explicit = pma_explicit[code]
            pma_info["pma_allowed"] = explicit.get("pma_allowed")
            pma_info["pma_max_percentage"] = explicit.get("pma_max_percentage", "100%")
            pma_info["pma_notes"] = explicit.get("pma_notes", "")
            pma_info["source"] = explicit.get("source", "explicit_document")
        
        pma_complete[code] = pma_info
    
    # Statistiche
    allowed = sum(1 for v in pma_complete.values() if v.get("pma_allowed") is True)
    closed = sum(1 for v in pma_complete.values() if v.get("pma_allowed") is False)
    restricted = sum(1 for v in pma_complete.values() if v.get("pma_max_percentage") != "100%")
    
    print(f"\n📊 Statistiche:")
    print(f"   PMA permesso (100%): {allowed} ({allowed*100/len(pma_complete):.1f}%)")
    print(f"   PMA chiuso (0%): {closed} ({closed*100/len(pma_complete):.1f}%)")
    print(f"   Con restrizioni (<100%): {restricted} ({restricted*100/len(pma_complete):.1f}%)")
    
    # Salva
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "source": "Positive Investment List (Perpres 10/2021) + explicit restrictions",
            "total_kbli": len(pma_complete),
            "logic": "All KBLI are PMA=100% by default unless explicitly restricted",
            "pma_data": pma_complete
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Salvato in: {OUTPUT_FILE}")
    
    return pma_complete


if __name__ == "__main__":
    apply_pma_defaults()
