#!/usr/bin/env python3
"""
Export BAB to JSON - run this FROM INSIDE the backend container
"""
import asyncio
import asyncpg
import json
import os


async def export_bab():
    """Export BAB data to JSON file"""
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return

    try:
        print(f"Connecting to database...")
        conn = await asyncpg.connect(db_url, timeout=30)
        print("✅ Connected!")

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
                created_at::text as created_at
            FROM parent_documents
            WHERE document_id = 'PP_31_2013'
            ORDER BY id
        """)

        await conn.close()

        # Convert to list of dicts
        bab_data = []
        for r in records:
            bab_data.append(dict(r))

        # Save to JSON
        output = {
            "document_id": "PP_31_2013",
            "total_bab": len(bab_data),
            "bab": bab_data
        }

        with open("/tmp/pp31_bab_export.json", "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Exported {len(bab_data)} BAB to /tmp/pp31_bab_export.json")
        print(json.dumps(output, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(export_bab())
