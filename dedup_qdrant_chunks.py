#!/usr/bin/env python3
"""
Dedup Qdrant Chunks
Removes duplicate chunks by chunk_id, keeping only the first occurrence
"""
import asyncio
import sys
from collections import defaultdict

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def dedup_qdrant_by_chunk_id():
    """Remove duplicate chunks, keep first by scroll order"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("="*80)
        print("DEDUPLICAZIONE CHUNKS QDRANT")
        print("="*80)

        # Get HTTP client
        http_client = await client._get_client()

        # Scroll ALL chunks
        print("\n📊 Recuperando tutti i chunks...")
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

        print(f"✅ Recuperati {len(all_points)} chunks totali\n")

        # Group by metadata.chunk_id
        print("🔍 Analisi duplicati per chunk_id...")
        groups = defaultdict(list)
        no_chunk_id = []

        for point in all_points:
            payload = point.get('payload', {})
            metadata = payload.get('metadata', {})
            chunk_id = metadata.get('chunk_id')

            if chunk_id:
                groups[chunk_id].append(point['id'])
            else:
                no_chunk_id.append(point['id'])

        # Analizza duplicati
        duplicates = {cid: pids for cid, pids in groups.items() if len(pids) > 1}

        print(f"📊 STATISTICHE:")
        print(f"  Chunks unici: {len(groups)}")
        print(f"  Chunks con chunk_id: {len(all_points) - len(no_chunk_id)}")
        print(f"  Chunks SENZA chunk_id: {len(no_chunk_id)}")
        print(f"  Gruppi con DUPLICATI: {len(duplicates)}")

        if not duplicates:
            print("\n✅ Nessun duplicato trovato!")
            return

        # Mostra duplicati
        print(f"\n{'='*80}")
        print("DUPLICATI TROVATI:")
        print(f"{'='*80}")

        total_to_delete = 0
        for chunk_id, point_ids in sorted(duplicates.items()):
            print(f"\n🔄 {chunk_id}")
            print(f"   {len(point_ids)} occorrenze: {point_ids}")
            print(f"   → KEEP: {point_ids[0]}")
            print(f"   → DELETE: {point_ids[1:]}")
            total_to_delete += len(point_ids) - 1

        print(f"\n{'='*80}")
        print(f"⚠️  TOTALE DA ELIMINARE: {total_to_delete} chunks duplicati")
        print(f"{'='*80}")

        # Chiedi conferma
        response = input("\n❓ Procedere con l'eliminazione? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Operazione annullata")
            return

        # Delete duplicates
        print("\n🗑️  Eliminazione duplicati in corso...")
        to_delete = []
        for chunk_id, point_ids in duplicates.items():
            # Keep first, delete rest
            to_delete.extend(point_ids[1:])

        # Batch delete (Qdrant supports batch delete via points/delete)
        url = f"/collections/{client.collection_name}/points/delete"

        # Delete in batches of 100
        batch_size = 100
        deleted_count = 0

        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i+batch_size]
            payload = {"points": batch}

            response = await http_client.post(url, json=payload, params={"wait": "true"})
            response.raise_for_status()

            deleted_count += len(batch)
            print(f"  Eliminati {deleted_count}/{len(to_delete)} chunks...")

        print(f"\n✅ COMPLETATO!")
        print(f"   Eliminati: {deleted_count} chunks duplicati")
        print(f"   Rimanenti: {len(all_points) - deleted_count} chunks unici")

    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(dedup_qdrant_by_chunk_id())
