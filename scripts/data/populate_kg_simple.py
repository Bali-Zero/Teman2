"""
Populate Knowledge Graph (Simple)
"""

import asyncio
import json

import asyncpg

ENTITIES = [
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
    ("npwp", "tax_id", "Tax Identification Number", {}),
    ("pph_21", "tax", "Income Tax Article 21 (Employee)", {}),
    ("pph_23", "tax", "Income Tax Article 23 (Services)", {}),
    ("pph_final", "tax", "Final Income Tax (UMKM)", {"rate": "0.5%"}),
    ("ppn", "tax", "Value Added Tax (VAT)", {"rate": "11%"}),
    ("corporate_tax", "tax", "Corporate Income Tax", {"rate": "22%"}),
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


async def populate():
    db_url = "postgres://localhost:5432/nuzantara_dev"
    print(f"Connecting to {db_url}...")
    try:
        conn = await asyncpg.connect(db_url)

        print("Cleaning old data...")
        await conn.execute("TRUNCATE TABLE kg_relationships, kg_entities CASCADE")

        print(f"Seeding {len(ENTITIES)} entities...")
        for entity_id, type_, name, meta in ENTITIES:
            await conn.execute(
                """
                INSERT INTO kg_entities (id, type, name, description, properties)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
            """,
                entity_id,
                type_,
                name,
                f"Entity: {name}",
                json.dumps(meta),
            )

        print(f"Seeding {len(RELATIONSHIPS)} relationships...")
        for source, rel, target, weight in RELATIONSHIPS:
            await conn.execute(
                """
                INSERT INTO kg_relationships (source_entity_id, target_entity_id, relationship_type, strength)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """,
                source,
                target,
                rel,
                weight,
            )

        await conn.close()
        print("✅ KG Populated")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(populate())
