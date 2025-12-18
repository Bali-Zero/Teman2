"""
Populate Knowledge Graph
Seeds the database with essential entities and relationships for the Indonesian Legal Domain.
Focus Areas: Visa, Tax, Company Registration (PT PMA), KBLI.
"""

import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- INITIAL DATA ---

ENTITIES = [
    # --- VISA & IMMIGRATION ---
    (
        "visa_investor",
        "visa",
        "Investor Visa (KITAS)",
        {"validity": "1-2 years", "code": "313/314"},
    ),
    ("visa_work", "visa", "Work Visa (KITAS)", {"validity": "1 year", "code": "312"}),
    ("visa_retirement", "visa", "Retirement Visa", {"min_age": 60}),
    ("visa_b211a", "visa", "B211A Visit Visa", {"purpose": "Business/Tourism"}),
    ("voa", "visa", "Visa on Arrival", {"validity": "30 days"}),
    ("kitas", "permit", "Limited Stay Permit", {}),
    ("kitap", "permit", "Permanent Stay Permit", {}),
    # --- CORPORATE & BUSINESS ---
    (
        "pt_pma",
        "legal_entity",
        "PT PMA (Foreign Owned Company)",
        {"min_capital": "10B IDR"},
    ),
    ("pt_local", "legal_entity", "PT Local", {}),
    ("cv", "legal_entity", "CV (Commanditaire Vennootschap)", {}),
    ("oss", "system", "Online Single Submission (OSS)", {"url": "oss.go.id"}),
    ("nib", "license", "Business Identification Number (NIB)", {}),
    ("kbli", "classification", "KBLI (Standard Industrial Classification)", {}),
    # --- TAXATION ---
    ("npwp", "tax_id", "Tax Identification Number", {}),
    ("pph_21", "tax", "Income Tax Article 21 (Employee)", {}),
    ("pph_23", "tax", "Income Tax Article 23 (Services)", {}),
    ("pph_final", "tax", "Final Income Tax (UMKM)", {"rate": "0.5%"}),
    ("ppn", "tax", "Value Added Tax (VAT)", {"rate": "11%"}),
    ("corporate_tax", "tax", "Corporate Income Tax", {"rate": "22%"}),
    # --- REAL ESTATE ---
    ("hak_milik", "property_right", "Freehold Title", {"foreigner_allowed": False}),
    ("hak_pakai", "property_right", "Right to Use", {"foreigner_allowed": True}),
    (
        "hak_guna_bangunan",
        "property_right",
        "Right to Build (HGB)",
        {"foreigner_allowed": "Via PT PMA"},
    ),
]

RELATIONSHIPS = [
    # Source, Relation, Target, Weight
    ("visa_investor", "requires", "pt_pma", 0.9),
    ("visa_work", "requires", "pt_pma", 0.8),
    ("visa_work", "requires", "pt_local", 0.8),
    ("pt_pma", "requires", "nib", 1.0),
    ("pt_pma", "requires", "npwp", 1.0),
    ("pt_pma", "requires", "oss", 0.9),
    ("pt_pma", "governed_by", "kbli", 1.0),
    ("nib", "issued_by", "oss", 1.0),
    ("pt_pma", "subject_to", "corporate_tax", 1.0),
    ("pt_pma", "subject_to", "ppn", 1.0),
    ("pt_pma", "subject_to", "pph_21", 0.9),
    ("pt_pma", "subject_to", "pph_23", 0.9),
    ("hak_guna_bangunan", "can_be_held_by", "pt_pma", 1.0),
    ("hak_pakai", "can_be_held_by", "visa_retirement", 0.7),
    ("hak_pakai", "can_be_held_by", "visa_work", 0.7),
    ("hak_pakai", "can_be_held_by", "visa_investor", 0.7),
]


async def populate_kg():
    """Populate KG tables"""
    db_url = settings.database_url
    if not db_url:
        logger.error("❌ DATABASE_URL not set")
        return

    try:
        pool = await asyncpg.create_pool(db_url)
        async with pool.acquire() as conn:
            logger.info("🧹 Cleaning old KG data...")
            await conn.execute("TRUNCATE TABLE kg_relationships, kg_entities CASCADE")

            logger.info(f"🌱 Seeding {len(ENTITIES)} entities...")
            for entity_id, type_, name, meta in ENTITIES:
                await conn.execute(
                    """
                    INSERT INTO kg_entities (entity_id, type, name, description, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (entity_id) DO NOTHING
                """,
                    entity_id,
                    type_,
                    name,
                    f"Entity: {name}",
                    meta,
                )

            logger.info(f"🔗 Seeding {len(RELATIONSHIPS)} relationships...")
            for source, rel, target, weight in RELATIONSHIPS:
                await conn.execute(
                    """
                    INSERT INTO kg_relationships (source_entity_id, target_entity_id, relationship, weight)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                """,
                    source,
                    target,
                    rel,
                    weight,
                )

        logger.info("✅ Knowledge Graph populated successfully!")
        await pool.close()

    except Exception as e:
        logger.error(f"❌ Error populating KG: {e}")


if __name__ == "__main__":
    asyncio.run(populate_kg())
