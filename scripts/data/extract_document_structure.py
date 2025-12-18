#!/usr/bin/env python3
"""
ZANTARA - Extract Document Structure from Text Content

Analizza il contenuto testuale dei documenti per estrarre struttura dati
dalle collezioni che hanno metadata vuoti ma dati strutturati nel testo.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")


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
        except Exception as e:
            print(f"   ⚠️ Errore peek: {e}")
            return {"ids": [], "documents": [], "metadatas": []}


class DocumentStructureExtractor:
    """Estrae struttura dati dai documenti testuali"""

    def __init__(self):
        self.patterns = {
            "json": re.compile(r"\{[^{}]*\}", re.DOTALL),
            "markdown_headers": re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),
            "markdown_lists": re.compile(r"^[-*+]\s+(.+)$", re.MULTILINE),
            "visa_types": re.compile(r"\b([A-Z]\d+)\s+VISA\b", re.IGNORECASE),
            "kbli_codes": re.compile(r"\b(\d{5})\b"),
            "prices": re.compile(
                r"\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*(?:USD|IDR|Rp)?",
                re.IGNORECASE,
            ),
            "dates": re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"),
            "urls": re.compile(r"https?://[^\s]+"),
            "emails": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            ),
        }

    def analyze_collection(
        self, collection_name: str, documents: list[str]
    ) -> dict[str, Any]:
        """Analizza struttura di una collezione"""
        print(f"\n🔍 Analizzando struttura: {collection_name}")

        structure = {
            "collection": collection_name,
            "total_docs": len(documents),
            "patterns_found": {},
            "content_types": Counter(),
            "avg_length": sum(len(d) for d in documents) / len(documents)
            if documents
            else 0,
        }

        # Analizza pattern per ogni documento
        for doc in documents[:50]:  # Analizza primi 50 per performance
            doc_structure = self._analyze_document(doc)
            for pattern_type, found in doc_structure.items():
                if found:
                    structure["patterns_found"][pattern_type] = (
                        structure["patterns_found"].get(pattern_type, 0) + 1
                    )

            # Determina tipo contenuto
            content_type = self._classify_content_type(doc)
            structure["content_types"][content_type] += 1

        return structure

    def _analyze_document(self, text: str) -> dict[str, bool]:
        """Analizza un singolo documento per pattern"""
        results = {}

        # JSON structures
        json_matches = self.patterns["json"].findall(text)
        results["contains_json"] = len(json_matches) > 0

        # Markdown structures
        headers = self.patterns["markdown_headers"].findall(text)
        lists = self.patterns["markdown_lists"].findall(text)
        results["contains_markdown"] = len(headers) > 0 or len(lists) > 0
        results["markdown_headers_count"] = len(headers)
        results["markdown_lists_count"] = len(lists)

        # Domain-specific patterns
        results["contains_visa_types"] = (
            len(self.patterns["visa_types"].findall(text)) > 0
        )
        results["contains_kbli_codes"] = (
            len(self.patterns["kbli_codes"].findall(text)) > 0
        )
        results["contains_prices"] = len(self.patterns["prices"].findall(text)) > 0
        results["contains_dates"] = len(self.patterns["dates"].findall(text)) > 0
        results["contains_urls"] = len(self.patterns["urls"].findall(text)) > 0
        results["contains_emails"] = len(self.patterns["emails"].findall(text)) > 0

        return results

    def _classify_content_type(self, text: str) -> str:
        """Classifica il tipo di contenuto"""
        text_lower = text.lower()

        if "visa" in text_lower or "kitas" in text_lower or "permit" in text_lower:
            return "visa_immigration"
        elif (
            "kbli" in text_lower or "business" in text_lower or "company" in text_lower
        ):
            return "business_codes"
        elif "tax" in text_lower or "pajak" in text_lower or "npwp" in text_lower:
            return "tax_regulations"
        elif (
            "law" in text_lower or "undang" in text_lower or "regulation" in text_lower
        ):
            return "legal_text"
        elif "property" in text_lower or "real estate" in text_lower:
            return "property"
        elif "price" in text_lower or "cost" in text_lower or "fee" in text_lower:
            return "pricing"
        else:
            return "general"

    def extract_structured_data(
        self, collection_name: str, documents: list[str]
    ) -> list[dict]:
        """Estrae dati strutturati dai documenti"""
        structured = []

        for i, doc in enumerate(documents[:20]):  # Primi 20 per esempio
            extracted = {
                "index": i,
                "collection": collection_name,
                "length": len(doc),
                "extracted_fields": {},
            }

            # Estrai JSON se presente
            json_matches = self.patterns["json"].findall(doc)
            if json_matches:
                try:
                    parsed = json.loads(json_matches[0])
                    extracted["extracted_fields"]["json_data"] = parsed
                except:
                    pass

            # Estrai visa types
            visa_types = self.patterns["visa_types"].findall(doc)
            if visa_types:
                extracted["extracted_fields"]["visa_types"] = list(set(visa_types))

            # Estrai KBLI codes
            kbli_codes = self.patterns["kbli_codes"].findall(doc)
            if kbli_codes:
                extracted["extracted_fields"]["kbli_codes"] = list(
                    set(kbli_codes[:10])
                )  # Max 10

            # Estrai prezzi
            prices = self.patterns["prices"].findall(doc)
            if prices:
                extracted["extracted_fields"]["prices"] = prices[:5]  # Max 5

            # Estrai date
            dates = self.patterns["dates"].findall(doc)
            if dates:
                extracted["extracted_fields"]["dates"] = list(set(dates[:5]))

            if extracted["extracted_fields"]:
                structured.append(extracted)

        return structured


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Document Structure Extractor")
    print("=" * 80)

    collections_to_analyze = [
        "visa_oracle",
        "kbli_unified",
        "tax_genius",
        "legal_unified",
        "bali_zero_pricing",
    ]

    extractor = DocumentStructureExtractor()
    results = {
        "analysis_date": datetime.now().isoformat(),
        "collections": {},
        "structured_data_samples": {},
    }

    for collection_name in collections_to_analyze:
        print(f"\n{'=' * 80}")
        print(f"📊 Collezione: {collection_name}")
        print(f"{'=' * 80}")

        try:
            client = SimpleQdrantClient(QDRANT_URL, collection_name)
            sample = client.peek(limit=100)

            if not sample.get("documents"):
                print("   ⚠️ Nessun documento estratto")
                continue

            # Analizza struttura
            structure = extractor.analyze_collection(
                collection_name, sample["documents"]
            )
            results["collections"][collection_name] = structure

            # Estrai dati strutturati
            structured = extractor.extract_structured_data(
                collection_name, sample["documents"]
            )
            results["structured_data_samples"][collection_name] = structured[
                :5
            ]  # Primi 5 esempi

            # Print summary
            print("\n📈 Riepilogo:")
            print(f"   Documenti analizzati: {structure['total_docs']}")
            print(f"   Lunghezza media: {structure['avg_length']:.0f} caratteri")
            print("   Pattern trovati:")
            for pattern, count in structure["patterns_found"].items():
                if count > 0:
                    print(f"     - {pattern}: {count} documenti")
            print("   Tipi contenuto:")
            for content_type, count in structure["content_types"].most_common(3):
                print(f"     - {content_type}: {count} documenti")

        except Exception as e:
            print(f"   ❌ Errore: {e}")
            results["collections"][collection_name] = {"error": str(e)}

    # Salva risultati
    output_dir = Path(__file__).parent / "qdrant_analysis_reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"document_structure_{timestamp}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Risultati salvati: {json_path}")
    print("\n✅ Analisi completata!")


if __name__ == "__main__":
    main()
