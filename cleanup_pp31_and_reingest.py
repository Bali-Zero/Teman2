#!/usr/bin/env python3
"""
Cleanup PP_31_2013 and Re-ingest with Deterministic UUIDs
"""
import asyncio
import sys
import httpx

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient


async def cleanup_and_reingest():
    """Delete all PP_31_2013 chunks and trigger re-ingestion"""

    client = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("=" * 80)
        print("CLEANUP PP_31_2013 E RE-INGESTION")
        print("=" * 80)

        # Step 1: Delete ALL PP_31_2013 chunks
        print("\n1️⃣ Eliminazione TUTTI i chunks PP_31_2013...")
        http_client = await client._get_client()

        # Scroll and collect all PP_31_2013 IDs
        all_pp31_ids = []
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

            # Filter only PP_31_2013
            for point in points:
                payload_data = point.get('payload', {})
                metadata = payload_data.get('metadata', {})
                doc_id = metadata.get('document_id')

                if doc_id == 'PP_31_2013':
                    all_pp31_ids.append(point['id'])

            next_offset = data.get("next_page_offset")
            if not next_offset:
                break
            offset = next_offset

        print(f"   Trovati {len(all_pp31_ids)} chunks PP_31_2013 da eliminare")

        # Delete in batches
        if all_pp31_ids:
            delete_url = f"/collections/{client.collection_name}/points/delete"
            batch_size = 100
            deleted = 0

            for i in range(0, len(all_pp31_ids), batch_size):
                batch = all_pp31_ids[i:i+batch_size]
                payload = {"points": batch}

                response = await http_client.post(delete_url, json=payload, params={"wait": "true"})
                response.raise_for_status()

                deleted += len(batch)
                print(f"   Eliminati {deleted}/{len(all_pp31_ids)} chunks...")

            print(f"\n✅ Eliminati {deleted} chunks PP_31_2013")
        else:
            print("\n✅ Nessun chunk PP_31_2013 trovato")

        # Step 2: Re-upload PDF with deterministic UUIDs
        print("\n2️⃣ Re-ingestion PP_31_2013 con UUID deterministici...")

        async with httpx.AsyncClient(timeout=180.0) as upload_client:
            pdf_path = "/Users/antonellosiano/desktop/nuzantara/apps/kb/data/imigrasi/PP_31_2013.pdf"

            with open(pdf_path, 'rb') as f:
                files = {'file': ('PP_31_2013.pdf', f, 'application/pdf')}

                response = await upload_client.post(
                    "https://nuzantara-rag.fly.dev/api/legal/ingest",
                    files=files,
                    timeout=180.0
                )

                response.raise_for_status()
                result = response.json()

                print(f"\n✅ Re-ingestion completata!")
                print(f"   Chunks creati: {result.get('chunks_created', 'N/A')}")
                print(f"   BAB: {result.get('structure', {}).get('bab_count', 'N/A')}")
                print(f"   Pasal: {result.get('structure', {}).get('pasal_count', 'N/A')}")

        print("\n" + "=" * 80)
        print("CLEANUP E RE-INGESTION COMPLETATI!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(cleanup_and_reingest())
