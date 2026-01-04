"""
Migration 032: Drop Legacy Knowledge Graph Tables

Removes the old KG schema (kg_entities, kg_relationships, kg_entity_mentions)
which has been replaced by the unified schema (kg_nodes, kg_edges) in migrations 028-029.

Date: 2025-12-31
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = 32
MIGRATION_NAME = "drop_legacy_kg_tables"


async def check_if_applied(conn: asyncpg.Connection) -> bool:
    """Check if migration was already applied"""
    result = await conn.fetchval("SELECT 1 FROM schema_migrations WHERE version = $1", MIGRATION_ID)
    return result is not None


async def run(conn: asyncpg.Connection) -> bool:
    """
    Drop legacy KG tables that are no longer used.

    Tables being dropped:
    - kg_entity_mentions (depends on kg_entities)
    - kg_relationships (depends on kg_entities)
    - kg_entities

    These have been replaced by:
    - kg_nodes (migration 028)
    - kg_edges (migration 028-029)
    """
    try:
        if await check_if_applied(conn):
            logger.info(f"Migration {MIGRATION_ID} already applied, skipping")
            return True

        logger.info(f"Running migration {MIGRATION_ID}: {MIGRATION_NAME}")

        # Drop tables in correct order (dependencies first)
        # kg_entity_mentions references kg_entities
        # kg_relationships references kg_entities

        await conn.execute("""
            -- Drop kg_entity_mentions first (references kg_entities)
            DROP TABLE IF EXISTS kg_entity_mentions CASCADE;

            -- Drop kg_relationships (references kg_entities)
            DROP TABLE IF EXISTS kg_relationships CASCADE;

            -- Drop kg_entities last
            DROP TABLE IF EXISTS kg_entities CASCADE;
        """)

        # Record migration
        await conn.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (version) DO NOTHING
            """,
            MIGRATION_ID,
            MIGRATION_NAME,
        )

        logger.info(
            f"✅ Migration {MIGRATION_ID} completed: dropped kg_entities, kg_relationships, kg_entity_mentions"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Migration {MIGRATION_ID} failed: {e}")
        raise
