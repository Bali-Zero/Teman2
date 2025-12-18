#!/usr/bin/env python3
"""
ZANTARA - Apply Metadata Updates to Qdrant

Applica gli aggiornamenti metadata estratti dal testo ai documenti Qdrant.
Richiede conferma esplicita prima di procedere.
"""

import json
import os
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
        except Exception:
            return {"ids": [], "documents": [], "metadatas": []}

    def update_metadata(self, point_id: str, metadata: dict) -> bool:
        """Aggiorna metadata di un punto"""
        try:
            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/{point_id}/payload"
            # Qdrant expects payload update format
            payload = {"payload": {"metadata": metadata}}
            response = requests.put(url, json=payload, timeout=10)

            return response.status_code == 200
        except Exception as e:
            print(f"   ⚠️ Errore update metadata: {e}")
            return False

    def batch_update_metadata(self, updates: list[dict]) -> dict[str, Any]:
        """Aggiorna metadata in batch"""
        try:
            url = f"{self.qdrant_url}/collections/{self.collection_name}/points/payload"
            # Qdrant batch update format
            points = [
                {"id": u["id"], "payload": {"metadata": u["metadata"]}} for u in updates
            ]
            payload = {"points": points}
            response = requests.put(
                url, json=payload, params={"wait": "true"}, timeout=60
            )

            if response.status_code == 200:
                return {"success": True, "updated": len(updates)}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def load_extraction_results():
    """Carica risultati estrazione metadata"""
    reports_dir = Path(__file__).parent / "qdrant_analysis_reports"
    import glob

    extraction_files = sorted(
        glob.glob(str(reports_dir / "metadata_extraction_*.json")), reverse=True
    )
    if not extraction_files:
        print(
            "❌ Nessun file di estrazione trovato. Esegui prima extract_and_update_metadata.py"
        )
        return None

    with open(extraction_files[0], "r") as f:
        return json.load(f)


def apply_updates(collection_name: str, examples: list[dict], dry_run: bool = True):
    """Applica aggiornamenti metadata"""
    client = SimpleQdrantClient(QDRANT_URL, collection_name)

    updates = []
    for ex in examples:
        if ex.get("extracted_metadata"):
            updates.append(
                {
                    "id": ex["id"],
                    "metadata": ex["merged_metadata"],
                }
            )

    if not updates:
        print("   ⚠️ Nessun aggiornamento da applicare")
        return {"updated": 0}

    if dry_run:
        print(f"   🔍 DRY RUN: {len(updates)} aggiornamenti pronti (non applicati)")
        return {"updated": 0, "dry_run": True}

    # Batch update
    result = client.batch_update_metadata(updates)
    return result


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Apply Metadata Updates to Qdrant")
    print("=" * 80)

    # Carica risultati estrazione
    print("\n📥 Caricando risultati estrazione...")
    extraction_results = load_extraction_results()

    if not extraction_results:
        return

    print(f"✅ Caricati risultati da {extraction_results['extraction_date']}")

    # Chiedi conferma
    print("\n" + "=" * 80)
    print("⚠️  ATTENZIONE: Questo script modificherà i documenti in Qdrant!")
    print("=" * 80)
    print("\nCollezioni da aggiornare:")
    for coll_name, coll_data in extraction_results["collections"].items():
        if "error" not in coll_data:
            print(
                f"  - {coll_name}: {coll_data.get('extracted_count', 0)} metadata estratti"
            )

    response = input(
        "\nVuoi procedere con l'aggiornamento? (scrivi 'APPLICA' per confermare): "
    )
    if response != "APPLICA":
        print("\n❌ Operazione annullata.")
        return

    # Dry run first
    print("\n🔍 Eseguendo DRY RUN...")
    dry_run_results = {}
    for coll_name, coll_data in extraction_results["collections"].items():
        if "error" not in coll_data and coll_data.get("examples"):
            print(f"\n📊 {coll_name}:")
            result = apply_updates(coll_name, coll_data["examples"], dry_run=True)
            dry_run_results[coll_name] = result

    # Chiedi conferma finale
    print("\n" + "=" * 80)
    response2 = input(
        "Confermi l'applicazione degli aggiornamenti? (scrivi 'CONFERMA'): "
    )
    if response2 != "CONFERMA":
        print("\n❌ Operazione annullata.")
        return

    # Applica aggiornamenti
    print("\n🚀 Applicando aggiornamenti...")
    results = {}
    for coll_name, coll_data in extraction_results["collections"].items():
        if "error" not in coll_data and coll_data.get("examples"):
            print(f"\n📊 {coll_name}:")
            result = apply_updates(coll_name, coll_data["examples"], dry_run=False)
            results[coll_name] = result
            if result.get("success"):
                print(f"   ✅ Aggiornati {result.get('updated', 0)} documenti")
            else:
                print(f"   ❌ Errore: {result.get('error')}")

    # Summary
    total_updated = sum(r.get("updated", 0) for r in results.values())
    print(f"\n{'=' * 80}")
    print("📊 RIEPILOGO")
    print(f"{'=' * 80}")
    print(f"Documenti aggiornati: {total_updated}")
    print("\n✅ Aggiornamento completato!")


if __name__ == "__main__":
    main()
