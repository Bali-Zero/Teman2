#!/usr/bin/env python3
"""
Show BAB from PostgreSQL via Fly Proxy
"""
import asyncio
import asyncpg
import json


async def show_bab_structure():
    """Display BAB structure from PostgreSQL"""

    # Use Fly internal connection
    db_url = "postgres://nuzantara_rag_db_user:w6uIDSFrr6z5n5I1pJcMQNl47CuzpVu0@dpg-ctdlljm8ii6s73ce05fg-a.oregon-postgres.render.com/nuzantara_rag_db?sslmode=require"

    try:
        print("=" * 100)
        print("POSTGRESQL BAB (PARENT DOCUMENTS) - PP_31_2013")
        print("=" * 100)

        conn = await asyncpg.connect(db_url)

        # Get all BAB for PP_31_2013
        bab_records = await conn.fetch("""
            SELECT
                id,
                document_id,
                title,
                pasal_count,
                char_count,
                full_text,
                metadata,
                created_at
            FROM parent_documents
            WHERE document_id = 'PP_31_2013'
            ORDER BY id
        """)

        print(f"\n📊 Total BAB: {len(bab_records)}\n")

        # Show each BAB completely
        for i, record in enumerate(bab_records, 1):
            print("\n" + "=" * 100)
            print(f"BAB #{i}: {record['title']}")
            print("=" * 100)
            print(f"ID:              {record['id']}")
            print(f"Document ID:     {record['document_id']}")
            print(f"Pasal Count:     {record['pasal_count']}")
            print(f"Char Count:      {record['char_count']}")
            print(f"Created At:      {record['created_at']}")

            # Show full text
            print(f"\n{'─' * 100}")
            print("FULL TEXT:")
            print(f"{'─' * 100}")
            print(record['full_text'])
            print(f"{'─' * 100}")
            print(f"Length: {len(record['full_text'])} characters")

            # Show metadata
            try:
                meta = json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata']
                print(f"\nMetadata:")
                print(json.dumps(meta, indent=2, ensure_ascii=False))
            except:
                print(f"\nMetadata: {record['metadata']}")

            print("\n")

        # Summary
        print("=" * 100)
        print("SUMMARY")
        print("=" * 100)
        print(f"Total BAB (Chapters): {len(bab_records)}")
        total_pasal = sum(r['pasal_count'] for r in bab_records)
        total_chars = sum(r['char_count'] for r in bab_records)
        print(f"Total Pasal across all BAB: {total_pasal}")
        print(f"Total characters: {total_chars:,}")
        print(f"Average Pasal per BAB: {total_pasal / len(bab_records):.1f}")
        print(f"Average chars per BAB: {total_chars / len(bab_records):,.0f}")

        await conn.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(show_bab_structure())
