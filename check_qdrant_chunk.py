#!/usr/bin/env python3
"""
Verifica chunk in Qdrant per PP_31_2013
"""
import asyncio
import sys
sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient
import json


async def check_chunks():
    """Verifica chunks in Qdrant"""

    # Connetti a Qdrant
    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    print("=" * 80)
    print("VERIFICA QDRANT - Collection: legal_unified")
    print("=" * 80)

    # Stats collection
    try:
        stats = await client.get_collection_stats()
        print(f"\n📊 Stats Collection:")
        print(f"  Total documents: {stats.get('total_documents', 0)}")
    except Exception as e:
        print(f"❌ Errore stats: {e}")

    # Scroll TUTTI i chunks PP_31_2013 usando HTTP client direttamente
    print(f"\n🔍 Recuperando TUTTI i chunks PP_31_2013...")
    try:
        all_results = []
        offset = None

        # Get HTTP client
        http_client = await client._get_client()

        # Scroll in batches fino a ottenere tutti i 306 chunks
        while True:
            url = f"/collections/{client.collection_name}/points/scroll"
            payload = {"limit": 100, "with_payload": True, "with_vectors": False}
            if offset:
                payload["offset"] = offset

            response = await http_client.post(url, json=payload)
            response.raise_for_status()

            data = response.json().get("result", {})
            points = data.get("points", [])

            if not points:
                break

            all_results.extend(points)

            # Get next offset
            next_offset = data.get("next_page_offset")
            if not next_offset:
                break
            offset = next_offset

        print(f"\n✅ TOTALE CHUNKS: {len(all_results)}")
        print(f"\n{'='*80}")

        # Stampa TUTTI i chunks con dettagli completi
        for i, point in enumerate(all_results):
            print(f"\n{'='*80}")
            print(f"CHUNK #{i+1}/{len(all_results)}")
            print(f"{'='*80}")
            print(f"ID: {point.get('id', 'N/A')}")

            payload = point.get('payload', {})

            # Info documento
            print(f"\n📄 DOCUMENTO:")
            print(f"  book_title: {payload.get('book_title', 'N/A')}")
            print(f"  document_id: {payload.get('document_id', 'N/A')}")

            # Info gerarchia
            print(f"\n🌳 GERARCHIA:")
            print(f"  chapter_id: {payload.get('chapter_id', 'N/A')}")
            print(f"  bab_title: {payload.get('bab_title', 'N/A')}")
            print(f"  hierarchy_path: {payload.get('hierarchy_path', 'N/A')}")
            print(f"  parent_chunk_ids: {payload.get('parent_chunk_ids', [])}")

            # Info pasal
            print(f"\n📋 PASAL:")
            print(f"  pasal_number: {payload.get('pasal_number', 'N/A')}")
            print(f"  ayat_count: {payload.get('ayat_count', 'N/A')}")

            # Testo COMPLETO
            text = payload.get('text', '')
            print(f"\n📝 TEXT COMPLETO ({len(text)} chars):")
            print(f"{'='*80}")
            print(text)
            print(f"{'='*80}")

    except Exception as e:
        print(f"\n❌ Errore durante scroll: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_chunks())
