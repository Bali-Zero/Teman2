#!/usr/bin/env python3
"""
Knowledge Graph Import Script
==============================
Imports pre-processed KG nodes and edges from JSON exports into PostgreSQL.

Source data:
  - data/kbli_2025_export/kg_nodes_20260205_001231.json  (~68,417 nodes)
  - data/kbli_2025_export/kg_edges_20260205_001231.json  (~30,674 edges)

Target tables:
  - kg_nodes (entity_id, entity_type, name, description, properties, confidence, source_collection, source_chunk_ids)
  - kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, confidence, source_collection, source_chunk_ids)

Usage:
    # Dry run (count only)
    python scripts/ingestion/import_kg_export.py --dry-run

    # Import with upsert (safe - won't duplicate)
    python scripts/ingestion/import_kg_export.py

    # Import from custom files
    python scripts/ingestion/import_kg_export.py --nodes path/to/nodes.json --edges path/to/edges.json

    # Clear existing data first (DESTRUCTIVE)
    python scripts/ingestion/import_kg_export.py --clear-first
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend-rag"))

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default export paths (relative to project root)
# This file: scripts/ingestion/import_kg_export.py → 2 levels up = scripts/, 3 levels up = nuzantara/
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_NODES = (
    PROJECT_ROOT / "data" / "kbli_2025_export" / "kg_nodes_20260205_001231.json"
)
DEFAULT_EDGES = (
    PROJECT_ROOT / "data" / "kbli_2025_export" / "kg_edges_20260205_001231.json"
)

# Source collection tag for imported data
SOURCE_COLLECTION = "kbli_2025_import"

# Batch size for PostgreSQL operations
BATCH_SIZE = 500


async def get_db_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Try loading from .env.local
        env_file = PROJECT_ROOT / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    database_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not database_url:
        raise ValueError(
            "DATABASE_URL not set. Set it as environment variable or in .env.local"
        )

    logger.info(f"Connecting to database: {database_url[:40]}...")
    return await asyncpg.create_pool(database_url, min_size=2, max_size=10)


async def ensure_tables_exist(pool: asyncpg.Pool):
    """Verify kg_nodes and kg_edges tables exist."""
    async with pool.acquire() as conn:
        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('kg_nodes', 'kg_edges')
            """
        )
        table_names = {row["table_name"] for row in tables}

        if "kg_nodes" not in table_names:
            logger.info("Creating kg_nodes table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    properties JSONB DEFAULT '{}'::jsonb,
                    confidence FLOAT DEFAULT 1.0,
                    source_collection TEXT,
                    source_chunk_ids TEXT[] DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(entity_type);
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_name ON kg_nodes(name);
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_chunks ON kg_nodes USING GIN(source_chunk_ids);
            """)

        if "kg_edges" not in table_names:
            logger.info("Creating kg_edges table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    relationship_id TEXT PRIMARY KEY,
                    source_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
                    target_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
                    relationship_type TEXT NOT NULL,
                    properties JSONB DEFAULT '{}'::jsonb,
                    confidence FLOAT DEFAULT 1.0,
                    source_collection TEXT,
                    source_chunk_ids TEXT[] DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges(source_entity_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges(target_entity_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_type ON kg_edges(relationship_type);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_chunks ON kg_edges USING GIN(source_chunk_ids);
            """)

        logger.info("✅ Tables verified: kg_nodes, kg_edges")


async def get_current_counts(pool: asyncpg.Pool) -> dict:
    """Get current row counts for reporting."""
    async with pool.acquire() as conn:
        nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
        return {"nodes": nodes, "edges": edges}


