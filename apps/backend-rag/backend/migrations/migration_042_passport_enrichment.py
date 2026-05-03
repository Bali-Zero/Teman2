"""
Migration 042: Passport Enrichment Fields

Adds columns for enhanced passport OCR and birthplace enrichment:
- gender: M/F from passport
- birthplace: City/country of birth
- passport_ocr_data: Full OCR JSON for audit
- birthplace_enrichment_date: When enrichment was done
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_NAME = "migration_042_passport_enrichment"

MIGRATION_SQL = """
-- Migration 042: Passport Enrichment Fields

-- gender: M or F extracted from passport
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'gender'
    ) THEN
        ALTER TABLE clients ADD COLUMN gender VARCHAR(1);
        RAISE NOTICE 'Added gender column to clients table';
    END IF;
END $$;

-- birthplace: City/Country from passport
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'birthplace'
    ) THEN
        ALTER TABLE clients ADD COLUMN birthplace VARCHAR(255);
        RAISE NOTICE 'Added birthplace column to clients table';
    END IF;
END $$;

-- passport_ocr_data: Full OCR response for audit/re-extraction
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'passport_ocr_data'
    ) THEN
        ALTER TABLE clients ADD COLUMN passport_ocr_data JSONB DEFAULT '{}'::jsonb;
        RAISE NOTICE 'Added passport_ocr_data column to clients table';
    END IF;
END $$;

-- birthplace_enrichment_date: Track when enrichment was done
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'birthplace_enrichment_date'
    ) THEN
        ALTER TABLE clients ADD COLUMN birthplace_enrichment_date TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Added birthplace_enrichment_date column to clients table';
    END IF;
END $$;

-- Index for clients needing enrichment (birthplace set but not enriched yet)
CREATE INDEX IF NOT EXISTS idx_clients_birthplace_enrichment
ON clients(birthplace) WHERE birthplace IS NOT NULL AND birthplace_enrichment_date IS NULL;

-- Index for birthday notifications (month + day lookup)
CREATE INDEX IF NOT EXISTS idx_clients_birthday
ON clients(EXTRACT(MONTH FROM date_of_birth), EXTRACT(DAY FROM date_of_birth))
WHERE date_of_birth IS NOT NULL;
"""


async def run_migration():
    """Run the migration."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return False

    try:
        conn = await asyncpg.connect(database_url)
        logger.info(f"Running {MIGRATION_NAME}...")

        # Check if migration already applied
        existing = await conn.fetchval(
            "SELECT 1 FROM migrations WHERE migration_name = $1",
            MIGRATION_NAME,
        )
        if existing:
            logger.info(f"Migration {MIGRATION_NAME} already applied, skipping")
            await conn.close()
            return True

        # Run migration
        await conn.execute(MIGRATION_SQL)

        # Record migration
        await conn.execute(
            """
            INSERT INTO migrations (migration_name, applied_at)
            VALUES ($1, NOW())
            ON CONFLICT (migration_name) DO NOTHING
            """,
            MIGRATION_NAME,
        )

        logger.info(f"✅ Migration {MIGRATION_NAME} completed successfully")
        await conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(run_migration())
