#!/usr/bin/env python3
"""
ZANTARA - Test Metadata Extraction su Collezioni Reali

Testa Pattern, ML e Hybrid extraction su documenti reali da Qdrant.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

# Import extractors
from extract_and_update_metadata import MetadataExtractor

try:
    from ml_metadata_extractor import MLMetadataExtractor, HybridMetadataExtractor
    ML_AVAILABLE = True
except:
    ML_AVAILABLE = False

# Qdrant connection
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")


class SimpleQdrantClient:
    """Semplice client Qdrant standalone"""

    def __init__(self, qdrant_url: str, collection_name: str):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.collection_name = collection_name

    def peek(self, limit: int = 10) -> dict[str, Any]:
        """Estrai sample documenti"""
        try:
            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll"
            payload = {"limit": limit, "with_payload": True, "with_vectors": False}
            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json().get("result", {})
                points = data.get("points", [])

                return {
                    "ids": [str(p["id"]) for p in points],
                    "documents": [p.get("payload", {}).get("text", "") for p in points],
                    "metadatas": [p.get("payload", {}).get("metadata", {}) for p in points],
                }
            else:
                return {"ids": [], "documents": [], "metadatas": []}
        except Exception as e:
            print(f"   ⚠️ Errore peek: {e}")
            return {"ids": [], "documents": [], "metadatas": []}


def test_collection(
    collection_name: str, 
    limit: int = 5,
    use_ml: bool = False
):
    """Testa extraction su una collezione"""
    print(f"\n{'='*80}")
    print(f"📚 COLLEZIONE: {collection_name}")
    print(f"{'='*80}")
    
    # Connetti a Qdrant
    client = SimpleQdrantClient(QDRANT_URL, collection_name)
    data = client.peek(limit=limit)
    
    if not data["documents"]:
        print(f"   ⚠️ Nessun documento trovato in {collection_name}")
        return
    
    print(f"\n📊 Documenti estratti: {len(data['documents'])}")
    
    # Inizializza extractors
    pattern_extractor = MetadataExtractor()
    
    ml_extractor = None
    hybrid_extractor = None
    if ML_AVAILABLE and use_ml:
        try:
            ml_extractor = MLMetadataExtractor()
            hybrid_extractor = HybridMetadataExtractor()
        except Exception as e:
            print(f"   ⚠️ ML extractor non disponibile: {e}")
    
    # Test su ogni documento
    results = []
    for i, (doc_id, text, existing_metadata) in enumerate(
        zip(data["ids"], data["documents"], data["metadatas"])
    ):
        print(f"\n{'─'*80}")
        print(f"📄 DOCUMENTO {i+1}/{len(data['documents'])}")
        print(f"   ID: {doc_id}")
        print(f"   Text length: {len(text)} chars")
        print(f"   Existing metadata fields: {len(existing_metadata)}")
        
        # Pattern extraction
        pattern_meta = pattern_extractor.extract_metadata(collection_name, text)
        print(f"\n   🔍 PATTERN EXTRACTION:")
        print(f"      Campi estratti: {len(pattern_meta)}")
        if pattern_meta:
            for k, v in list(pattern_meta.items())[:5]:
                v_str = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
                print(f"      - {k}: {v_str}")
        else:
            print(f"      (nessun campo estratto)")
        
        # ML extraction (se disponibile)
        ml_meta = {}
        if ml_extractor:
            try:
                print(f"\n   🤖 ML EXTRACTION:")
                ml_meta = ml_extractor.extract_with_ml(collection_name, text)
                print(f"      Campi estratti: {len(ml_meta)}")
                if ml_meta:
                    for k, v in list(ml_meta.items())[:5]:
                        v_str = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
                        print(f"      - {k}: {v_str}")
                else:
                    print(f"      (nessun campo estratto o bloccato)")
            except Exception as e:
                print(f"      ⚠️ Errore: {str(e)[:100]}")
        
        # Hybrid extraction (se disponibile)
        hybrid_meta = {}
        if hybrid_extractor:
            try:
                print(f"\n   🔄 HYBRID EXTRACTION:")
                hybrid_meta = hybrid_extractor.extract(collection_name, text, use_ml=use_ml)
                print(f"      Campi estratti: {len(hybrid_meta)}")
                if hybrid_meta:
                    for k, v in list(hybrid_meta.items())[:5]:
                        v_str = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
                        print(f"      - {k}: {v_str}")
            except Exception as e:
                print(f"      ⚠️ Errore: {str(e)[:100]}")
        
        # Confronto
        print(f"\n   📊 CONFRONTO:")
        print(f"      Pattern: {len(pattern_meta)} campi")
        if ml_extractor:
            print(f"      ML: {len(ml_meta)} campi")
        if hybrid_extractor:
            print(f"      Hybrid: {len(hybrid_meta)} campi")
        
        # Salva risultati
        results.append({
            "doc_id": doc_id,
            "text_length": len(text),
            "existing_metadata_fields": len(existing_metadata),
            "pattern_fields": len(pattern_meta),
            "ml_fields": len(ml_meta) if ml_extractor else 0,
            "hybrid_fields": len(hybrid_meta) if hybrid_extractor else 0,
            "pattern_metadata": pattern_meta,
            "ml_metadata": ml_meta,
            "hybrid_metadata": hybrid_meta,
        })
    
    # Statistiche aggregate
    print(f"\n{'─'*80}")
    print(f"📈 STATISTICHE AGGREGATE:")
    avg_pattern = sum(r["pattern_fields"] for r in results) / len(results) if results else 0
    avg_ml = sum(r["ml_fields"] for r in results) / len(results) if results and ml_extractor else 0
    avg_hybrid = sum(r["hybrid_fields"] for r in results) / len(results) if results and hybrid_extractor else 0
    
    print(f"   Pattern (media): {avg_pattern:.1f} campi/documento")
    if ml_extractor:
        print(f"   ML (media): {avg_ml:.1f} campi/documento")
    if hybrid_extractor:
        print(f"   Hybrid (media): {avg_hybrid:.1f} campi/documento")
    
    return results


def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test metadata extraction su collezioni reali")
    parser.add_argument("--collection", type=str, help="Nome collezione (default: tutte)")
    parser.add_argument("--limit", type=int, default=5, help="Numero documenti da testare (default: 5)")
    parser.add_argument("--use-ml", action="store_true", help="Usa ML extraction (richiede GOOGLE_API_KEY)")
    
    args = parser.parse_args()
    
    print("="*80)
    print("ZANTARA - Test Metadata Extraction su Collezioni Reali")
    print("="*80)
    
    # Check ML availability
    api_key = os.getenv("GOOGLE_API_KEY")
    use_ml = args.use_ml and ML_AVAILABLE and api_key
    
    if args.use_ml:
        if not ML_AVAILABLE:
            print("\n⚠️ ML extraction non disponibile (modulo non trovato)")
        elif not api_key:
            print("\n⚠️ GOOGLE_API_KEY non configurato")
        else:
            print(f"\n✅ ML extraction disponibile (GOOGLE_API_KEY configurato)")
    else:
        print(f"\n📝 Pattern extraction only (usa --use-ml per abilitare ML)")
    
    # Collezioni da testare
    collections_to_test = [
        "visa_oracle",
        "kbli_unified", 
        "tax_genius",
        "bali_zero_pricing",
    ]
    
    if args.collection:
        collections_to_test = [args.collection]
    
    # Test ogni collezione
    all_results = {}
    for collection_name in collections_to_test:
        try:
            results = test_collection(collection_name, limit=args.limit, use_ml=use_ml)
            if results:
                all_results[collection_name] = results
        except Exception as e:
            print(f"\n❌ Errore testando {collection_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Report finale
    print(f"\n{'='*80}")
    print("📊 REPORT FINALE")
    print(f"{'='*80}")
    
    for collection_name, results in all_results.items():
        avg_pattern = sum(r["pattern_fields"] for r in results) / len(results) if results else 0
        avg_ml = sum(r["ml_fields"] for r in results) / len(results) if results and use_ml else 0
        avg_hybrid = sum(r["hybrid_fields"] for r in results) / len(results) if results and use_ml else 0
        
        print(f"\n{collection_name}:")
        print(f"   Documenti testati: {len(results)}")
        print(f"   Pattern (media): {avg_pattern:.1f} campi/doc")
        if use_ml:
            print(f"   ML (media): {avg_ml:.1f} campi/doc")
            print(f"   Hybrid (media): {avg_hybrid:.1f} campi/doc")
    
    # Salva risultati JSON
    output_file = Path(__file__).parent / "test_extraction_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n💾 Risultati salvati in: {output_file}")
    
    print("\n✅ Test completato!")


if __name__ == "__main__":
    main()

