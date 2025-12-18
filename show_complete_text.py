#!/usr/bin/env python3
"""
Show COMPLETE TEXT from chunks
"""
import asyncio
import sys

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def show_complete_text():
    """Display complete text from chunks"""

    qdrant = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("=" * 100)
        print("PP_31_2013 - COMPLETE CHUNK TEXTS")
        print("=" * 100)

        http_client = await qdrant._get_client()

        # Get first 10 chunks
        url = f"/collections/{qdrant.collection_name}/points/scroll"
        payload = {
            "limit": 10,
            "with_payload": True,
            "with_vectors": False,
            "filter": {
                "must": [
                    {"key": "metadata.document_id", "match": {"value": "PP_31_2013"}}
                ]
            }
        }

        response = await http_client.post(url, json=payload)
        response.raise_for_status()

        data = response.json().get("result", {})
        points = data.get("points", [])

        for i, chunk in enumerate(points, 1):
            payload_data = chunk.get('payload', {})
            metadata = payload_data.get('metadata', {})
            text = payload_data.get('text', '')

            print(f"\n{'=' * 100}")
            print(f"CHUNK #{i} - Pasal {metadata.get('pasal_number', 'N/A')}")
            print(f"{'=' * 100}")
            print(f"UUID: {chunk['id']}")
            print(f"BAB: {metadata.get('bab_title', 'N/A')}")
            print(f"Hierarchy: {metadata.get('hierarchy_path', 'N/A')}")
            print(f"\n{'─' * 100}")
            print("TESTO COMPLETO:")
            print(f"{'─' * 100}")
            print(text)
            print(f"{'─' * 100}")
            print(f"Length: {len(text)} characters")
            print(f"Ayat count: {metadata.get('ayat_count', 0)}")
            print(f"Ayat numbers: {metadata.get('ayat_numbers', [])}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(show_complete_text())
