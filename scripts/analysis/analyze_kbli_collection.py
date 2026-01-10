#!/usr/bin/env python3
"""
Analizza in dettaglio la collection kbli_unified in Qdrant.
Verifica struttura dati, qualità, campi presenti, e confronta con dati estratti.
"""

import json
import os
import sys
from pathlib import Path
from typing import Set, Dict, List
from collections import Counter, defaultdict

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


def get_collection_info() -> dict:
    """Ottiene info completa sulla collection."""
    result = qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
    return result.get("result", {})


def sample_points(limit: int = 100) -> List[dict]:
    """Estrae un campione di punti dalla collection."""
    result = qdrant_request(
        "POST",
        f"/collections/{COLLECTION_NAME}/points/scroll",
        {
            "limit": limit,
            "with_payload": True,
            "with_vectors": False
        }
    )
    return result.get("result", {}).get("points", [])


def analyze_collection():
    """Analizza in dettaglio la collection kbli_unified."""
    print("=" * 70)
    print("🔍 ANALISI DETTAGLIATA COLLECTION KBLI_UNIFIED")
    print("=" * 70)
    print()
    
    # 1. Info collection
    print("1️⃣  INFO COLLECTION:")
    try:
        info = get_collection_info()
        points_count = info.get("points_count", 0)
        vectors_count = info.get("vectors_count", 0)
        indexed_vectors_count = info.get("indexed_vectors_count", 0)
        
        print(f"   Collection: {COLLECTION_NAME}")
        print(f"   URL: {QDRANT_URL}")
        print(f"   Totale punti: {points_count}")
        print(f"   Vettori: {vectors_count}")
        print(f"   Vettori indicizzati: {indexed_vectors_count}")
        
        # Config vector
        config = info.get("config", {})
        params = config.get("params", {})
        vectors_config = params.get("vectors", {})
        if vectors_config:
            size = vectors_config.get("size", "N/A")
            distance = vectors_config.get("distance", "N/A")
            print(f"   Vector size: {size}")
            print(f"   Distance: {distance}")
        
        print()
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return
    
    # 2. Campione punti
    print("2️⃣  ANALISI CAMPIONE DATI (primi 100 punti):")
    sample = sample_points(limit=100)
    print(f"   Punti analizzati: {len(sample)}")
    print()
    
    if not sample:
        print("   ⚠️  Collection vuota!")
        return
    
    # 3. Analisi struttura payload
    print("3️⃣  STRUTTURA PAYLOAD:")
    payload_fields = defaultdict(int)
    metadata_fields = defaultdict(int)
    kbli_codes = set()
    sources = Counter()
    
    for point in sample:
        payload = point.get("payload", {})
        
        # Campi payload top-level
        for field in payload.keys():
            payload_fields[field] += 1
        
        # Metadata
        metadata = payload.get("metadata", {})
        if metadata:
            for field in metadata.keys():
                metadata_fields[field] += 1
            
            # KBLI code
            kode = metadata.get("kode", "")
            if kode and isinstance(kode, str) and kode.isdigit() and len(kode) == 5:
                kbli_codes.add(kode)
            
            # Source
            source = metadata.get("source", payload.get("source", "unknown"))
            sources[source] += 1
    
    print("   Campi payload top-level:")
    for field, count in sorted(payload_fields.items(), key=lambda x: -x[1]):
        print(f"      {field}: {count}/{len(sample)} ({count/len(sample)*100:.1f}%)")
    
    print()
    print("   Campi metadata:")
    for field, count in sorted(metadata_fields.items(), key=lambda x: -x[1]):
        print(f"      {field}: {count}/{len(sample)} ({count/len(sample)*100:.1f}%)")
    
    print()
    print(f"   KBLI unici nel campione: {len(kbli_codes)}")
    print()
    print("   Sources (top 10):")
    for source, count in sources.most_common(10):
        print(f"      {source}: {count}")
    print()
    
    # 4. Analisi qualità dati
    print("4️⃣  QUALITÀ DATI (campione):")
    quality_stats = {
        "has_kode": 0,
        "has_judul": 0,
        "has_risk_level": 0,
        "has_pma_allowed": 0,
        "has_pma_percentage": 0,
        "has_skala_usaha": 0,
        "has_ruang_lingkup": 0,
        "has_sektor": 0,
    }
    
    for point in sample:
        payload = point.get("payload", {})
        metadata = payload.get("metadata", {})
        content = payload.get("content", "")
        
        if metadata.get("kode"):
            quality_stats["has_kode"] += 1
        if metadata.get("judul"):
            quality_stats["has_judul"] += 1
        if metadata.get("risk_level") or metadata.get("tingkat_risiko"):
            quality_stats["has_risk_level"] += 1
        if metadata.get("pma_allowed") is not None:
            quality_stats["has_pma_allowed"] += 1
        if metadata.get("pma_max_percentage"):
            quality_stats["has_pma_percentage"] += 1
        if metadata.get("skala_usaha"):
            quality_stats["has_skala_usaha"] += 1
        if metadata.get("ruang_lingkup"):
            quality_stats["has_ruang_lingkup"] += 1
        if metadata.get("sektor"):
            quality_stats["has_sektor"] += 1
    
    for field, count in quality_stats.items():
        pct = count / len(sample) * 100 if sample else 0
        status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
        print(f"   {status} {field}: {count}/{len(sample)} ({pct:.1f}%)")
    print()
    
    # 5. Campione punti dettagliato
    print("5️⃣  CAMPIONE PUNTI DETTAGLIATO (primi 3):")
    for i, point in enumerate(sample[:3], 1):
        payload = point.get("payload", {})
        metadata = payload.get("metadata", {})
        content = payload.get("content", "")
        
        print(f"\n   [{i}] Point ID: {point.get('id', 'N/A')}")
        print(f"      Kode: {metadata.get('kode', 'N/A')}")
        print(f"      Judul: {metadata.get('judul', 'N/A')[:60]}...")
        print(f"      Risk Level: {metadata.get('risk_level', metadata.get('tingkat_risiko', 'N/A'))}")
        print(f"      PMA Allowed: {metadata.get('pma_allowed', 'N/A')}")
        print(f"      PMA Max %: {metadata.get('pma_max_percentage', 'N/A')}")
        print(f"      Source: {metadata.get('source', 'N/A')}")
        print(f"      Content length: {len(content)} chars")
        if content:
            print(f"      Content preview: {content[:100]}...")
    print()
    
    # 6. Estrazione completa codici KBLI
    print("6️⃣  ESTRAZIONE COMPLETA CODICI KBLI:")
    print("   (Questo può richiedere alcuni minuti...)")
    
    all_kbli_codes = set()
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
                all_kbli_codes.add(kode)
        
        batch_count += 1
        if batch_count % 10 == 0:
            print(f"   Batch {batch_count}: {len(all_kbli_codes)} KBLI unici finora...")
        
        next_offset = result.get("result", {}).get("next_page_offset")
        if not next_offset:
            break
        scroll_id = next_offset
    
    print(f"   ✅ Totale KBLI unici: {len(all_kbli_codes)}")
    print()
    
    # 7. Distribuzione per prefisso
    print("7️⃣  DISTRIBUZIONE PER PREFISSO (primi 2 cifre):")
    prefixes = Counter(code[:2] for code in all_kbli_codes)
    for prefix in sorted(prefixes.keys())[:20]:
        print(f"   {prefix}xx: {prefixes[prefix]} KBLI")
    print()
    
    # 8. Salva report completo
    report = {
        "collection_info": {
            "name": COLLECTION_NAME,
            "url": QDRANT_URL,
            "points_count": points_count,
            "vectors_count": vectors_count,
        },
        "sample_analysis": {
            "sample_size": len(sample),
            "payload_fields": dict(payload_fields),
            "metadata_fields": dict(metadata_fields),
            "sources": dict(sources),
            "quality_stats": quality_stats,
        },
        "complete_analysis": {
            "total_kbli_unique": len(all_kbli_codes),
            "kbli_codes": sorted(list(all_kbli_codes)),
            "prefixes": dict(prefixes),
        }
    }
    
    report_file = DATA_DIR / "kbli_collection_analysis.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"📁 Report completo salvato: {report_file.name}")
    print()
    
    # 9. Riepilogo finale
    print("=" * 70)
    print("📊 RIEPILOGO FINALE")
    print("=" * 70)
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Totale punti: {points_count}")
    print(f"   KBLI unici: {len(all_kbli_codes)}")
    print(f"   Sources principali: {', '.join([s[0] for s in sources.most_common(3)])}")
    print()
    print("=" * 70)


if __name__ == "__main__":
    analyze_collection()
