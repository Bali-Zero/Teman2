#!/usr/bin/env python3
"""
Import Kemnaker Circular KG to Production PostgreSQL via Fly.io

This script imports the KG entities and relationships that were backed up
to /tmp/kemnaker_circular_kg.json into production PostgreSQL.

Usage (requires Fly.io proxy):
    # Terminal 1: Start Fly.io proxy to PostgreSQL
    fly proxy 15432:5432 -a nuzantara-rag

    # Terminal 2: Run this script
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL="postgres://user:pass@localhost:15432/dbname" python scripts/ingestion/import_kemnaker_kg_production.py

Alternatively, run on Fly.io machine directly:
    fly ssh console -a nuzantara-rag
    cd /app
    python -c "..." (copy the SQL below)
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# KG backup file path
KG_BACKUP_FILE = Path("/tmp/kemnaker_circular_kg.json")
COLLECTION_NAME = "immigration_circulars"


async def import_kg():
    """Import KG from backup file to PostgreSQL."""
    import asyncpg

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        logger.info("Usage: DATABASE_URL='postgres://...' python import_kemnaker_kg_production.py")
        logger.info("Or use Fly.io proxy: fly proxy 15432:5432 -a nuzantara-rag")
        sys.exit(1)

    if not KG_BACKUP_FILE.exists():
        logger.error(f"Backup file not found: {KG_BACKUP_FILE}")
        logger.info("Run ingest_kemnaker_circular.py first to create the backup")
        sys.exit(1)

    # Load KG data
    with open(KG_BACKUP_FILE) as f:
        kg_data = json.load(f)

    entities = kg_data.get("entities", [])
    relationships = kg_data.get("relationships", [])

    logger.info(f"Loaded {len(entities)} entities, {len(relationships)} relationships")

    # Connect to PostgreSQL
    conn = await asyncpg.connect(database_url)

    try:
        # Insert entities
        logger.info("Inserting entities to kg_nodes...")
        for entity in entities:
            await conn.execute(
                """
                INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                ON CONFLICT (entity_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    properties = EXCLUDED.properties,
                    confidence = EXCLUDED.confidence,
                    source_collection = EXCLUDED.source_collection
                """,
                entity["entity_id"],
                entity["entity_type"],
                entity["name"],
                entity.get("description", ""),
                json.dumps(entity.get("properties", {})),
                entity.get("confidence", 0.9),
                COLLECTION_NAME,
            )
            logger.info(f"  ✅ {entity['entity_id']}: {entity['name']}")

        # Ensure PP 28/2025 entity exists (referenced by relationship)
        await conn.execute(
            """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
            ON CONFLICT (entity_id) DO NOTHING
            """,
            "pp_28_2025",
            "peraturan_pemerintah",
            "PP No. 28 Tahun 2025",
            "Peraturan Pemerintah tentang Peraturan Pelaksana UU Cipta Kerja (Ketenagakerjaan)",
            json.dumps({"number": "28", "year": "2025", "topic": "Ketenagakerjaan"}),
            0.9,
            "legal_unified_hybrid",
        )
        logger.info("  ✅ pp_28_2025: PP No. 28 Tahun 2025 (reference target)")

        # Insert relationships
        logger.info("Inserting relationships to kg_edges...")
        for rel in relationships:
            await conn.execute(
                """
                INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, confidence, source_collection)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                ON CONFLICT (relationship_id) DO UPDATE SET
                    properties = EXCLUDED.properties,
                    confidence = EXCLUDED.confidence,
                    source_collection = EXCLUDED.source_collection
                """,
                rel["relationship_id"],
                rel["source_entity_id"],
                rel["target_entity_id"],
                rel["relationship_type"],
                json.dumps(rel.get("properties", {})),
                rel.get("confidence", 0.9),
                COLLECTION_NAME,
            )
            logger.info(f"  ✅ {rel['source_entity_id']} --{rel['relationship_type']}--> {rel['target_entity_id']}")

        logger.info("=" * 60)
        logger.info("KG IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Entities: {len(entities) + 1}")  # +1 for PP 28/2025
        logger.info(f"Relationships: {len(relationships)}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(import_kg())
