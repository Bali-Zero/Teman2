#!/usr/bin/env python3
"""
Confronta la qualità dei dati tra KBLI in Qdrant e KBLI estratti da Lampiran I.
Identifica quali KBLI necessitano aggiornamento.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
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


def get_kbli_from_qdrant(code: str) -> Optional[Dict]:
    """Ottiene un KBLI specifico da Qdrant."""
    try:
        result = qdrant_request(
            "POST",
            f"/collections/{COLLECTION_NAME}/points/scroll",
            {
                "filter": {
                    "must": [
                        {"key": "metadata.kode", "match": {"value": code}}
                    ]
                },
                "limit": 1,
                "with_payload": True,
                "with_vectors": False
            }
        )
        
        points = result.get("result", {}).get("points", [])
        if points:
            return points[0].get("payload", {})
        return None
    except Exception as e:
        print(f"  ⚠️  Errore fetch {code}: {e}")
        return None


def get_all_kbli_from_qdrant() -> Dict[str, Dict]:
    """Estrae tutti i KBLI da Qdrant."""
    print("📊 Estrazione KBLI da Qdrant...")
    
    kbli_data = {}
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
        
        try:
            result = qdrant_request(
                "POST",
                f"/collections/{COLLECTION_NAME}/points/scroll",
                payload
            )
        except Exception as e:
            print(f"   ⚠️  Errore batch {batch_count + 1}: {e}")
            break
        
        points = result.get("result", {}).get("points", [])
        if not points:
            break
        
        for point in points:
            payload_data = point.get("payload", {})
            metadata = payload_data.get("metadata", {})
            kode = metadata.get("kode", "")
            
            if kode and isinstance(kode, str) and kode.isdigit() and len(kode) == 5:
                # Prendi il punto più completo se ci sono duplicati
                if kode not in kbli_data:
                    kbli_data[kode] = payload_data
                else:
                    # Confronta completezza
                    existing_fields = sum(1 for v in kbli_data[kode].get("metadata", {}).values() if v)
                    new_fields = sum(1 for v in metadata.values() if v)
                    if new_fields > existing_fields:
                        kbli_data[kode] = payload_data
        
        batch_count += 1
        if batch_count % 5 == 0:
            print(f"   Batch {batch_count}: {len(kbli_data)} KBLI unici finora...")
        
        next_offset = result.get("result", {}).get("next_page_offset")
        if not next_offset:
            break
        scroll_id = next_offset
    
    print(f"   ✅ Totale KBLI estratti da Qdrant: {len(kbli_data)}")
    return kbli_data


def get_extracted_kbli() -> Dict[str, Dict]:
    """Carica KBLI estratti da Lampiran I."""
    final_file = sorted(DATA_DIR.glob("kbli_complete_final_*.json"), 
                       key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not final_file:
        print("❌ Nessun file completo finale trovato!")
        return {}
    
    print(f"📁 Caricamento file: {final_file[0].name}")
    with open(final_file[0]) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    print(f"   ✅ Totale KBLI estratti: {len(kbli_data)}")
    return kbli_data


def normalize_value(value) -> str:
    """Normalizza valori per confronto."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return ",".join(sorted(str(v) for v in value))
    return str(value).strip()


def compare_kbli_fields(qdrant_kbli: Dict, extracted_kbli: Dict) -> Dict:
    """Confronta i campi di un KBLI tra Qdrant e estratto."""
    qdrant_meta = qdrant_kbli.get("metadata", {})
    extracted = extracted_kbli
    
    comparison = {
        "kode": extracted.get("kode", ""),
        "fields_comparison": {},
        "qdrant_better": [],
        "extracted_better": [],
        "needs_update": False,
        "update_reasons": []
    }
    
    # Campi da confrontare
    fields_to_compare = {
        "judul": ("judul", "judul"),
        "risk_level": ("risk_level", "tingkat_risiko"),
        "pma_allowed": ("pma_allowed", "pma_allowed"),
        "pma_max_percentage": ("pma_max_percentage", "pma_max_percentage"),
        "skala_usaha": ("scales", "skala_usaha"),
        "ruang_lingkup": ("ruang_lingkup", "ruang_lingkup"),
        "sektor": ("sektor", "sektor"),
    }
    
    for field_name, (qdrant_key, extracted_key) in fields_to_compare.items():
        qdrant_val = qdrant_meta.get(qdrant_key)
        extracted_val = extracted.get(extracted_key)
        
        qdrant_norm = normalize_value(qdrant_val)
        extracted_norm = normalize_value(extracted_val)
        
        comparison["fields_comparison"][field_name] = {
            "qdrant": qdrant_val,
            "extracted": extracted_val,
            "qdrant_present": bool(qdrant_val),
            "extracted_present": bool(extracted_val),
            "different": qdrant_norm != extracted_norm
        }
        
        # Determina quale è migliore
        if not qdrant_val and extracted_val:
            comparison["extracted_better"].append(field_name)
            comparison["needs_update"] = True
            comparison["update_reasons"].append(f"{field_name}: mancante in Qdrant, presente in estratto")
        elif qdrant_val and not extracted_val:
            comparison["qdrant_better"].append(field_name)
        elif qdrant_norm != extracted_norm:
            # Entrambi presenti ma diversi - estratto potrebbe essere più aggiornato
            comparison["extracted_better"].append(field_name)
            comparison["needs_update"] = True
            comparison["update_reasons"].append(f"{field_name}: valore diverso")
    
    return comparison


