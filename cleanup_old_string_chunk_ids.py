#!/usr/bin/env python3
"""
Delete OLD chunks that have STRING chunk_ids in metadata.
Keep NEW chunks that have UUID chunk_ids (UUID5 deterministic).
"""
import asyncio
import sys
import re

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


def is_uuid(value: str) -> bool:
    """Check if string is a valid UUID format"""
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(uuid_pattern, str(value).lower()))


async def cleanup_old_chunks():
    """Delete old chunks with STRING chunk_ids, keep UUID5 chunks"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("=" * 80)
        print("CLEANUP OLD CHUNKS (STRING chunk_ids)")
        print("=" * 80)

        http_client = await client._get_client()

        # Scroll all chunks
        print("\n📊 Scanning all chunks...")
        all_points = []
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

            all_points.extend(points)

            next_offset = data.get("next_page_offset")
            if not next_offset:
                break
            offset = next_offset

        print(f"✅ Found {len(all_points)} total chunks\n")

        # Separate old (STRING chunk_id) vs new (UUID chunk_id)
        old_chunks = []
        new_chunks = []
        no_chunk_id = []

        for point in all_points:
            payload_data = point.get('payload', {})
            metadata = payload_data.get('metadata', {})
            chunk_id = metadata.get('chunk_id')

            if not chunk_id:
                no_chunk_id.append(point['id'])
            elif is_uuid(chunk_id):
                new_chunks.append(point['id'])
            else:
                old_chunks.append(point['id'])

        print("📊 STATISTICS:")
        print(f"  OLD chunks (STRING chunk_id): {len(old_chunks)}")
        print(f"  NEW chunks (UUID chunk_id): {len(new_chunks)}")
        print(f"  No chunk_id: {len(no_chunk_id)}")

        if not old_chunks:
            print("\n✅ No old chunks to clean up!")
            return

        print(f"\n⚠️  WILL DELETE {len(old_chunks)} old chunks with STRING chunk_ids")
        print("   (Keeping new chunks with UUID5 deterministic IDs)")

        response = input("\n❓ Proceed with deletion? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            return

        # Delete old chunks
        print(f"\n🗑️  Deleting {len(old_chunks)} old chunks...")
        url = f"/collections/{client.collection_name}/points/delete"

        batch_size = 100
        deleted = 0

        for i in range(0, len(old_chunks), batch_size):
            batch = old_chunks[i:i+batch_size]
            payload = {"points": batch}

            response = await http_client.post(url, json=payload, params={"wait": "true"})
            response.raise_for_status()

            deleted += len(batch)
            print(f"  Deleted {deleted}/{len(old_chunks)} chunks...")

        print(f"\n✅ COMPLETED!")
        print(f"   Deleted: {deleted} old chunks (STRING chunk_ids)")
        print(f"   Remaining: {len(new_chunks)} new chunks (UUID5 deterministic)")
        print(f"\n🎉 All future ingestions will use UUID5 deterministic IDs!")
        print(f"   No more duplicates!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(cleanup_old_chunks())
