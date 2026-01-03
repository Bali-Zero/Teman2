"""
Migration: Add Source Chunk IDs to Knowledge Graph
Version: 029
Date: 2025-12-29
Description: Links entities and relationships to vector DB chunk IDs.
"""

from typing import Any


async def apply(conn: Any) -> None:
    # 1. Add source_chunk_ids to kg_nodes
    await conn.execute("""
        ALTER TABLE kg_nodes 
        ADD COLUMN IF NOT EXISTS source_chunk_ids TEXT[] DEFAULT '{}';
        
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_chunks ON kg_nodes USING GIN(source_chunk_ids);
    """)

    # 2. Add source_chunk_ids to kg_edges
    await conn.execute("""
        ALTER TABLE kg_edges 
        ADD COLUMN IF NOT EXISTS source_chunk_ids TEXT[] DEFAULT '{}';
        
        CREATE INDEX IF NOT EXISTS idx_kg_edges_chunks ON kg_edges USING GIN(source_chunk_ids);
    """)

    print("✅ Applied migration 029: Added source_chunk_ids to Knowledge Graph")

async def rollback(conn: Any) -> None:
    await conn.execute("ALTER TABLE kg_nodes DROP COLUMN IF EXISTS source_chunk_ids;")
    await conn.execute("ALTER TABLE kg_edges DROP COLUMN IF EXISTS source_chunk_ids;")
    print("Rollback migration 029: source_chunk_ids dropped")
