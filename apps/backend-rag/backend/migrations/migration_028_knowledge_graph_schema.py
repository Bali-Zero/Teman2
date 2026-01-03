"""
Migration: Create Knowledge Graph Tables
Version: 028
Date: 2025-12-29
Description: Adds persistence for Knowledge Graph nodes and edges.
"""

from typing import Any


async def apply(conn: Any) -> None:
    # 1. Create Nodes Table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            properties JSONB DEFAULT '{}'::jsonb,
            confidence FLOAT DEFAULT 1.0,
            source_collection TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(entity_type);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_name ON kg_nodes(name);
    """)

    # 2. Create Edges Table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges (
            relationship_id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
            target_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
            relationship_type TEXT NOT NULL,
            properties JSONB DEFAULT '{}'::jsonb,
            confidence FLOAT DEFAULT 1.0,
            source_collection TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges(source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges(target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_type ON kg_edges(relationship_type);
    """)

    print("✅ Applied migration 028: Knowledge Graph schema created")

async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS kg_edges;")
    await conn.execute("DROP TABLE IF EXISTS kg_nodes;")
    print("Rollback migration 028: Knowledge Graph schema dropped")
