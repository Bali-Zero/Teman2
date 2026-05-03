"""
Migration 044: Seed Practice Types

Populates the practice_types table with standard practice types
that match the frontend dropdown values.
"""

import asyncio
import logging
import os

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_NAME = "migration_044_seed_practice_types"

# Practice types that match frontend dropdown values
PRACTICE_TYPES = [
    # VISA category
    {
        "code": "visa",
        "name": "Tourist Visa",
        "category": "visa",
        "description": "Tourist visa application (VOA, B211, etc.)",
        "base_price": 2500000,
        "duration_days": 7,
    },
    {
        "code": "extension_visa",
        "name": "Visa Extension",
        "category": "visa",
        "description": "Extension of existing tourist visa",
        "base_price": 1500000,
        "duration_days": 5,
    },
    # KITAS category
    {
        "code": "kitas",
        "name": "KITAS Application",
        "category": "kitas",
        "description": "Temporary stay permit (work, investor, retirement)",
        "base_price": 15000000,
        "duration_days": 30,
    },
    {
        "code": "extension_kitas",
        "name": "KITAS Extension",
        "category": "kitas",
        "description": "Extension of existing KITAS",
        "base_price": 12000000,
        "duration_days": 21,
    },
    # TAX category
    {
        "code": "tax",
        "name": "Tax Services",
        "category": "tax",
        "description": "Tax registration, reporting, and compliance",
        "base_price": 3000000,
        "duration_days": 14,
    },
    # COMPANY category
    {
        "code": "new_pt",
        "name": "New PT (Company Setup)",
        "category": "company",
        "description": "New PT PMA or PT Local company registration",
        "base_price": 35000000,
        "duration_days": 60,
    },
    {
        "code": "revision_pt",
        "name": "PT Revision/Amendment",
        "category": "company",
        "description": "Company document revision (akta, directors, etc.)",
        "base_price": 8000000,
        "duration_days": 21,
    },
    # OTHER category
    {
        "code": "accessories",
        "name": "Accessories/Add-ons",
        "category": "other",
        "description": "Additional services (legalization, translation, etc.)",
        "base_price": 1000000,
        "duration_days": 7,
    },
]


async def run_migration():
    """Run the migration."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return False

    try:
        conn = await asyncpg.connect(database_url)
        logger.info("Connected to database")

        # Check if migration already applied
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM migrations WHERE migration_name = $1", MIGRATION_NAME,
        )
        if existing:
            logger.info(f"Migration {MIGRATION_NAME} already applied, skipping")
            await conn.close()
            return True

        # Insert practice types (upsert - update if exists)
        # Note: actual column names are typical_duration_days and is_active
        for pt in PRACTICE_TYPES:
            await conn.execute(
                """
                INSERT INTO practice_types (code, name, category, description, base_price, typical_duration_days, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, true)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    description = EXCLUDED.description,
                    base_price = EXCLUDED.base_price,
                    typical_duration_days = EXCLUDED.typical_duration_days,
                    is_active = true
                """,
                pt["code"],
                pt["name"],
                pt["category"],
                pt["description"],
                pt["base_price"],
                pt["duration_days"],
            )
            logger.info(f"Upserted practice type: {pt['code']}")

        # Record migration
        await conn.execute("INSERT INTO migrations (migration_name) VALUES ($1)", MIGRATION_NAME)
        logger.info(f"Migration {MIGRATION_NAME} completed successfully")

        # Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM practice_types WHERE is_active = true")
        logger.info(f"Total active practice types: {count}")

        await conn.close()
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(run_migration())
