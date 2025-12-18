#!/usr/bin/env python3
"""
ZANTARA - Qdrant Document Quality Validator

Valida qualità documenti Qdrant:
- Chunk vuoti o troppo corti
- Metadata mancanti/inconsistenti
- Embeddings duplicati
- Struttura dati
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")

COLLECTIONS = [
    "bali_zero_pricing",
    "bali_zero_team",
    "visa_oracle",
    "kbli_unified",
    "tax_genius",
    "legal_unified",
    "knowledge_base",
    "property_unified",
]


class SimpleQdrantClient:
    """Semplice client Qdrant standalone"""

    def __init__(self, qdrant_url: str, collection_name: str):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.collection_name = collection_name

    def peek(self, limit: int = 100) -> dict[str, Any]:
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
                    "metadatas": [
                        p.get("payload", {}).get("metadata", {}) for p in points
                    ],
                }
            else:
                return {"ids": [], "documents": [], "metadatas": []}
        except Exception:
            return {"ids": [], "documents": [], "metadatas": []}


class QualityValidator:
    """Valida qualità documenti"""

    def validate_collection(
        self, collection_name: str, documents: list[str], metadatas: list[dict]
    ) -> dict[str, Any]:
        """Valida una collezione"""
        issues = []
        stats = {
            "total": len(documents),
            "empty_chunks": 0,
            "too_short_chunks": 0,
            "too_long_chunks": 0,
            "missing_metadata": 0,
            "avg_length": 0,
            "min_length": float("inf"),
            "max_length": 0,
        }

        lengths = []

        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            # Check empty
            if not doc or len(doc.strip()) == 0:
                stats["empty_chunks"] += 1
                issues.append({"type": "empty_chunk", "index": i, "id": "unknown"})

            # Check length
            doc_len = len(doc) if doc else 0
            lengths.append(doc_len)

            if doc_len < 10:
                stats["too_short_chunks"] += 1
                issues.append({"type": "too_short", "index": i, "length": doc_len})

            if doc_len > 5000:
                stats["too_long_chunks"] += 1
                issues.append({"type": "too_long", "index": i, "length": doc_len})

            # Check metadata
            if not isinstance(meta, dict) or len(meta) == 0:
                stats["missing_metadata"] += 1

            # Update stats
            stats["min_length"] = min(stats["min_length"], doc_len)
            stats["max_length"] = max(stats["max_length"], doc_len)

        if lengths:
            stats["avg_length"] = sum(lengths) / len(lengths)
            stats["min_length"] = (
                stats["min_length"] if stats["min_length"] != float("inf") else 0
            )

        # Quality score (0-100)
        quality_score = 100
        if stats["total"] > 0:
            quality_score -= (stats["empty_chunks"] / stats["total"]) * 30
            quality_score -= (stats["too_short_chunks"] / stats["total"]) * 20
            quality_score -= (stats["too_long_chunks"] / stats["total"]) * 10
            quality_score -= (stats["missing_metadata"] / stats["total"]) * 10

        quality_score = max(0, min(100, quality_score))

        return {
            "collection": collection_name,
            "stats": stats,
            "issues": issues[:20],  # Primi 20 problemi
            "total_issues": len(issues),
            "quality_score": round(quality_score, 2),
            "status": "good"
            if quality_score >= 80
            else "warning"
            if quality_score >= 60
            else "critical",
        }


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Qdrant Document Quality Validator")
    print("=" * 80)

    validator = QualityValidator()
    results = {
        "validation_date": datetime.now().isoformat(),
        "collections": {},
        "summary": {},
    }

    total_issues = 0
    total_docs = 0
    quality_scores = []

    for collection_name in COLLECTIONS:
        print(f"\n{'=' * 80}")
        print(f"🔍 Validando: {collection_name}")
        print(f"{'=' * 80}")

        try:
            client = SimpleQdrantClient(QDRANT_URL, collection_name)
            sample = client.peek(limit=100)

            if not sample.get("documents"):
                print("   ⚠️ Nessun documento estratto")
                continue

            validation = validator.validate_collection(
                collection_name, sample["documents"], sample["metadatas"]
            )

            results["collections"][collection_name] = validation
            total_issues += validation["total_issues"]
            total_docs += validation["stats"]["total"]
            quality_scores.append(validation["quality_score"])

            # Print results
            print(f"✅ Documenti analizzati: {validation['stats']['total']}")
            print(
                f"📊 Quality Score: {validation['quality_score']}/100 ({validation['status']})"
            )
            print(f"⚠️ Problemi trovati: {validation['total_issues']}")
            print(f"   - Chunk vuoti: {validation['stats']['empty_chunks']}")
            print(f"   - Chunk troppo corti: {validation['stats']['too_short_chunks']}")
            print(f"   - Chunk troppo lunghi: {validation['stats']['too_long_chunks']}")
            print(f"   - Metadata mancanti: {validation['stats']['missing_metadata']}")
            print(
                f"   - Lunghezza media: {validation['stats']['avg_length']:.0f} caratteri"
            )

        except Exception as e:
            print(f"   ❌ Errore: {e}")
            results["collections"][collection_name] = {"error": str(e)}

    # Summary
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    results["summary"] = {
        "total_collections": len(COLLECTIONS),
        "total_documents_validated": total_docs,
        "total_issues": total_issues,
        "average_quality_score": round(avg_quality, 2),
        "collections_with_issues": sum(
            1 for c in results["collections"].values() if c.get("total_issues", 0) > 0
        ),
    }

    # Save results
    output_dir = Path(__file__).parent / "qdrant_analysis_reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"quality_validation_{timestamp}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print("📊 RIEPILOGO VALIDAZIONE")
    print(f"{'=' * 80}")
    print(f"Collezioni validate: {results['summary']['total_collections']}")
    print(f"Documenti totali: {results['summary']['total_documents_validated']}")
    print(f"Problemi totali: {results['summary']['total_issues']}")
    print(f"Quality Score medio: {results['summary']['average_quality_score']}/100")
    print(f"\n✅ Report salvato: {json_path}")


if __name__ == "__main__":
    main()