def compare_all_kbli():
    """Confronta tutti i KBLI comuni."""
    print("=" * 70)
    print("🔍 CONFRONTO QUALITÀ DATI KBLI")
    print("=" * 70)
    print()
    
    # Carica dati
    print("1️⃣  CARICAMENTO DATI:")
    qdrant_kbli = get_all_kbli_from_qdrant()
    print()
    extracted_kbli = get_extracted_kbli()
    print()
    
    # Trova KBLI comuni
    qdrant_codes = set(qdrant_kbli.keys())
    extracted_codes = set(extracted_kbli.keys())
    common_codes = qdrant_codes & extracted_codes
    
    print("2️⃣  STATISTICHE:")
    print(f"   KBLI in Qdrant: {len(qdrant_codes)}")
    print(f"   KBLI estratti: {len(extracted_codes)}")
    print(f"   KBLI comuni: {len(common_codes)}")
    print()
    
    # Confronta ogni KBLI comune
    print("3️⃣  CONFRONTO QUALITÀ:")
    comparisons = {}
    needs_update = []
    qdrant_better_count = defaultdict(int)
    extracted_better_count = defaultdict(int)
    
    for code in sorted(common_codes):
        comparison = compare_kbli_fields(qdrant_kbli[code], extracted_kbli[code])
        comparisons[code] = comparison
        
        if comparison["needs_update"]:
            needs_update.append(code)
        
        for field in comparison["qdrant_better"]:
            qdrant_better_count[field] += 1
        for field in comparison["extracted_better"]:
            extracted_better_count[field] += 1
    
    print(f"   KBLI che necessitano aggiornamento: {len(needs_update)}/{len(common_codes)} ({len(needs_update)/len(common_codes)*100:.1f}%)")
    print()
    
    # Statistiche per campo
    print("4️⃣  STATISTICHE PER CAMPO:")
    print("\n   Campi dove estratto è migliore:")
    for field, count in sorted(extracted_better_count.items(), key=lambda x: -x[1]):
        pct = count / len(common_codes) * 100
        print(f"      {field}: {count}/{len(common_codes)} ({pct:.1f}%)")
    
    print("\n   Campi dove Qdrant è migliore:")
    for field, count in sorted(qdrant_better_count.items(), key=lambda x: -x[1]):
        pct = count / len(common_codes) * 100
        print(f"      {field}: {count}/{len(common_codes)} ({pct:.1f}%)")
    print()
    
    # Campione KBLI che necessitano aggiornamento
    print("5️⃣  CAMPIONE KBLI CHE NECESSITANO AGGIORNAMENTO (primi 10):")
    for i, code in enumerate(needs_update[:10], 1):
        comp = comparisons[code]
        print(f"\n   [{i}] {code}: {extracted_kbli[code].get('judul', 'N/A')[:50]}...")
        print(f"      Motivi aggiornamento:")
        for reason in comp["update_reasons"][:3]:
            print(f"         - {reason}")
    print()
    
    # Salva report completo
    report = {
        "generated_at": datetime.now().isoformat(),
        "statistics": {
            "qdrant_total": len(qdrant_codes),
            "extracted_total": len(extracted_codes),
            "common_total": len(common_codes),
            "needs_update": len(needs_update),
            "update_percentage": len(needs_update) / len(common_codes) * 100 if common_codes else 0
        },
        "field_statistics": {
            "extracted_better": dict(extracted_better_count),
            "qdrant_better": dict(qdrant_better_count)
        },
        "kbli_needing_update": sorted(needs_update),
        "comparisons": {
            code: {
                "kode": comp["kode"],
                "needs_update": comp["needs_update"],
                "update_reasons": comp["update_reasons"],
                "fields_comparison": comp["fields_comparison"]
            }
            for code, comp in comparisons.items()
            if comp["needs_update"]
        }
    }
    
    report_file = DATA_DIR / "kbli_quality_comparison.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Report completo salvato: {report_file.name}")
    print()
    
    # Riepilogo finale
    print("=" * 70)
    print("📊 RIEPILOGO FINALE")
    print("=" * 70)
    print(f"   KBLI comuni analizzati: {len(common_codes)}")
    print(f"   KBLI che necessitano aggiornamento: {len(needs_update)}")
    print(f"   Percentuale: {len(needs_update)/len(common_codes)*100:.1f}%")
    print()
    
    if needs_update:
        print("   Campi più spesso migliori nell'estratto:")
        top_fields = sorted(extracted_better_count.items(), key=lambda x: -x[1])[:5]
        for field, count in top_fields:
            print(f"      {field}: {count} KBLI")
    print()
    print("=" * 70)


if __name__ == "__main__":
    compare_all_kbli()
