#!/usr/bin/env python3
"""
Check RAW payload structure from Qdrant
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def check_raw_payload():
    """Check raw payload structure"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        # Get HTTP client
        http_client = await client._get_client()

        # Scroll first chunk
        url = f"/collections/{client.collection_name}/points/scroll"
        payload = {"limit": 3, "with_payload": True, "with_vectors": False}

        response = await http_client.post(url, json=payload)
        response.raise_for_status()

        data = response.json().get("result", {})
        points = data.get("points", [])

        print("="*80)
        print(f"TROVATI {len(points)} CHUNKS - MOSTRA PAYLOAD RAW JSON")
        print("="*80)

        for i, point in enumerate(points):
            print(f"\n{'='*80}")
            print(f"CHUNK #{i+1}")
            print(f"{'='*80}")
            print(json.dumps(point, indent=2, ensure_ascii=False))

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_raw_payload())