async def clear_tables(pool: asyncpg.Pool):
    """Clear existing KG data. DESTRUCTIVE."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM kg_edges")
        await conn.execute("DELETE FROM kg_nodes")
        logger.warning("🗑️  Cleared all data from kg_nodes and kg_edges")


async def import_nodes(
    pool: asyncpg.Pool, nodes_file: Path, dry_run: bool = False
) -> dict:
    """
    Import nodes from JSON export into kg_nodes table.

    Uses UPSERT (ON CONFLICT DO UPDATE) to safely handle duplicates.
    """
    logger.info(f"Loading nodes from {nodes_file}...")
    with open(nodes_file, "r") as f:
        nodes = json.load(f)

    total = len(nodes)
    logger.info(f"Found {total:,} nodes to import")

    if dry_run:
        # Count unique entity types
        types = {}
        for node in nodes:
            t = node.get("entity_type", "unknown")
            types[t] = types.get(t, 0) + 1
        logger.info(f"Entity types: {json.dumps(types, indent=2)}")
        return {"total": total, "imported": 0, "types": types}

    imported = 0
    skipped = 0
    errors = 0

    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = nodes[i : i + BATCH_SIZE]

        async with pool.acquire() as conn:
            async with conn.transaction():
                for node in batch:
                    try:
                        entity_id = node["entity_id"]
                        entity_type = node.get("entity_type", "unknown")
                        name = node.get("name", entity_id)
                        description = node.get("description", "")
                        metadata = node.get("metadata", {})

                        await conn.execute(
                            """
                            INSERT INTO kg_nodes (
                                entity_id, entity_type, name, description,
                                properties, confidence, source_collection,
                                source_chunk_ids, created_at, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                            ON CONFLICT (entity_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                description = COALESCE(NULLIF(EXCLUDED.description, ''), kg_nodes.description),
                                properties = kg_nodes.properties || EXCLUDED.properties,
                                confidence = GREATEST(kg_nodes.confidence, EXCLUDED.confidence),
                                source_collection = EXCLUDED.source_collection,
                                updated_at = NOW()
                            """,
                            entity_id,
                            entity_type,
                            name,
                            description,
                            json.dumps(metadata),
                            1.0,  # High confidence for curated export data
                            SOURCE_COLLECTION,
                            [],  # No chunk IDs for bulk import
                        )
                        imported += 1

                    except Exception as e:
                        errors += 1
                        if errors <= 10:
                            logger.warning(
                                f"Error importing node {node.get('entity_id', '?')}: {e}"
                            )

        # Progress
        progress = min(i + BATCH_SIZE, total)
        if progress % 5000 == 0 or progress >= total:
            logger.info(
                f"  Nodes: {progress:,}/{total:,} processed, "
                f"{imported:,} imported, {errors} errors"
            )

    logger.info(
        f"✅ Nodes import complete: {imported:,} imported, "
        f"{skipped:,} skipped, {errors} errors"
    )
    return {"total": total, "imported": imported, "skipped": skipped, "errors": errors}


async def import_edges(
    pool: asyncpg.Pool, edges_file: Path, dry_run: bool = False
) -> dict:
    """
    Import edges from JSON export into kg_edges table.

    Uses UPSERT with generated relationship_id.
    Validates that source and target entities exist (FK constraint).
    """
    logger.info(f"Loading edges from {edges_file}...")
    with open(edges_file, "r") as f:
        edges = json.load(f)

    total = len(edges)
    logger.info(f"Found {total:,} edges to import")

    if dry_run:
        # Count relationship types
        types = {}
        for edge in edges:
            t = edge.get("relationship_type", "UNKNOWN")
            types[t] = types.get(t, 0) + 1
        logger.info(f"Relationship types: {json.dumps(types, indent=2)}")
        return {"total": total, "imported": 0, "types": types}

    imported = 0
    fk_violations = 0
    errors = 0

    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = edges[i : i + BATCH_SIZE]

        async with pool.acquire() as conn:
            for edge in batch:
                try:
                    source_id = edge["source_entity_id"]
                    target_id = edge["target_entity_id"]
                    rel_type = edge.get("relationship_type", "RELATED_TO")
                    metadata = edge.get("metadata", {})

                    # Generate relationship_id
                    rel_id = f"{source_id}__{rel_type}__{target_id}"

                    await conn.execute(
                        """
                        INSERT INTO kg_edges (
                            relationship_id, source_entity_id, target_entity_id,
                            relationship_type, properties, confidence,
                            source_collection, source_chunk_ids, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                        ON CONFLICT (relationship_id) DO UPDATE SET
                            properties = kg_edges.properties || EXCLUDED.properties,
                            confidence = GREATEST(kg_edges.confidence, EXCLUDED.confidence)
                        """,
                        rel_id,
                        source_id,
                        target_id,
                        rel_type,
                        json.dumps(metadata),
                        1.0,
                        SOURCE_COLLECTION,
                        [],
                    )
                    imported += 1

                except Exception as e:
                    error_str = str(e).lower()
                    if "foreign key" in error_str or "violates" in error_str:
                        fk_violations += 1
                    else:
                        errors += 1
                        if errors <= 10:
                            logger.warning(
                                f"Error importing edge "
                                f"{edge.get('source_entity_id', '?')} -> "
                                f"{edge.get('target_entity_id', '?')}: {e}"
                            )

        # Progress
        progress = min(i + BATCH_SIZE, total)
        if progress % 5000 == 0 or progress >= total:
            logger.info(
                f"  Edges: {progress:,}/{total:,} processed, "
                f"{imported:,} imported, {fk_violations} FK skips, {errors} errors"
            )

    logger.info(
        f"✅ Edges import complete: {imported:,} imported, "
        f"{fk_violations} FK violations skipped, {errors} errors"
    )
    return {
        "total": total,
        "imported": imported,
        "fk_violations": fk_violations,
        "errors": errors,
    }


async def verify_import(pool: asyncpg.Pool):
    """Run basic integrity checks on imported data."""
    async with pool.acquire() as conn:
        # Counts
        nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")

        # Entity type distribution
        type_dist = await conn.fetch(
            """
            SELECT entity_type, COUNT(*) as cnt
            FROM kg_nodes
            GROUP BY entity_type
            ORDER BY cnt DESC
            LIMIT 15
            """
        )

        # Relationship type distribution
        rel_dist = await conn.fetch(
            """
            SELECT relationship_type, COUNT(*) as cnt
            FROM kg_edges
            GROUP BY relationship_type
            ORDER BY cnt DESC
            """
        )

        # Orphan check (nodes with no edges)
        orphans = await conn.fetchval(
            """
            SELECT COUNT(*) FROM kg_nodes n
            WHERE NOT EXISTS (
                SELECT 1 FROM kg_edges e
                WHERE e.source_entity_id = n.entity_id
                   OR e.target_entity_id = n.entity_id
            )
            """
        )

        # Connectivity
        connected = nodes - orphans
        connectivity = (connected / nodes * 100) if nodes > 0 else 0

        logger.info("\n" + "=" * 60)
        logger.info("KNOWLEDGE GRAPH VERIFICATION REPORT")
        logger.info("=" * 60)
        logger.info(f"Total nodes:        {nodes:,}")
        logger.info(f"Total edges:        {edges:,}")
        logger.info(f"Connected nodes:    {connected:,} ({connectivity:.1f}%)")
        logger.info(f"Orphan nodes:       {orphans:,}")
        logger.info(f"Avg edges/node:     {edges / nodes:.1f}" if nodes > 0 else "N/A")
        logger.info("")
        logger.info("Entity Types:")
        for row in type_dist:
            logger.info(f"  {row['entity_type']:25s} {row['cnt']:>8,}")
        logger.info("")
        logger.info("Relationship Types:")
        for row in rel_dist:
            logger.info(f"  {row['relationship_type']:25s} {row['cnt']:>8,}")
        logger.info("=" * 60)

        return {
            "nodes": nodes,
            "edges": edges,
            "connectivity_pct": connectivity,
            "orphans": orphans,
        }


async def main():
    parser = argparse.ArgumentParser(
        description="Import KG JSON exports into PostgreSQL"
    )
    parser.add_argument(
        "--nodes",
        type=str,
        default=str(DEFAULT_NODES),
        help="Path to nodes JSON file",
    )
    parser.add_argument(
        "--edges",
        type=str,
        default=str(DEFAULT_EDGES),
        help="Path to edges JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count and analyze data without importing",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Clear existing data before import (DESTRUCTIVE)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-import verification",
    )
    args = parser.parse_args()

    nodes_file = Path(args.nodes)
    edges_file = Path(args.edges)

    # Validate files exist
    if not nodes_file.exists():
        logger.error(f"Nodes file not found: {nodes_file}")
        sys.exit(1)
    if not edges_file.exists():
        logger.error(f"Edges file not found: {edges_file}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("NUZANTARA KNOWLEDGE GRAPH IMPORT")
    logger.info("=" * 60)
    logger.info(
        f"Nodes file: {nodes_file} ({nodes_file.stat().st_size / 1024 / 1024:.1f} MB)"
    )
    logger.info(
        f"Edges file: {edges_file} ({edges_file.stat().st_size / 1024 / 1024:.1f} MB)"
    )
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE IMPORT'}")
    logger.info("")

    start = time.time()

    # Dry run: analyze JSON files only, no database needed
    if args.dry_run:
        node_stats = await import_nodes(None, nodes_file, dry_run=True)
        edge_stats = await import_edges(None, edges_file, dry_run=True)
        elapsed = time.time() - start
        logger.info(f"\nTotal time: {elapsed:.1f} seconds")
        return

    # Live import: connect to database
    pool = await get_db_pool()

    try:
        # Ensure tables exist
        await ensure_tables_exist(pool)

        # Get current state
        before = await get_current_counts(pool)
        logger.info(
            f"Current state: {before['nodes']:,} nodes, {before['edges']:,} edges"
        )

        # Clear if requested
        if args.clear_first:
            await clear_tables(pool)

        # Import nodes first (edges depend on nodes via FK)
        node_stats = await import_nodes(pool, nodes_file)

        # Import edges
        edge_stats = await import_edges(pool, edges_file)

        # Verify
        if not args.skip_verify:
            await verify_import(pool)

        elapsed = time.time() - start
        logger.info(f"\nTotal time: {elapsed:.1f} seconds")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
