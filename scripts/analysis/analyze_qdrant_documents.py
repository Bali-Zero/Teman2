#!/usr/bin/env python3
"""
ZANTARA - Qdrant Documents Structure Analyzer

Analizza la struttura completa dei 25k+ documenti in Qdrant:
- Statistiche per collezione
- Analisi metadata
- Esempi documenti
- Verifica qualità
- Report JSON/Markdown
"""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# Get Qdrant URL from env or use default
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")


class SimpleQdrantClient:
    """Semplice client Qdrant standalone senza dipendenze backend"""

    def __init__(self, qdrant_url: str, collection_name: str):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.collection_name = collection_name

    def get_collection_stats(self) -> dict[str, Any]:
        """Ottieni statistiche collezione"""
        try:
            url = f"{self.qdrant_url}/collections/{self.collection_name}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json().get("result", {})
                return {
                    "collection_name": self.collection_name,
                    "total_documents": data.get("points_count", 0),
                    "vector_size": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size", 1536),
                    "distance": data.get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("distance", "Cosine"),
                    "status": data.get("status", "unknown"),
                }
            else:
                return {
                    "collection_name": self.collection_name,
                    "error": f"HTTP {response.status_code}",
                }
        except Exception as e:
            return {"collection_name": self.collection_name, "error": str(e)}

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
                    "metadatas": [
                        p.get("payload", {}).get("metadata", {}) for p in points
                    ],
                }
            else:
                return {"ids": [], "documents": [], "metadatas": []}
        except Exception as e:
            print(f"   ⚠️ Errore peek: {e}")
            return {"ids": [], "documents": [], "metadatas": []}


# Collezioni reali da analizzare (dal SearchService)
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

# Collezioni con alias (per riferimento)
COLLECTION_ALIASES = {
    "kbli_eye": "kbli_unified",
    "legal_architect": "legal_unified",
    "kb_indonesian": "knowledge_base",
    "zantara_books": "knowledge_base",
    "cultural_insights": "knowledge_base",
    "tax_updates": "tax_genius",
    "tax_knowledge": "tax_genius",
    "property_listings": "property_unified",
    "property_knowledge": "property_unified",
    "legal_updates": "legal_unified",
    "legal_intelligence": "legal_unified",
}


