#!/usr/bin/env python3
"""
Agent 3: Insert KG Entities to PostgreSQL
==========================================
Batch inserts KG entities (nodes + edges) into PostgreSQL with retry logic.

Input: data/kg_entities_*.json (from Agent 2)
Output: Updated kg_nodes and kg_edges tables in PostgreSQL
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend-rag"))

import asyncpg

from backend.app.core.config import settings as backend_settings
from backend.db.utils import db_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [AGENT-3] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def get_db_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    # Try environment variable first
    database_url = os.environ.get("DATABASE_URL")

    # Fall back to backend settings (already imported at top)
    if not database_url:
        database_url = backend_settings.database_url

    # Try loading from .env.local as last resort
    if not database_url:
        env_file = Path(__file__).parent.parent.parent / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    database_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not database_url:
        raise ValueError("DATABASE_URL not set. Set it as environment variable or in .env.local")

    logger.info(f"Connecting to database: {database_url[:40]}...")
    return await asyncpg.create_pool(database_url, min_size=2, max_size=10)


@db_retry(max_retries=3, delay=1.0, backoff_factor=2.0)
async def insert_nodes_batch(pool: asyncpg.Pool, nodes: list[dict]) -> int:
    """
    Insert batch of nodes with UPSERT logic.

    Args:
        pool: Database connection pool
        nodes: List of node dicts

    Returns:
        Number of nodes inserted/updated
    """
    inserted = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            for node in nodes:
                try:
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
                        node["entity_id"],
                        node["entity_type"],
                        node["name"],
                        node.get("description", ""),
                        json.dumps(node.get("metadata", {})),
                        node.get("confidence", 1.0),
                        node.get("source_collection", "kbli_2025_final"),
                        [],  # No chunk IDs for bulk import
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Error inserting node {node.get('entity_id', '?')}: {e}")

    return inserted


@db_retry(max_retries=3, delay=1.0, backoff_factor=2.0)
async def insert_edges_batch(pool: asyncpg.Pool, edges: list[dict]) -> tuple[int, int]:
    """
    Insert batch of edges with UPSERT logic.

    Args:
        pool: Database connection pool
        edges: List of edge dicts

    Returns:
        Tuple of (inserted count, FK violation count)
    """
    inserted = 0
    fk_violations = 0

    async with pool.acquire() as conn:
        for edge in edges:
            try:
                source_id = edge["source_entity_id"]
                target_id = edge["target_entity_id"]
                rel_type = edge.get("relationship_type", "RELATED_TO")
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
                    json.dumps(edge.get("metadata", {})),
                    edge.get("confidence", 1.0),
                    edge.get("source_collection", "kbli_2025_final"),
                    [],
                )
                inserted += 1

            except Exception as e:
                error_str = str(e).lower()
                if "foreign key" in error_str or "violates" in error_str:
                    fk_violations += 1
                else:
                    logger.warning(
                        f"Error inserting edge {edge.get('source_entity_id', '?')} -> "
                        f"{edge.get('target_entity_id', '?')}: {e}"
                    )

    return inserted, fk_violations


async def insert_kg_entities(pool: asyncpg.Pool, kg_entities: dict) -> dict:
    """
    Insert all KG entities (nodes + edges) to PostgreSQL.

    Args:
        pool: Database connection pool
        kg_entities: Dict with 'nodes' and 'edges' lists

    Returns:
        Dict with insertion stats
    """
    nodes = kg_entities["nodes"]
    edges = kg_entities["edges"]

    logger.info(f"Inserting {len(nodes):,} nodes and {len(edges):,} edges...")

    # Insert nodes in batches
    total_nodes_inserted = 0
    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i : i + BATCH_SIZE]
        inserted = await insert_nodes_batch(pool, batch)
        total_nodes_inserted += inserted

        if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(nodes):
            progress = min(i + BATCH_SIZE, len(nodes))
            logger.info(
                f"  Nodes: {progress:,}/{len(nodes):,} processed "
                f"({progress / len(nodes) * 100:.1f}%)"
            )

    logger.info(f"✅ Nodes inserted: {total_nodes_inserted:,}/{len(nodes):,}")

    # Insert edges in batches
    total_edges_inserted = 0
    total_fk_violations = 0

    for i in range(0, len(edges), BATCH_SIZE):
        batch = edges[i : i + BATCH_SIZE]
        inserted, fk_violations = await insert_edges_batch(pool, batch)
        total_edges_inserted += inserted
        total_fk_violations += fk_violations

        if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(edges):
            progress = min(i + BATCH_SIZE, len(edges))
            logger.info(
                f"  Edges: {progress:,}/{len(edges):,} processed "
                f"({progress / len(edges) * 100:.1f}%), "
                f"FK violations: {total_fk_violations}"
            )

    logger.info(
        f"✅ Edges inserted: {total_edges_inserted:,}/{len(edges):,} "
        f"(FK violations: {total_fk_violations})"
    )

    return {
        "nodes_total": len(nodes),
        "nodes_inserted": total_nodes_inserted,
        "edges_total": len(edges),
        "edges_inserted": total_edges_inserted,
        "edges_fk_violations": total_fk_violations,
    }


async def verify_insertion(pool: asyncpg.Pool) -> dict:
    """Verify insertion by counting final rows."""
    async with pool.acquire() as conn:
        total_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        total_edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
        kbli_nodes = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_nodes WHERE entity_id LIKE 'kbli:%'"
        )
        perizinan_nodes = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'perizinan'"
        )
        sektor_nodes = await conn.fetchval(
            "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'sektor'"
        )

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "kbli_nodes": kbli_nodes,
        "perizinan_nodes": perizinan_nodes,
        "sektor_nodes": sektor_nodes,
    }


async def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Insert KG entities to PostgreSQL")
    parser.add_argument(
        "--input",
        type=str,
        help="Path to kg_entities JSON file (from Agent 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - analyze but don't insert",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("AGENT 3: INSERT KG ENTITIES TO POSTGRESQL")
    logger.info("=" * 70)

    # Find input file
    if args.input:
        input_file = Path(args.input)
    else:
        # Find latest kg_entities file
        data_dir = Path(__file__).parent.parent.parent / "data"
        entity_files = sorted(data_dir.glob("kg_entities_*.json"), reverse=True)
        if not entity_files:
            logger.error("❌ No kg_entities_*.json files found in data/")
            return
        input_file = entity_files[0]

    logger.info(f"Input file: {input_file}")

    # Load data
    with open(input_file, encoding="utf-8") as f:
        kg_entities = json.load(f)

    logger.info(
        f"Loaded {len(kg_entities['nodes']):,} nodes and {len(kg_entities['edges']):,} edges"
    )

    if args.dry_run:
        logger.info("DRY RUN MODE - No database changes")
        logger.info(f"Would insert {len(kg_entities['nodes']):,} nodes")
        logger.info(f"Would insert {len(kg_entities['edges']):,} edges")
        return

    # Connect to database
    pool = await get_db_pool()

    try:
        # Before stats
        before = await verify_insertion(pool)
        logger.info(
            f"Current state: {before['total_nodes']:,} nodes, {before['total_edges']:,} edges"
        )

        # Insert
        await insert_kg_entities(pool, kg_entities)

        # After stats
        after = await verify_insertion(pool)

        logger.info("\n" + "=" * 70)
        logger.info("FINAL VERIFICATION")
        logger.info("=" * 70)
        logger.info(f"Total nodes: {after['total_nodes']:,} (was {before['total_nodes']:,})")
        logger.info(f"Total edges: {after['total_edges']:,} (was {before['total_edges']:,})")
        logger.info(f"KBLI nodes: {after['kbli_nodes']:,}")
        logger.info(f"Perizinan nodes: {after['perizinan_nodes']:,}")
        logger.info(f"Sektor nodes: {after['sektor_nodes']:,}")
        logger.info("=" * 70)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
