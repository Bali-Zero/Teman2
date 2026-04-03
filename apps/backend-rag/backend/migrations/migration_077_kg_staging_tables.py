"""
Migration: Create KG Staging Tables for Auto-Expansion Quarantine Pattern
Version: 077
Date: 2026-04-03
Description: Creates kg_nodes_staging and kg_edges_staging tables for the
  GraphRAG Evolution v6.0 auto-expansion quarantine pattern.

  Auto-expanded entities write to staging tables first.
  A batch promotion job validates and promotes to production
  kg_nodes/kg_edges every 6h.

  Reference: docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md §3.4
"""

from typing import Any


async def apply(conn: Any) -> None:
    # 1. Create Staging Nodes Table (mirrors kg_nodes + extraction metadata)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes_staging (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            properties JSONB DEFAULT '{}'::jsonb,
            confidence FLOAT DEFAULT 0.7,
            source_chunk_ids TEXT[],
            extraction_source TEXT DEFAULT 'auto_heuristic',
            promotion_status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_status
            ON kg_nodes_staging(promotion_status);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_created
            ON kg_nodes_staging(created_at);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_type
            ON kg_nodes_staging(entity_type);
    """)

    # 2. Create Staging Edges Table (mirrors kg_edges + extraction metadata)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges_staging (
            relationship_id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            properties JSONB DEFAULT '{}'::jsonb,
            confidence FLOAT DEFAULT 0.7,
            source_chunk_ids TEXT[],
            extraction_source TEXT DEFAULT 'auto_heuristic',
            promotion_status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_status
            ON kg_edges_staging(promotion_status);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_source
            ON kg_edges_staging(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_target
            ON kg_edges_staging(target_entity_id);
    """)

    # 3. Add source_collection_previous to kg_nodes for Qdrant migration rollback
    await conn.execute("""
        ALTER TABLE kg_nodes
            ADD COLUMN IF NOT EXISTS source_collection_previous TEXT;
    """)

    print("✅ Applied migration 077: KG staging tables + source_collection_previous")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS kg_edges_staging;")
    await conn.execute("DROP TABLE IF EXISTS kg_nodes_staging;")
    await conn.execute("ALTER TABLE kg_nodes DROP COLUMN IF EXISTS source_collection_previous;")
    print("Rollback migration 077: KG staging tables dropped")
