#!/usr/bin/env python3
"""
ZANTARA - Extract and Update Metadata from Text

Estrae metadata strutturati dal testo dei documenti e aggiorna Qdrant
secondo lo schema standardizzato.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev").rstrip("/")

# Load schema
SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "qdrant_metadata_schema.json"
with open(SCHEMA_PATH, "r") as f:
    METADATA_SCHEMAS = json.load(f)


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

    def update_metadata(self, point_id: str, metadata: dict) -> bool:
        """Aggiorna metadata di un punto"""
        try:
            # Qdrant API: Set payload for points
            # Convert point_id to integer (Qdrant requires integer or UUID)
            try:
                point_id_int = int(point_id)
            except ValueError:
                # If not integer, try as UUID string
                point_id_int = point_id

            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/payload"
            payload = {
                "points": [point_id_int],
                "payload": metadata,  # Qdrant payload è direttamente il dict, non nested
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                return True
            else:
                # Log error for debugging
                error_msg = (
                    response.text[:200]
                    if hasattr(response, "text")
                    else str(response.status_code)
                )
                if response.status_code != 200:
                    print(
                        f"   ⚠️ Update failed (HTTP {response.status_code}): {error_msg}"
                    )
                return False
        except Exception as e:
            print(f"   ⚠️ Errore update metadata: {e}")
            return False


class MetadataExtractor:
    """Estrae metadata strutturati dal testo"""

    def __init__(self):
        self.patterns = {
            "visa_type": re.compile(r"\b([A-Z]\d+)\s+VISA\b", re.IGNORECASE),
            "visa_category": re.compile(
                r"(tourist|business|work|transit|diplomatic)", re.IGNORECASE
            ),
            "entry_type": re.compile(r"(single|multiple)\s+entry", re.IGNORECASE),
            "duration": re.compile(
                r"(\d+)\s*(days?|weeks?|months?|years?)", re.IGNORECASE
            ),
            "fee_usd": re.compile(
                r"\$\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)|USD\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)",
                re.IGNORECASE,
            ),
            "fee_idr": re.compile(
                r"(?:IDR|Rp)\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{3})*)", re.IGNORECASE
            ),
            "kbli_code": re.compile(r"\b(\d{5})\b"),
            "investment_minimum": re.compile(
                r"investment.*?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{3})*)\s*(?:IDR|Rp)",
                re.IGNORECASE,
            ),
            "risk_level": re.compile(
                r"risk\s+level.*?(low|medium|high|mt|lt)", re.IGNORECASE
            ),
            "tax_rate": re.compile(r"(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE),
            "law_id": re.compile(
                r"(?:UU|PERMEN|PERDA|KEPMEN)\s*(?:No\.?)?\s*(\d+)[/\s](\d{4})",
                re.IGNORECASE,
            ),
            "pasal": re.compile(r"pasal\s+(\d+[A-Z]?)", re.IGNORECASE),
            "status_vigensi": re.compile(r"(berlaku|dicabut|diubah)", re.IGNORECASE),
            "date": re.compile(r"(\d{4}-\d{2}-\d{2})"),
            "json": re.compile(r"\{[^{}]*\}", re.DOTALL),
        }

    def extract_visa_metadata(self, text: str) -> dict[str, Any]:
        """Estrae metadata per visa_oracle"""
        metadata = {}

        # Visa type
        visa_match = self.patterns["visa_type"].search(text)
        if visa_match:
            metadata["visa_type"] = visa_match.group(1)

        # Category
        category_match = self.patterns["visa_category"].search(text)
        if category_match:
            metadata["visa_category"] = category_match.group(1).lower()

        # Entry type
        entry_match = self.patterns["entry_type"].search(text)
        if entry_match:
            metadata["entry_type"] = entry_match.group(1).lower()

        # Duration
        duration_match = self.patterns["duration"].search(text)
        if duration_match:
            metadata[
                "duration"
            ] = f"{duration_match.group(1)} {duration_match.group(2)}"

        # Fee USD
        fee_usd_match = self.patterns["fee_usd"].search(text)
        if fee_usd_match:
            fee = fee_usd_match.group(1) or fee_usd_match.group(2)
            try:
                metadata["fee_usd"] = float(fee.replace(",", ""))
            except Exception:
                pass

        # Fee IDR
        fee_idr_match = self.patterns["fee_idr"].search(text)
        if fee_idr_match:
            try:
                metadata["fee_idr"] = float(
                    fee_idr_match.group(1).replace(",", "").replace(".", "")
                )
            except Exception:
                pass

        # Try to extract JSON if present
        json_match = self.patterns["json"].search(text)
        if json_match:
            try:
                json_data = json.loads(json_match.group(0))
                # Extract common fields from JSON
                if "visa_type" in json_data:
                    metadata["visa_type"] = json_data["visa_type"]
                if "category" in json_data:
                    metadata["visa_category"] = json_data["category"]
                if "fee" in json_data:
                    metadata["fee_usd"] = json_data["fee"]
            except Exception:
                pass

        # Date
        date_match = self.patterns["date"].search(text)
        if date_match:
            metadata["last_updated"] = date_match.group(1)

        return metadata

    def extract_kbli_metadata(self, text: str) -> dict[str, Any]:
        """Estrae metadata per kbli_unified"""
        metadata = {}

        # KBLI code
        kbli_match = self.patterns["kbli_code"].search(text)
        if kbli_match:
            metadata["kbli_code"] = kbli_match.group(1)

        # Description (first sentence or markdown header)
        desc_match = re.search(
            r"^#{1,3}\s+(.+)$|^(.+?)(?:\.|$)", text[:200], re.MULTILINE
        )
        if desc_match:
            metadata["kbli_description"] = (desc_match.group(1) or desc_match.group(2))[
                :200
            ]

        # Investment minimum
        inv_match = self.patterns["investment_minimum"].search(text)
        if inv_match:
            try:
                inv_str = inv_match.group(1).replace(",", "").replace(".", "")
                metadata["investment_minimum"] = float(inv_str)
            except Exception:
                pass

        # Risk level
        risk_match = self.patterns["risk_level"].search(text)
        if risk_match:
            metadata["risk_level"] = risk_match.group(1).upper()

        # Required licenses (from markdown lists)
        licenses = re.findall(
            r"^[-*+]\s+(.+license.+)$", text, re.MULTILINE | re.IGNORECASE
        )
        if licenses:
            metadata["required_licenses"] = [lic.strip() for lic in licenses[:5]]

        return metadata

    def extract_tax_metadata(self, text: str) -> dict[str, Any]:
        """Estrae metadata per tax_genius"""
        metadata = {}

        # Tax type (from headers or first line)
        tax_type_patterns = [
            r"^(?:###\s+)?(.+tax.+?)(?:\s|$)",
            r"(?:NPWP|PPh|PPN|PBB)\s*(.+?)",
            r"Tax\s+Type[:\s]+(.+?)(?:\n|$)",
            r"(.+?)\s+Tax",
        ]
        for pattern in tax_type_patterns:
            tax_type_match = re.search(
                pattern, text[:200], re.IGNORECASE | re.MULTILINE
            )
            if tax_type_match:
                tax_type = tax_type_match.group(1).strip()
                if len(tax_type) < 50:  # Avoid too long matches
                    metadata["tax_type"] = tax_type
                    break

        # Tax rate (multiple patterns)
        rate_patterns = [
            r"(\d+(?:[.,]\d+)?)\s*%",
            r"rate[:\s]+(\d+(?:[.,]\d+)?)",
            r"(\d+(?:[.,]\d+)?)\s*percent",
        ]
        for pattern in rate_patterns:
            rate_match = re.search(pattern, text, re.IGNORECASE)
            if rate_match:
                try:
                    metadata["tax_rate"] = float(rate_match.group(1).replace(",", "."))
                    break
                except Exception:
                    pass

        # Try to extract JSON
        json_match = self.patterns["json"].search(text)
        if json_match:
            try:
                json_data = json.loads(json_match.group(0))
                if "tax_type" in json_data:
                    metadata["tax_type"] = json_data["tax_type"]
                if "rate" in json_data:
                    metadata["tax_rate"] = json_data["rate"]
                if "regulation" in json_data:
                    metadata["regulation_reference"] = json_data["regulation"]
            except Exception:
                pass

        # Date
        date_match = self.patterns["date"].search(text)
        if date_match:
            metadata["effective_date"] = date_match.group(1)

        # Source
        if "source_document" not in metadata:
            metadata["source_document"] = "tax_genius"

        return metadata

    def extract_legal_metadata(self, text: str) -> dict[str, Any]:
        """Estrae metadata per legal_unified"""
        metadata = {}

        # Law ID
        law_match = self.patterns["law_id"].search(text)
        if law_match:
            metadata["law_id"] = f"{law_match.group(1)}/{law_match.group(2)}"

        # Pasal
        pasal_match = self.patterns["pasal"].search(text)
        if pasal_match:
            metadata["pasal"] = pasal_match.group(1)

        # Status vigensi
        status_match = self.patterns["status_vigensi"].search(text)
        if status_match:
            metadata["status_vigensi"] = status_match.group(1).lower()

        # Year
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        if year_match:
            try:
                metadata["year"] = int(year_match.group(0))
            except Exception:
                pass

        # Title (from markdown header)
        title_match = re.search(r"^#{1,3}\s+(.+)$", text[:200], re.MULTILINE)
        if title_match:
            metadata["law_title"] = title_match.group(1).strip()[:200]

        return metadata

    def extract_pricing_metadata(self, text: str) -> dict[str, Any]:
        """Estrae metadata per bali_zero_pricing"""
        metadata = {}

        # Service name (from visa type or first line)
        visa_match = self.patterns["visa_type"].search(text)
        if visa_match:
            metadata["service_name"] = f"{visa_match.group(1)} VISA"
            metadata["service_type"] = "visa"
        else:
            # Try to find service name from various patterns
            service_patterns = [
                r"^(\d+\.\s*[A-Z]\d+\s+VISA)",
                r"^(\d+\.\s*.+?VISA)",
                r"Description:\s*(.+?VISA)",
                r"^(.+?)(?:\s+VISA|\s+Service|Description)",
            ]
            for pattern in service_patterns:
                service_match = re.search(
                    pattern, text[:200], re.IGNORECASE | re.MULTILINE
                )
                if service_match:
                    metadata["service_name"] = service_match.group(1).strip()
                    if "visa" in metadata["service_name"].lower():
                        metadata["service_type"] = "visa"
                    break

        # Price USD
        fee_usd_match = self.patterns["fee_usd"].search(text)
        if fee_usd_match:
            fee = fee_usd_match.group(1) or fee_usd_match.group(2)
            try:
                metadata["price_usd"] = float(fee.replace(",", ""))
                metadata["currency"] = "USD"
            except Exception:
                pass

        # Price IDR
        fee_idr_match = self.patterns["fee_idr"].search(text)
        if fee_idr_match:
            try:
                metadata["price_idr"] = float(
                    fee_idr_match.group(1).replace(",", "").replace(".", "")
                )
                metadata["currency"] = "IDR"
            except Exception:
                pass

        # Source
        if "source" not in metadata:
            metadata["source"] = "bali_zero_pricing"

        return metadata

    def extract_metadata(self, collection_name: str, text: str) -> dict[str, Any]:
        """Estrae metadata in base alla collezione"""
        extractors = {
            "visa_oracle": self.extract_visa_metadata,
            "kbli_unified": self.extract_kbli_metadata,
            "tax_genius": self.extract_tax_metadata,
            "legal_unified": self.extract_legal_metadata,
            "bali_zero_pricing": self.extract_pricing_metadata,
        }

        extractor = extractors.get(collection_name)
        if extractor:
            return extractor(text)
        return {}


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Extract and Update Metadata from Text")
    print("=" * 80)

    collections_to_process = [
        "visa_oracle",
        "kbli_unified",
        "tax_genius",
        "legal_unified",
        "bali_zero_pricing",
    ]

    extractor = MetadataExtractor()
    results = {
        "extraction_date": datetime.now().isoformat(),
        "collections": {},
    }

    for collection_name in collections_to_process:
        print(f"\n{'=' * 80}")
        print(f"📊 Processando: {collection_name}")
        print(f"{'=' * 80}")

        try:
            client = SimpleQdrantClient(QDRANT_URL, collection_name)
            # Processa tutti i documenti disponibili (o almeno 1000 per collezione)
            sample = client.peek(limit=1000)  # Processa fino a 1000 documenti

            if not sample.get("documents"):
                print("   ⚠️ Nessun documento estratto")
                continue

            extracted_count = 0
            updated_count = 0
            examples = []

            for i, (doc_id, doc_text, old_meta) in enumerate(
                zip(sample["ids"], sample["documents"], sample["metadatas"])
            ):
                # Estrai metadata
                new_metadata = extractor.extract_metadata(collection_name, doc_text)

                if new_metadata:
                    extracted_count += 1

                    # Merge con metadata esistenti (non sovrascrivere se già presenti)
                    merged_metadata = (
                        old_meta.copy() if isinstance(old_meta, dict) else {}
                    )
                    merged_metadata.update(new_metadata)

                    # Salva esempio
                    if len(examples) < 3:
                        examples.append(
                            {
                                "id": doc_id,
                                "old_metadata": old_meta,
                                "extracted_metadata": new_metadata,
                                "merged_metadata": merged_metadata,
                            }
                        )

                    # Update Qdrant
                    # NOTA: Decommentare per applicare gli aggiornamenti
                    # ATTENZIONE: Questo modificherà i documenti in produzione!
                    update_enabled = (
                        os.getenv("ENABLE_QDRANT_UPDATE", "false").lower() == "true"
                    )
                    if update_enabled and client.update_metadata(
                        doc_id, merged_metadata
                    ):
                        updated_count += 1

            results["collections"][collection_name] = {
                "total_processed": len(sample["documents"]),
                "extracted_count": extracted_count,
                "updated_count": updated_count,
                "examples": examples,
            }

            print("\n✅ Risultati:")
            print(f"   Documenti processati: {len(sample['documents'])}")
            print(f"   Metadata estratti: {extracted_count}")
            update_status = (
                "✅ AGGIORNATI" if update_enabled else "⚠️ DISABILITATO (test mode)"
            )
            print(f"   Documenti aggiornati: {updated_count} ({update_status})")

        except Exception as e:
            print(f"   ❌ Errore: {e}")
            results["collections"][collection_name] = {"error": str(e)}

    # Salva risultati
    output_dir = Path(__file__).parent / "qdrant_analysis_reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"metadata_extraction_{timestamp}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print("📊 RIEPILOGO")
    print(f"{'=' * 80}")
    total_extracted = sum(
        c.get("extracted_count", 0) for c in results["collections"].values()
    )
    print(f"Metadata estratti totali: {total_extracted}")
    print(f"\n✅ Report salvato: {json_path}")
    print("\n⚠️ NOTA: Update Qdrant DISABILITATO per sicurezza.")
    print(
        "   Per applicare gli aggiornamenti, decommentare le righe di update nel codice."
    )


if __name__ == "__main__":
    main()