class QdrantDocumentAnalyzer:
    """Analizzatore completo della struttura documenti Qdrant"""

    def __init__(self, qdrant_url: str = None):
        """Inizializza l'analizzatore"""
        self.qdrant_url = qdrant_url or QDRANT_URL
        self.results = {
            "analysis_date": datetime.now().isoformat(),
            "collections": {},
            "summary": {},
            "metadata_analysis": {},
            "quality_issues": [],
        }

    def analyze_collection(self, collection_name: str) -> dict[str, Any]:
        """Analizza una singola collezione"""
        print(f"\n{'=' * 80}")
        print(f"📊 Analizzando collezione: {collection_name}")
        print(f"{'=' * 80}")

        try:
            client = SimpleQdrantClient(
                qdrant_url=self.qdrant_url, collection_name=collection_name
            )

            # 1. Statistiche collezione
            stats = client.get_collection_stats()
            print(f"✅ Connesso a {collection_name}")
            print(f"   Documenti totali: {stats.get('total_documents', 0)}")
            print(f"   Vector size: {stats.get('vector_size', 'N/A')}")
            print(f"   Distance metric: {stats.get('distance', 'N/A')}")
            print(f"   Status: {stats.get('status', 'N/A')}")

            if stats.get("error"):
                print(f"   ⚠️ Errore: {stats['error']}")
                return {"error": stats["error"]}

            total_docs = stats.get("total_documents", 0)
            if total_docs == 0:
                print("   ⚠️ Collezione vuota!")
                return {"empty": True}

            # 2. Estrai sample documenti (max 100 per analisi)
            print("\n📥 Estraendo sample documenti...")
            sample_size = min(100, total_docs)
            sample = client.peek(limit=sample_size)

            if not sample.get("documents"):
                print("   ⚠️ Nessun documento estratto")
                return {"error": "No documents extracted"}

            # 3. Analisi metadata
            print("\n🔍 Analizzando metadata...")
            metadata_analysis = self._analyze_metadata(sample["metadatas"])

            # 4. Analisi qualità
            print("\n✅ Verificando qualità...")
            quality_issues = self._check_quality(
                sample["documents"], sample["metadatas"]
            )

            # 5. Statistiche chunk
            chunk_stats = self._analyze_chunks(sample["documents"])

            # 6. Esempi documenti (primi 3)
            examples = []
            for i in range(min(3, len(sample["documents"]))):
                examples.append(
                    {
                        "id": sample["ids"][i],
                        "text_preview": sample["documents"][i][:200] + "..."
                        if len(sample["documents"][i]) > 200
                        else sample["documents"][i],
                        "text_length": len(sample["documents"][i]),
                        "metadata": sample["metadatas"][i],
                    }
                )

            collection_result = {
                "stats": stats,
                "metadata_analysis": metadata_analysis,
                "quality_issues": quality_issues,
                "chunk_stats": chunk_stats,
                "examples": examples,
                "sample_size": len(sample["documents"]),
            }

            # Print summary
            print(f"\n📈 Riepilogo {collection_name}:")
            print(
                f"   Campi metadata unici: {len(metadata_analysis.get('unique_fields', []))}"
            )
            print(f"   Problemi qualità: {len(quality_issues)}")
            print(
                f"   Lunghezza media chunk: {chunk_stats.get('avg_length', 0):.0f} caratteri"
            )

            return collection_result

        except Exception as e:
            print(f"   ❌ Errore analizzando {collection_name}: {e}")
            return {"error": str(e)}

    def _analyze_metadata(self, metadatas: list[dict]) -> dict[str, Any]:
        """Analizza struttura e contenuto dei metadata"""
        if not metadatas:
            return {}

        # Raccogli tutti i campi (gestendo dict annidati)
        all_fields = set()
        field_values = defaultdict(list)
        field_types = defaultdict(set)

        def extract_fields(obj, prefix=""):
            """Estrae ricorsivamente i campi da dict annidati"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, dict):
                        # Dict annidato: aggiungi il campo e continua ricorsivamente
                        all_fields.add(full_key)
                        field_values[full_key].append("[nested_dict]")
                        field_types[full_key].add("dict")
                        extract_fields(value, full_key)
                    elif isinstance(value, list):
                        # Lista: aggiungi il campo e processa elementi
                        all_fields.add(full_key)
                        field_values[full_key].append(f"[list:{len(value)}]")
                        field_types[full_key].add("list")
                        for item in value:
                            extract_fields(item, full_key)
                    else:
                        # Valore semplice
                        all_fields.add(full_key)
                        field_values[full_key].append(value)
                        field_types[full_key].add(type(value).__name__)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_fields(item, f"{prefix}[{i}]" if prefix else f"[{i}]")

        for meta in metadatas:
            if not isinstance(meta, dict):
                continue
            extract_fields(meta)

        # Analizza ogni campo
        field_analysis = {}
        for field in sorted(all_fields):
            values = field_values[field]
            unique_values = set(v for v in values if v is not None)

            field_analysis[field] = {
                "count": len(values),
                "null_count": sum(1 for v in values if v is None),
                "unique_count": len(unique_values),
                "types": list(field_types[field]),
                "sample_values": list(unique_values)[:5],  # Primi 5 valori unici
            }

            # Se pochi valori unici, mostra tutti (escludendo dict/list)
            simple_values = [
                v for v in unique_values if not isinstance(v, (dict, list))
            ]
            if len(simple_values) <= 10 and simple_values:
                field_analysis[field]["all_values"] = simple_values[:10]

        return {
            "unique_fields": sorted(all_fields),
            "field_analysis": field_analysis,
            "total_fields": len(all_fields),
        }

    def _check_quality(self, documents: list[str], metadatas: list[dict]) -> list[dict]:
        """Verifica problemi di qualità"""
        issues = []

        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            # Chunk vuoti o troppo corti
            if not doc or len(doc.strip()) == 0:
                issues.append(
                    {
                        "type": "empty_chunk",
                        "index": i,
                        "collection": "unknown",
                    }
                )

            if doc and len(doc.strip()) < 10:
                issues.append(
                    {
                        "type": "too_short",
                        "index": i,
                        "length": len(doc),
                        "collection": "unknown",
                    }
                )

            # Metadata mancanti critici
            if isinstance(meta, dict):
                # Controlla campi comuni che dovrebbero esserci
                common_fields = ["book_title", "source", "collection", "tier", "law_id"]
                missing_fields = [
                    f
                    for f in common_fields
                    if f not in meta and f in ["book_title", "source"]
                ]
                if missing_fields:
                    issues.append(
                        {
                            "type": "missing_metadata",
                            "index": i,
                            "missing_fields": missing_fields,
                        }
                    )

        return issues

    def _analyze_chunks(self, documents: list[str]) -> dict[str, Any]:
        """Analizza statistiche sui chunk"""
        if not documents:
            return {}

        lengths = [len(doc) for doc in documents if doc]
        if not lengths:
            return {}

        return {
            "count": len(lengths),
            "avg_length": sum(lengths) / len(lengths),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "median_length": sorted(lengths)[len(lengths) // 2],
        }

    def analyze_all(self) -> dict[str, Any]:
        """Analizza tutte le collezioni"""
        print("\n🚀 Inizio analisi completa Qdrant")
        print(f"   URL: {self.qdrant_url}")
        print(f"   Collezioni da analizzare: {len(COLLECTIONS)}")

        total_docs = 0
        successful_collections = 0

        for collection_name in COLLECTIONS:
            result = self.analyze_collection(collection_name)
            self.results["collections"][collection_name] = result

            if "error" not in result and "empty" not in result:
                successful_collections += 1
                total_docs += result["stats"].get("total_documents", 0)

        # Summary globale
        self.results["summary"] = {
            "total_collections_analyzed": len(COLLECTIONS),
            "successful_collections": successful_collections,
            "total_documents": total_docs,
            "analysis_timestamp": datetime.now().isoformat(),
        }

        # Analisi metadata cross-collection
        print("\n🔍 Analisi metadata cross-collection...")
        self._analyze_cross_collection_metadata()

        return self.results

    def _analyze_cross_collection_metadata(self):
        """Analizza pattern metadata tra collezioni"""
        all_fields = set()
        field_frequency = Counter()

        for collection_name, result in self.results["collections"].items():
            if "metadata_analysis" in result:
                fields = result["metadata_analysis"].get("unique_fields", [])
                all_fields.update(fields)
                for field in fields:
                    field_frequency[field] += 1

        self.results["metadata_analysis"] = {
            "all_fields": sorted(all_fields),
            "field_frequency": dict(field_frequency.most_common()),
            "collections_count": len(self.results["collections"]),
        }

    def generate_reports(self, output_dir: Path = None):
        """Genera report JSON e Markdown"""
        if output_dir is None:
            output_dir = Path(__file__).parent / "qdrant_analysis_reports"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON Report
        json_path = output_dir / f"qdrant_analysis_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Report JSON salvato: {json_path}")

        # Markdown Report
        md_path = output_dir / f"qdrant_analysis_{timestamp}.md"
        self._generate_markdown_report(md_path)
        print(f"✅ Report Markdown salvato: {md_path}")

    def _generate_markdown_report(self, output_path: Path):
        """Genera report Markdown dettagliato"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Analisi Struttura Documenti Qdrant\n\n")
            f.write(f"**Data analisi**: {self.results['analysis_date']}\n\n")

            # Summary
            summary = self.results["summary"]
            f.write("## 📊 Riepilogo\n\n")
            f.write(
                f"- **Collezioni analizzate**: {summary['successful_collections']}/{summary['total_collections_analyzed']}\n"
            )
            f.write(f"- **Documenti totali**: {summary['total_documents']:,}\n\n")

            # Per ogni collezione
            f.write("## 📚 Collezioni\n\n")
            for collection_name, result in self.results["collections"].items():
                if "error" in result:
                    f.write(f"### {collection_name}\n\n")
                    f.write(f"❌ **Errore**: {result['error']}\n\n")
                    continue

                if "empty" in result:
                    f.write(f"### {collection_name}\n\n")
                    f.write("⚠️ **Collezione vuota**\n\n")
                    continue

                stats = result.get("stats", {})
                metadata = result.get("metadata_analysis", {})
                chunk_stats = result.get("chunk_stats", {})
                examples = result.get("examples", [])

                f.write(f"### {collection_name}\n\n")
                f.write(f"- **Documenti**: {stats.get('total_documents', 0):,}\n")
                f.write(f"- **Vector size**: {stats.get('vector_size', 'N/A')}\n")
                f.write(f"- **Distance**: {stats.get('distance', 'N/A')}\n")
                f.write(
                    f"- **Campi metadata**: {len(metadata.get('unique_fields', []))}\n"
                )
                f.write(
                    f"- **Lunghezza media chunk**: {chunk_stats.get('avg_length', 0):.0f} caratteri\n\n"
                )

                # Campi metadata
                if metadata.get("unique_fields"):
                    f.write("**Campi metadata**:\n")
                    for field in metadata["unique_fields"][:10]:  # Primi 10
                        f.write(f"- `{field}`\n")
                    if len(metadata["unique_fields"]) > 10:
                        f.write(
                            f"- ... e altri {len(metadata['unique_fields']) - 10} campi\n"
                        )
                    f.write("\n")

                # Esempi
                if examples:
                    f.write("**Esempi documenti**:\n\n")
                    for i, ex in enumerate(examples[:2], 1):  # Primi 2 esempi
                        f.write(f"#### Esempio {i}\n\n")
                        f.write(f"- **ID**: `{ex['id']}`\n")
                        f.write(f"- **Lunghezza**: {ex['text_length']} caratteri\n")
                        f.write(f"- **Preview**: {ex['text_preview']}\n\n")
                        f.write("**Metadata**:\n```json\n")
                        f.write(
                            json.dumps(ex["metadata"], indent=2, ensure_ascii=False)
                        )
                        f.write("\n```\n\n")

            # Metadata cross-collection
            if self.results.get("metadata_analysis"):
                f.write("## 🔍 Analisi Metadata Cross-Collection\n\n")
                meta_analysis = self.results["metadata_analysis"]
                f.write(
                    f"- **Campi totali unici**: {len(meta_analysis.get('all_fields', []))}\n\n"
                )
                f.write("**Campi più comuni**:\n\n")
                for field, count in list(
                    meta_analysis.get("field_frequency", {}).items()
                )[:15]:
                    f.write(f"- `{field}`: presente in {count} collezioni\n")
                f.write("\n")


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Qdrant Documents Structure Analyzer")
    print("=" * 80)

    analyzer = QdrantDocumentAnalyzer()
    results = analyzer.analyze_all()

    # Print final summary
    print("\n" + "=" * 80)
    print("📊 RIEPILOGO FINALE")
    print("=" * 80)
    summary = results["summary"]
    print(
        f"Collezioni analizzate: {summary['successful_collections']}/{summary['total_collections_analyzed']}"
    )
    print(f"Documenti totali: {summary['total_documents']:,}")

    # Generate reports
    analyzer.generate_reports()

    print("\n✅ Analisi completata!")


if __name__ == "__main__":
    main()
