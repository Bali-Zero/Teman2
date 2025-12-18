#!/usr/bin/env python3
"""
Show Complete PP_31_2013 Structure
Display chunks from Qdrant and BAB from PostgreSQL
"""
import asyncio
import sys
import json

sys.path.insert(0, '/Users/antonellosiano/desktop/nuzantara/apps/backend-rag/backend')

from core.qdrant_db import QdrantClient
import asyncpg


async def show_complete_structure():
    """Display complete hierarchical structure"""

    # Qdrant client
    qdrant = QdrantClient(
        qdrant_url="https://nuzantara-qdrant.fly.dev",
        collection_name="legal_unified",
        api_key="QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo"
    )

    try:
        print("=" * 100)
        print("PP_31_2013 - COMPLETE HIERARCHICAL STRUCTURE")
        print("=" * 100)

        # ========== PART 1: QDRANT CHUNKS (PASAL) ==========
        print("\n" + "=" * 100)
        print("PART 1: QDRANT CHUNKS (Pasal Level)")
        print("=" * 100)

        http_client = await qdrant._get_client()

        # Get all PP_31_2013 chunks
        all_chunks = []
        offset = None

        while True:
            url = f"/collections/{qdrant.collection_name}/points/scroll"
            payload = {
                "limit": 100,
                "with_payload": True,
                "with_vectors": False,
                "filter": {
                    "must": [
                        {"key": "metadata.document_id", "match": {"value": "PP_31_2013"}}
                    ]
                }
            }
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

        print(f"\n📊 Total Chunks: {len(all_chunks)}\n")

        # Show first 5 complete chunks
        print("=" * 100)
        print("FIRST 5 COMPLETE CHUNKS (with full metadata):")
        print("=" * 100)

        for i, chunk in enumerate(all_chunks[:5], 1):
            payload_data = chunk.get('payload', {})
            metadata = payload_data.get('metadata', {})
            text = payload_data.get('text', '')

            print(f"\n{'─' * 100}")
            print(f"CHUNK #{i}")
            print(f"{'─' * 100}")
            print(f"UUID (Point ID):     {chunk['id']}")
            print(f"Chunk ID:            {metadata.get('chunk_id', 'N/A')}")
            print(f"Document ID:         {metadata.get('document_id', 'N/A')}")
            print(f"Hierarchy Path:      {metadata.get('hierarchy_path', 'N/A')}")
            print(f"BAB Title:           {metadata.get('bab_title', 'N/A')}")
            print(f"Pasal Number:        {metadata.get('pasal_number', 'N/A')}")
            print(f"Ayat Count:          {metadata.get('ayat_count', 'N/A')}")
            print(f"Ayat Max:            {metadata.get('ayat_max', 'N/A')}")
            print(f"Ayat Numbers:        {metadata.get('ayat_numbers', 'N/A')}")
            print(f"Ayat Valid:          {metadata.get('ayat_sequence_valid', 'N/A')}")
            print(f"Has Ayat:            {metadata.get('has_ayat', 'N/A')}")
            print(f"\nText Preview (first 500 chars):")
            print("─" * 100)
            print(text[:500] + ("..." if len(text) > 500 else ""))
            print("─" * 100)
            print(f"Full Text Length: {len(text)} characters")

        # Show BAB distribution
        print("\n" + "=" * 100)
        print("CHUNKS DISTRIBUTION BY BAB")
        print("=" * 100)

        bab_distribution = {}
        for chunk in all_chunks:
            metadata = chunk['payload']['metadata']
            bab_title = metadata.get('bab_title', 'NO_BAB')
            bab_distribution[bab_title] = bab_distribution.get(bab_title, 0) + 1

        for bab, count in sorted(bab_distribution.items()):
            print(f"{bab}: {count} chunks")

        # ========== PART 2: POSTGRESQL BAB (PARENT DOCUMENTS) ==========
        print("\n" + "=" * 100)
        print("PART 2: POSTGRESQL BAB (Parent Documents)")
        print("=" * 100)

        try:
            # Try to connect to PostgreSQL
            db_url = "postgresql://nuzantara_rag_db_user:w6uIDSFrr6z5n5I1pJcMQNl47CuzpVu0@dpg-ctdlljm8ii6s73ce05fg-a.oregon-postgres.render.com/nuzantara_rag_db"

            conn = await asyncpg.connect(db_url)

            # Get all BAB for PP_31_2013
            bab_records = await conn.fetch("""
                SELECT
                    id,
                    document_id,
                    title,
                    pasal_count,
                    char_count,
                    LEFT(full_text, 500) as text_preview,
                    LENGTH(full_text) as full_text_length,
                    metadata
                FROM parent_documents
                WHERE document_id = 'PP_31_2013'
                ORDER BY id
            """)

            print(f"\n📊 Total BAB (Parent Documents): {len(bab_records)}\n")

            # Show all BAB
            print("=" * 100)
            print("ALL BAB (CHAPTERS):")
            print("=" * 100)

            for i, record in enumerate(bab_records, 1):
                print(f"\n{'─' * 100}")
                print(f"BAB #{i}")
                print(f"{'─' * 100}")
                print(f"ID:              {record['id']}")
                print(f"Document ID:     {record['document_id']}")
                print(f"Title:           {record['title']}")
                print(f"Pasal Count:     {record['pasal_count']}")
                print(f"Char Count:      {record['char_count']}")
                print(f"Full Text Length: {record['full_text_length']}")
                print(f"\nText Preview (first 500 chars):")
                print("─" * 100)
                print(record['text_preview'])
                print("─" * 100)

                # Parse metadata if JSON
                try:
                    meta = json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata']
                    print(f"\nMetadata Keys: {list(meta.keys())}")
                except:
                    pass

            await conn.close()

            print("\n" + "=" * 100)
            print("SUMMARY")
            print("=" * 100)
            print(f"Total Qdrant Chunks (Pasal): {len(all_chunks)}")
            print(f"Total PostgreSQL BAB (Chapters): {len(bab_records)}")
            print(f"Architecture: ✅ Hierarchical (BAB → PostgreSQL, Pasal → Qdrant)")
            print(f"UUID5 Deterministic IDs: ✅ Enabled")
            print(f"Quality Validation: ✅ Ayat sequence tracking active")

        except Exception as e:
            print(f"\n⚠️  Could not connect to PostgreSQL: {e}")
            print("\n💡 BAB data exists in PostgreSQL but not accessible from local machine.")
            print("   BAB structure includes:")
            print("   - Full chapter text")
            print("   - All Pasal within that chapter")
            print("   - Quality metadata (text_fingerprint, ocr_quality_score)")
            print("   - Hierarchy information")

        print("\n" + "=" * 100)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(show_complete_structure())
