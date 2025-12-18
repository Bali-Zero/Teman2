#!/usr/bin/env python3
"""
Count unique chunk_ids vs total chunks for PP_31_2013
"""
import asyncio
import sys
from collections import defaultdict

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def count_unique_chunks():
    """Count unique vs duplicate chunks"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("=" * 80)
        print("CONTEGGIO CHUNK_ID UNIVOCI PER PP_31_2013")
        print("=" * 80)

        # Get HTTP client
        http_client = await client._get_client()

        # Scroll all chunks
        all_chunks = []
        offset = None

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

            all_chunks.extend(points)

            next_offset = data.get("next_page_offset")
            if not next_offset:
                break
            offset = next_offset

        print(f"\n📊 TOTALE CHUNKS: {len(all_chunks)}")

        # Count PP_31_2013 chunks
        pp_31_chunks = []
        chunk_id_to_uuids = defaultdict(list)

        for point in all_chunks:
            payload_data = point.get('payload', {})
            metadata = payload_data.get('metadata', {})

            doc_id = metadata.get('document_id')
            if doc_id == 'PP_31_2013':
                pp_31_chunks.append(point)
                chunk_id = metadata.get('chunk_id', 'NO_CHUNK_ID')
                uuid = point.get('id')
                chunk_id_to_uuids[chunk_id].append(uuid)

        print(f"\n📄 PP_31_2013 chunks: {len(pp_31_chunks)}")
        print(f"📝 chunk_id univoci: {len(chunk_id_to_uuids)}")

        # Find duplicates
        duplicates = {cid: uuids for cid, uuids in chunk_id_to_uuids.items() if len(uuids) > 1}

        if duplicates:
            print(f"\n⚠️  DUPLICATI TROVATI: {len(duplicates)} chunk_id con multiple UUID")
            print(f"\nPrimi 10 duplicati:")
            for i, (chunk_id, uuids) in enumerate(list(duplicates.items())[:10]):
                print(f"\n{i+1}. {chunk_id}")
                print(f"   Occorrenze: {len(uuids)}")
                for uuid in uuids[:5]:  # Show max 5 UUIDs
                    print(f"   → {uuid}")
        else:
            print(f"\n✅ NO DUPLICATI! Ogni chunk_id ha 1 solo UUID")
            print(f"   UUID deterministici funzionano!")

        # Check if old random UUIDs still exist
        sample_chunk_ids = list(chunk_id_to_uuids.keys())[:5]
        print(f"\n🔍 Sample UUID per chunk_id:")
        for cid in sample_chunk_ids:
            uuids = chunk_id_to_uuids[cid]
            print(f"\n{cid}:")
            for uuid in uuids:
                print(f"  → {uuid}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(count_unique_chunks())
