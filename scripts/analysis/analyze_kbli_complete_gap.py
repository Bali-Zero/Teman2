#!/usr/bin/env python3
"""
Analizza il gap completo tra:
- Master list BPS 7/2025 (tutti i KBLI ufficiali)
- KBLI estratti da Lampiran I PP 28/2025 (832)
- KBLI presenti in Qdrant (1,948)

Identifica quanti e quali KBLI mancano da ciascuna fonte.
"""

import json
import os
import sys
from pathlib import Path
from typing import Set, Dict, List, Any
from collections import Counter
from datetime import datetime

import requests
from dotenv import load_dotenv

# Add backend path
backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
sys.path.insert(0, backend_path)
load_dotenv(os.path.join(backend_path, ".env"))

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "kbli_unified"

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"


def qdrant_request(method: str, endpoint: str, json_data: dict = None) -> dict:
    """Make request to Qdrant REST API."""
    url = f"{QDRANT_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY
    
    if method == "GET":
        r = requests.get(url, headers=headers)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=json_data)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    r.raise_for_status()
    return r.json()


def get_all_kbli_codes_from_qdrant() -> Set[str]:
    """Estrae tutti i codici KBLI dalla collection Qdrant."""
    print("📊 Estrazione codici KBLI da Qdrant...")
    
    kbli_codes = set()
    scroll_id = None
    batch_count = 0
    
    while True:
        payload = {
            "limit": 1000,
            "with_payload": True,
            "with_vectors": False
        }
        
        if scroll_id:
            payload["offset"] = scroll_id
        
        result = qdrant_request(
            "POST",
            f"/collections/{COLLECTION_NAME}/points/scroll",
            payload
        )
        
        points = result.get("result", {}).get("points", [])
        if not points:
            break
        
        for point in points:
            payload_data = point.get("payload", {})
            metadata = payload_data.get("metadata", {})
            kode = metadata.get("kode", "")
            
            if kode and kode.isdigit() and len(kode) == 5:
                kbli_codes.add(kode)
        
        batch_count += 1
        print(f"   Batch {batch_count}: {len(points)} punti, {len(kbli_codes)} KBLI unici")
        
        # Check if there are more points
        next_offset = result.get("result", {}).get("next_page_offset")
        if not next_offset:
            break
        scroll_id = next_offset
    
    return kbli_codes


def load_bps_master_list() -> Dict[str, Dict]:
    """Carica master list BPS."""
    bps_file = DATA_DIR / "bps_master_list_complete.json"
    
    if not bps_file.exists():
        print(f"❌ File BPS master list non trovato: {bps_file}")
        return {}
    
    print(f"📁 Caricamento BPS master list: {bps_file.name}")
    with open(bps_file) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    print(f"   ✅ Totale KBLI in BPS: {len(kbli_data)}")
    return kbli_data


