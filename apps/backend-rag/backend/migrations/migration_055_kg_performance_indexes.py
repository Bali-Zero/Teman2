"""
Migration: Knowledge Graph Performance Indexes
Version: 055
Date: 2026-02-26
Description: Adds trigram index for fuzzy entity resolution and composite
             indexes for BFS traversal performance on 56k nodes / 161k edges.

Requires pg_trgm extension (already available on Fly.io PostgreSQL).
"""

from typing import Any


async def apply(conn: Any) -> None:
    # 1. Enable pg_trgm extension (idempotent)
    await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Trigram GIN index on kg_nodes.name for similarity() queries
    #    Without this, resolve_entities_node does a full table scan (56k rows)
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kg_nodes_name_trgm
        ON kg_nodes USING GIN(name gin_trgm_ops);
    """)

    # 3. Composite index for BFS traversal: source + relationship type + confidence filter
    #    The traverse_graph_node queries by source_entity_id with relationship_type IN (...)
    #    and joins on target confidence > 0.7
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kg_edges_source_reltype
        ON kg_edges(source_entity_id, relationship_type);
    """)

    # 4. Covering index for entity resolution: LOWER(name) for exact match
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kg_nodes_name_lower
        ON kg_nodes(LOWER(name));
    """)

    # 5. Partial index for high-confidence nodes (used in traversal filter: confidence > 0.7)
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kg_nodes_high_confidence
        ON kg_nodes(entity_id) WHERE confidence > 0.7;
    """)

    print("✅ Applied migration 055: KG performance indexes (trigram, composite, partial)")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_kg_nodes_name_trgm;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_edges_source_reltype;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_nodes_name_lower;")
    await conn.execute("DROP INDEX IF EXISTS idx_kg_nodes_high_confidence;")
    print("Rollback migration 055: KG performance indexes dropped")
