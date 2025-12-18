#!/usr/bin/env python3
"""
Apply Migration 022 directly to PostgreSQL via asyncpg
"""
import asyncio
import asyncpg


async def apply_migration():
    """Apply migration 022 to parent_documents table"""

    conn_string = "postgresql://nuzantara:uLNT1jX9mKQKN1KzIYH2kQ@nuzantara-db.flycast:5432/nuzantara?sslmode=disable"

    print("=" * 80)
    print("APPLYING MIGRATION 022: Dedup Constraints & Quality Tracking")
    print("=" * 80)

    try:
        conn = await asyncpg.connect(conn_string, timeout=10)

        # Add columns
        print("\n1️⃣  Adding text_fingerprint column...")
        await conn.execute(
            "ALTER TABLE parent_documents ADD COLUMN IF NOT EXISTS text_fingerprint VARCHAR(64);"
        )

        print("2️⃣  Adding OCR quality columns...")
        await conn.execute(
            """
            ALTER TABLE parent_documents
            ADD COLUMN IF NOT EXISTS is_incomplete BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS ocr_quality_score FLOAT DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS needs_reextract BOOLEAN DEFAULT FALSE;
            """
        )

        print("3️⃣  Adding source version columns...")
        await conn.execute(
            """
            ALTER TABLE parent_documents
            ADD COLUMN IF NOT EXISTS source_id TEXT,
            ADD COLUMN IF NOT EXISTS source_version VARCHAR(32),
            ADD COLUMN IF NOT EXISTS ingestion_run_id VARCHAR(64),
            ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN DEFAULT TRUE;
            """
        )

        print("4️⃣  Creating indexes...")
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_parent_docs_fingerprint
            ON parent_documents(document_id, text_fingerprint);
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_parent_docs_incomplete
            ON parent_documents(is_incomplete) WHERE is_incomplete = TRUE;
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_parent_docs_canonical
            ON parent_documents(document_id, is_canonical) WHERE is_canonical = TRUE;
            """
        )

        print("\n✅ Migration 022 applied successfully!")

        # Verify
        print("\n📊 Verifying schema...")
        rows = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'parent_documents'
            AND column_name IN ('text_fingerprint', 'is_incomplete', 'ocr_quality_score',
                                'needs_reextract', 'source_id', 'source_version',
                                'ingestion_run_id', 'is_canonical')
            ORDER BY column_name;
            """
        )

        print("\nNew columns:")
        for row in rows:
            print(f"  - {row['column_name']:<25} {row['data_type']:<20} NULL: {row['is_nullable']}")

        await conn.close()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(apply_migration())