def load_lampiran_extracted() -> Dict[str, Dict]:
    """Carica KBLI estratti da Lampiran I."""
    final_file = sorted(DATA_DIR.glob("kbli_complete_final_*.json"), 
                       key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not final_file:
        print("⚠️  Nessun file completo finale trovato!")
        return {}
    
    print(f"📁 Caricamento dati Lampiran I: {final_file[0].name}")
    with open(final_file[0]) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    print(f"   ✅ Totale KBLI estratti da Lampiran I: {len(kbli_data)}")
    return kbli_data


def analyze_gap():
    """Analizza il gap completo tra tutte le fonti."""
    print("=" * 70)
    print("🔍 ANALISI GAP COMPLETA KBLI")
    print("=" * 70)
    print()
    
    report: Dict[str, Any] = {
        "analysis_date": datetime.now().isoformat(),
        "sources": {
            "bps_master_list": {},
            "lampiran_extracted": {},
            "qdrant": {}
        },
        "gap_analysis": {},
        "recommendations": []
    }
    
    # 1. Carica tutte le fonti
    print("1️⃣  CARICAMENTO FONTI:")
    bps_kbli = load_bps_master_list()
    lampiran_kbli = load_lampiran_extracted()
    qdrant_codes = get_all_kbli_codes_from_qdrant()
    
    bps_codes = set(bps_kbli.keys())
    lampiran_codes = set(lampiran_kbli.keys())
    
    report["sources"]["bps_master_list"] = {
        "total": len(bps_codes),
        "codes": sorted(list(bps_codes))
    }
    report["sources"]["lampiran_extracted"] = {
        "total": len(lampiran_codes),
        "codes": sorted(list(lampiran_codes))
    }
    report["sources"]["qdrant"] = {
        "total": len(qdrant_codes),
        "codes": sorted(list(qdrant_codes))
    }
    
    print()
    
    # 2. Analisi gap
    print("2️⃣  ANALISI GAP:")
    print(f"   BPS Master List: {len(bps_codes)} KBLI")
    print(f"   Lampiran I estratti: {len(lampiran_codes)} KBLI")
    print(f"   Qdrant: {len(qdrant_codes)} KBLI")
    print()
    
    # KBLI in BPS ma non estratti da Lampiran I
    missing_from_lampiran = bps_codes - lampiran_codes
    print(f"   ⚠️  KBLI in BPS ma NON estratti da Lampiran I: {len(missing_from_lampiran)}")
    print(f"      Coverage Lampiran I: {len(lampiran_codes)/len(bps_codes)*100:.1f}%")
    
    # KBLI estratti ma non in BPS (errori?)
    not_in_bps = lampiran_codes - bps_codes
    if not_in_bps:
        print(f"   ❌ KBLI estratti ma NON in BPS (errori?): {len(not_in_bps)}")
        print(f"      Esempi: {sorted(list(not_in_bps))[:10]}")
    else:
        print(f"   ✅ Tutti i KBLI estratti sono presenti in BPS")
    
    # KBLI in Qdrant ma non in BPS (obsoleti?)
    obsolete_in_qdrant = qdrant_codes - bps_codes
    if obsolete_in_qdrant:
        print(f"   ⚠️  KBLI in Qdrant ma NON in BPS (obsoleti?): {len(obsolete_in_qdrant)}")
        print(f"      Esempi: {sorted(list(obsolete_in_qdrant))[:10]}")
    else:
        print(f"   ✅ Tutti i KBLI in Qdrant sono presenti in BPS")
    
    # KBLI in BPS ma non in Qdrant
    missing_from_qdrant = bps_codes - qdrant_codes
    print(f"   ⚠️  KBLI in BPS ma NON in Qdrant: {len(missing_from_qdrant)}")
    print(f"      Coverage Qdrant: {len(qdrant_codes & bps_codes)/len(bps_codes)*100:.1f}%")
    
    # KBLI con dati completi (in Lampiran I)
    with_complete_data = lampiran_codes & bps_codes
    print(f"   ✅ KBLI con dati completi (Lampiran I): {len(with_complete_data)}")
    print(f"      Percentuale: {len(with_complete_data)/len(bps_codes)*100:.1f}%")
    
    print()
    
    # 3. Statistiche dettagliate
    report["gap_analysis"] = {
        "total_bps": len(bps_codes),
        "extracted_from_lampiran": len(lampiran_codes),
        "in_qdrant": len(qdrant_codes),
        "missing_from_lampiran": sorted(list(missing_from_lampiran)),
        "missing_from_lampiran_count": len(missing_from_lampiran),
        "not_in_bps": sorted(list(not_in_bps)),
        "obsolete_in_qdrant": sorted(list(obsolete_in_qdrant)),
        "missing_from_qdrant": sorted(list(missing_from_qdrant)),
        "with_complete_data": sorted(list(with_complete_data)),
        "coverage_lampiran_percentage": len(lampiran_codes)/len(bps_codes)*100 if bps_codes else 0,
        "coverage_qdrant_percentage": len(qdrant_codes & bps_codes)/len(bps_codes)*100 if bps_codes else 0
    }
    
    # 4. Distribuzione per prefisso
    print("3️⃣  DISTRIBUZIONE PER PREFISSO (KBLI mancanti da Lampiran I):")
    missing_prefixes = Counter(code[:2] for code in missing_from_lampiran)
    print("\n   Top 10 prefissi con più KBLI mancanti:")
    for prefix, count in missing_prefixes.most_common(10):
        print(f"      {prefix}xx: {count} KBLI mancanti")
    print()
    
    report["gap_analysis"]["missing_prefix_distribution"] = dict(missing_prefixes)
    
    # 5. Raccomandazioni
    print("4️⃣  RACCOMANDAZIONI:")
    recommendations = []
    
    if len(missing_from_lampiran) > 0:
        recommendations.append({
            "priority": "high",
            "action": "Verificare se KBLI mancanti sono in altri Lampiran (II, III, IV) o sezioni PP 28/2025",
            "count": len(missing_from_lampiran)
        })
        print(f"   🔴 Priorità ALTA: {len(missing_from_lampiran)} KBLI mancano da Lampiran I")
        print(f"      Verificare se sono in altri Lampiran o sezioni PP 28/2025")
    
    if len(missing_from_qdrant) > 0:
        recommendations.append({
            "priority": "medium",
            "action": f"Aggiungere {len(missing_from_qdrant)} KBLI mancanti a Qdrant",
            "count": len(missing_from_qdrant)
        })
        print(f"   🟡 Priorità MEDIA: {len(missing_from_qdrant)} KBLI mancano da Qdrant")
    
    if obsolete_in_qdrant:
        recommendations.append({
            "priority": "low",
            "action": f"Verificare e rimuovere {len(obsolete_in_qdrant)} KBLI obsoleti da Qdrant",
            "count": len(obsolete_in_qdrant)
        })
        print(f"   🟢 Priorità BASSA: {len(obsolete_in_qdrant)} KBLI obsoleti in Qdrant da verificare")
    
    report["recommendations"] = recommendations
    print()
    
    # 6. Salva report
    report_file = DATA_DIR / "kbli_complete_gap_analysis.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Report completo salvato: {report_file.name}")
    print()
    
    print("=" * 70)
    print("📊 RIEPILOGO FINALE")
    print("=" * 70)
    print(f"   Master List BPS: {len(bps_codes)} KBLI")
    print(f"   Estratti Lampiran I: {len(lampiran_codes)} ({len(lampiran_codes)/len(bps_codes)*100:.1f}%)")
    print(f"   In Qdrant: {len(qdrant_codes)} ({len(qdrant_codes & bps_codes)/len(bps_codes)*100:.1f}% dei BPS)")
    print(f"   Mancanti da Lampiran I: {len(missing_from_lampiran)}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    analyze_gap()
