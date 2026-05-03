"""
Migration: Add GIN indexes on KG JSONB properties and source_chunk_ids
Version: 088
Date: 2026-04-06
Description: Adds GIN indexes for faster JSONB property queries and array containment.
    Already applied to production DB on 2026-04-06.
"""

from typing import Any


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_properties_gin ON kg_nodes USING GIN (properties);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_properties_gin ON kg_edges USING GIN (properties);
    """)
    await conn.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='kg_nodes' AND column_name='source_chunk_ids') THEN
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_chunk_ids_gin ON kg_nodes USING GIN (source_chunk_ids);
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='kg_edges' AND column_name='source_chunk_ids') THEN
                CREATE INDEX IF NOT EXISTS idx_kg_edges_chunk_ids_gin ON kg_edges USING GIN (source_chunk_ids);
            END IF;
        END $$;
    """)
    print("Applied migration 088: KG GIN indexes")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_kg_nodes_properties_gin;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_edges_properties_gin;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_nodes_chunk_ids_gin;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_edges_chunk_ids_gin;")
    print("Rollback migration 088")
