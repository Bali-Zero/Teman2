#!/usr/bin/env python3
"""
ZANTARA - Embedding Quality Analyzer

Analizza la qualità degli embeddings e la similarità tra documenti in Qdrant.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import requests

# Get Qdrant URL from env or use default
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")


class SimpleQdrantClient:
    """Semplice client Qdrant standalone"""

    def __init__(self, qdrant_url: str, collection_name: str):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.collection_name = collection_name

    def get_sample_with_vectors(self, limit: int = 100) -> dict[str, Any]:
        """Estrai sample documenti con vettori"""
        try:
            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/scroll"
            payload = {"limit": limit, "with_payload": True, "with_vectors": True}
            response = requests.post(url, json=payload, timeout=60)

            if response.status_code == 200:
                data = response.json().get("result", {})
                points = data.get("points", [])

                return {
                    "ids": [str(p["id"]) for p in points],
                    "documents": [p.get("payload", {}).get("text", "") for p in points],
                    "metadatas": [
                        p.get("payload", {}).get("metadata", {}) for p in points
                    ],
                    "vectors": [p.get("vector", []) for p in points],
                }
            else:
                return {"ids": [], "documents": [], "metadatas": [], "vectors": []}
        except Exception as e:
            print(f"   ⚠️ Errore: {e}")
            return {"ids": [], "documents": [], "metadatas": [], "vectors": []}


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calcola cosine similarity tra due vettori"""
    if len(vec1) != len(vec2):
        return 0.0

    vec1_arr = np.array(vec1)
    vec2_arr = np.array(vec2)

    dot_product = np.dot(vec1_arr, vec2_arr)
    norm1 = np.linalg.norm(vec1_arr)
    norm2 = np.linalg.norm(vec2_arr)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def analyze_embedding_quality(
    collection_name: str, sample_size: int = 100
) -> dict[str, Any]:
    """Analizza qualità embeddings per una collezione"""
    print(f"\n{'=' * 80}")
    print(f"🔍 Analizzando qualità embeddings: {collection_name}")
    print(f"{'=' * 80}")

    client = SimpleQdrantClient(QDRANT_URL, collection_name)
    sample = client.get_sample_with_vectors(limit=sample_size)

    if not sample["vectors"]:
        print("   ⚠️ Nessun vettore estratto")
        return {"error": "No vectors extracted"}

    vectors = sample["vectors"]
    documents = sample["documents"]

    # Verifica dimensione vettori
    vector_dimensions = [len(v) for v in vectors if v]
    if not vector_dimensions:
        return {"error": "No valid vectors"}

    expected_dim = 1536
    dimension_stats = {
        "expected": expected_dim,
        "actual": vector_dimensions[0] if vector_dimensions else 0,
        "consistent": all(d == expected_dim for d in vector_dimensions),
        "min": min(vector_dimensions),
        "max": max(vector_dimensions),
    }

    print("   📐 Dimensione vettori:")
    print(f"      Attesa: {expected_dim}")
    print(f"      Attuale: {dimension_stats['actual']}")
    print(f"      Consistente: {'✅' if dimension_stats['consistent'] else '❌'}")

    # Calcola similarità tra documenti
    print("\n   🔗 Calcolando similarità tra documenti...")
    similarities = []
    similar_pairs = []

    # Calcola similarità per coppie di documenti
    for i in range(min(50, len(vectors))):  # Limita a 50 per performance
        for j in range(i + 1, min(50, len(vectors))):
            if vectors[i] and vectors[j]:
                sim = cosine_similarity(vectors[i], vectors[j])
                similarities.append(sim)

                # Trova coppie molto simili (>0.9) o molto diverse (<0.1)
                if sim > 0.9:
                    similar_pairs.append(
                        {
                            "doc1_index": i,
                            "doc2_index": j,
                            "similarity": sim,
                            "doc1_preview": documents[i][:100] if documents[i] else "",
                            "doc2_preview": documents[j][:100] if documents[j] else "",
                        }
                    )

    if similarities:
        similarity_stats = {
            "count": len(similarities),
            "mean": float(np.mean(similarities)),
            "median": float(np.median(similarities)),
            "std": float(np.std(similarities)),
            "min": float(np.min(similarities)),
            "max": float(np.max(similarities)),
            "high_similarity_pairs": len([s for s in similarities if s > 0.9]),
            "low_similarity_pairs": len([s for s in similarities if s < 0.1]),
        }

        print("   📊 Statistiche similarità:")
        print(f"      Media: {similarity_stats['mean']:.3f}")
        print(f"      Mediana: {similarity_stats['median']:.3f}")
        print(f"      Min: {similarity_stats['min']:.3f}")
        print(f"      Max: {similarity_stats['max']:.3f}")
        print(
            f"      Coppie molto simili (>0.9): {similarity_stats['high_similarity_pairs']}"
        )
        print(
            f"      Coppie molto diverse (<0.1): {similarity_stats['low_similarity_pairs']}"
        )
    else:
        similarity_stats = {}

    # Analizza distribuzione vettori
    print("\n   📈 Analizzando distribuzione vettori...")
    all_vectors = np.array([v for v in vectors if v and len(v) == expected_dim])

    if len(all_vectors) > 0:
        vector_norms = [np.linalg.norm(v) for v in all_vectors]
        distribution_stats = {
            "count": len(all_vectors),
            "mean_norm": float(np.mean(vector_norms)),
            "std_norm": float(np.std(vector_norms)),
            "min_norm": float(np.min(vector_norms)),
            "max_norm": float(np.max(vector_norms)),
        }

        print(f"      Norma media: {distribution_stats['mean_norm']:.3f}")
        print(f"      Deviazione std: {distribution_stats['std_norm']:.3f}")
    else:
        distribution_stats = {}

    result = {
        "collection_name": collection_name,
        "sample_size": len(vectors),
        "dimension_stats": dimension_stats,
        "similarity_stats": similarity_stats,
        "distribution_stats": distribution_stats,
        "similar_pairs": similar_pairs[:10],  # Primi 10 esempi
    }

    return result


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Embedding Quality Analyzer")
    print("=" * 80)

    collections = [
        "visa_oracle",
        "kbli_unified",
        "tax_genius",
        "legal_unified",
        "knowledge_base",
    ]

    results = {
        "analysis_date": datetime.now().isoformat(),
        "collections": {},
    }

    for collection_name in collections:
        try:
            result = analyze_embedding_quality(collection_name, sample_size=100)
            results["collections"][collection_name] = result
        except Exception as e:
            print(f"   ❌ Errore: {e}")
            results["collections"][collection_name] = {"error": str(e)}

    # Summary
    print(f"\n{'=' * 80}")
    print("📊 RIEPILOGO FINALE")
    print(f"{'=' * 80}")

    for collection_name, result in results["collections"].items():
        if "error" not in result:
            dim_stats = result.get("dimension_stats", {})
            sim_stats = result.get("similarity_stats", {})

            print(f"\n{collection_name}:")
            print(
                f"   Dimensione: {dim_stats.get('actual', 'N/A')} (consistente: {dim_stats.get('consistent', False)})"
            )
            if sim_stats:
                print(f"   Similarità media: {sim_stats.get('mean', 0):.3f}")
                print(
                    f"   Coppie simili (>0.9): {sim_stats.get('high_similarity_pairs', 0)}"
                )

    # Salva risultati
    output_dir = Path(__file__).parent / "qdrant_analysis_reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"embedding_quality_{timestamp}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Report salvato: {json_path}")
    print("\n✅ Analisi completata!")


if __name__ == "__main__":
    main()
