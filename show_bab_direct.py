#!/usr/bin/env python3
"""
Connect directly to PostgreSQL and show BAB
"""
import asyncio
import asyncpg


async def show_bab():
    """Show BAB from PostgreSQL"""

    # Render PostgreSQL connection
    db_url = "postgresql://nuzantara_rag_db_user:w6uIDSFrr6z5n5I1pJcMQNl47CuzpVu0@dpg-ctdlljm8ii6s73ce05fg-a.oregon-postgres.render.com/nuzantara_rag_db"

    try:
        print("Connecting to PostgreSQL...")
        conn = await asyncpg.connect(
            db_url,
            ssl='require',
            timeout=30
        )

        print("✅ Connected!\n")
        print("="*100)
        print("PP_31_2013 - BAB (Parent Documents)")
        print("="*100)

        records = await conn.fetch("""
            SELECT
                id,
                document_id,
                type,
                title,
                pasal_count,
                char_count,
                LEFT(full_text, 2000) as text_preview,
                LENGTH(full_text) as full_text_length,
                created_at
            FROM parent_documents
            WHERE document_id = 'PP_31_2013'
            ORDER BY id
        """)

        print(f"\n📊 Total BAB: {len(records)}\n")

        for i, r in enumerate(records, 1):
            print("\n" + "="*100)
            print(f"BAB #{i}")
            print("="*100)
            print(f"ID:               {r['id']}")
            print(f"Document ID:      {r['document_id']}")
            print(f"Type:             {r['type']}")
            print(f"Title:            {r['title']}")
            print(f"Pasal Count:      {r['pasal_count']}")
            print(f"Char Count:       {r['char_count']}")
            print(f"Full Text Length: {r['full_text_length']}")
            print(f"Created At:       {r['created_at']}")
            print(f"\n{'─'*100}")
            print("TEXT PREVIEW (first 2000 chars):")
            print(f"{'─'*100}")
            print(r['text_preview'])
            print(f"{'─'*100}\n")

        await conn.close()
        print("\n✅ Query completed successfully!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(show_bab())
