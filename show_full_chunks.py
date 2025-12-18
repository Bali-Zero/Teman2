#!/usr/bin/env python3
"""
Show FULL chunks with complete metadata and text
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def show_full_chunks():
    """Show full chunks with metadata"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        # Get HTTP client
        http_client = await client._get_client()

        # Scroll chunks
        url = f"/collections/{client.collection_name}/points/scroll"
        payload = {"limit": 10, "with_payload": True, "with_vectors": False}

        response = await http_client.post(url, json=payload)
        response.raise_for_status()

        data = response.json().get("result", {})
        points = data.get("points", [])

        print("="*80)
        print(f"SHOWING {len(points)} FULL CHUNKS")
        print("="*80)

        for i, point in enumerate(points):
            payload_data = point.get('payload', {})
            metadata = payload_data.get('metadata', {})
            text = payload_data.get('text', '')

            # Skip chunks with no real text
            if len(text) < 100:
                continue

            print(f"\n{'='*80}")
            print(f"CHUNK #{i+1} - COMPLETO CON METADATI E TESTO")
            print(f"{'='*80}")

            print(f"\n🆔 CHUNK ID: {point.get('id')}")

            print(f"\n📄 DOCUMENTO:")
            print(f"  document_id: {metadata.get('document_id', 'N/A')}")
            print(f"  book_title: {metadata.get('book_title', 'N/A')[:80]}...")
            print(f"  legal_type: {metadata.get('legal_type', 'N/A')}")
            print(f"  legal_number: {metadata.get('legal_number', 'N/A')}")
            print(f"  legal_year: {metadata.get('legal_year', 'N/A')}")

            print(f"\n🌳 GERARCHIA:")
            print(f"  chapter_id: {metadata.get('chapter_id', 'N/A')}")
            print(f"  bab_title: {metadata.get('bab_title', 'N/A')}")
            print(f"  hierarchy_path: {metadata.get('hierarchy_path', 'N/A')}")
            print(f"  hierarchy_level: {metadata.get('hierarchy_level', 'N/A')}")
            print(f"  parent_chunk_ids: {metadata.get('parent_chunk_ids', [])}")

            print(f"\n📋 PASAL:")
            print(f"  pasal_number: {metadata.get('pasal_number', 'N/A')}")
            print(f"  ayat_count: {metadata.get('ayat_count', 'N/A')}")
            print(f"  chunk_id: {metadata.get('chunk_id', 'N/A')}")

            print(f"\n📝 TEXT COMPLETO ({len(text)} caratteri):")
            print(f"{'='*80}")
            print(text)
            print(f"{'='*80}")

            print(f"\n🔑 PARENT_CHUNK_IDS (link a PostgreSQL):")
            for parent_id in metadata.get('parent_chunk_ids', []):
                print(f"  → {parent_id}")

            print(f"\n" + "="*80)
            print()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(show_full_chunks())
