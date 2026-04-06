#!/usr/bin/env python3
"""
Advanced Knowledge Graph Enhancement Script

Applies advanced quality improvements:
1. Entity name normalization
2. Hierarchical relationship detection
3. Domain-specific relationship inference
4. Cross-reference detection

Usage:
    # Dry run
    python -m scripts.kg_advanced_enhance --dry-run

    # Apply to specific collection
    python -m scripts.kg_advanced_enhance --collection legal_unified_hybrid

    # Full enhancement
    python -m scripts.kg_advanced_enhance --apply
"""

import argparse
import asyncio
import logging
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kg_enhance")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_enhancement(
    collection: str | None = None,
    dry_run: bool = True,
):
    """Run the enhancement pipeline"""
    import asyncpg

    from backend.services.knowledge_graph.advanced_quality import (
        detect_hierarchical_relationships,
        infer_domain_relationships,
        normalize_entity_name,
    )

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    conn = await asyncpg.connect(db_url)

    try:
        # Get collections to process
        if collection:
            collections = [collection]
        else:
            rows = await conn.fetch(
                "SELECT DISTINCT source_collection FROM kg_nodes WHERE source_collection IS NOT NULL"
            )
            collections = [row["source_collection"] for row in rows]

        logger.info(f"Processing {len(collections)} collections")

        total_normalized = 0
        total_hierarchical = 0
        total_domain = 0

        for coll in collections:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing: {coll}")
            logger.info(f"{'=' * 60}")

            # Get entities
            entities = await conn.fetch(
                """
                SELECT entity_id, entity_type, name
                FROM kg_nodes
                WHERE source_collection = $1
            """,
                coll,
            )

            entity_list = [
                {"id": row["entity_id"], "type": row["entity_type"], "name": row["name"]}
                for row in entities
            ]

            logger.info(f"Found {len(entity_list)} entities")

            # Step 1: Normalize names
            normalized_count = 0
            for entity in entity_list:
                normalized = normalize_entity_name(entity["name"], entity["type"])
                if normalized != entity["name"]:
                    normalized_count += 1
                    if not dry_run:
                        await conn.execute(
                            "UPDATE kg_nodes SET name = $1 WHERE entity_id = $2",
                            normalized,
                            entity["id"],
                        )
                    else:
                        if normalized_count <= 5:
                            logger.info(f"  [NORM] '{entity['name']}' → '{normalized}'")

            total_normalized += normalized_count
            logger.info(f"Normalized: {normalized_count} entities")

            # Step 2: Hierarchical relationships
            hierarchical = detect_hierarchical_relationships(entity_list)
            total_hierarchical += len(hierarchical)

            if not dry_run and hierarchical:
                for rel in hierarchical:
                    rel_id = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
                    try:
                        await conn.execute(
                            """
                            INSERT INTO kg_edges (
                                relationship_id, source_entity_id, target_entity_id,
                                relationship_type, properties, confidence,
                                source_collection, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                            ON CONFLICT DO NOTHING
                        """,
                            rel_id,
                            rel["source_id"],
                            rel["target_id"],
                            rel["type"],
                            f'{{"evidence": "{rel["evidence"]}"}}',
                            rel["confidence"],
                            coll,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert relation {rel_id}: {e}")
            else:
                for rel in hierarchical[:5]:
                    logger.info(
                        f"  [HIER] {rel['type']}: {rel['source_id'][:30]} → {rel['target_id'][:30]}"
                    )

            logger.info(f"Hierarchical: {len(hierarchical)} relationships")

            # Step 3: Domain rules for orphans
            orphan_ids = await conn.fetch(
                """
                SELECT entity_id FROM kg_nodes n
                WHERE n.source_collection = $1
                AND NOT EXISTS (
                    SELECT 1 FROM kg_edges e
                    WHERE e.source_entity_id = n.entity_id
                       OR e.target_entity_id = n.entity_id
                )
            """,
                coll,
            )

            orphan_id_set = {row["entity_id"] for row in orphan_ids}
            orphan_entities = [e for e in entity_list if e["id"] in orphan_id_set]

            logger.info(f"Orphans: {len(orphan_entities)}")

            # Use domain keywords as context
            context = "izin usaha perizinan dokumen persyaratan kbli klasifikasi biaya tarif jangka waktu berlaku"
            domain_rels = infer_domain_relationships(orphan_entities, context)
            total_domain += len(domain_rels)

            if not dry_run and domain_rels:
                for rel in domain_rels:
                    rel_id = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
                    try:
                        await conn.execute(
                            """
                            INSERT INTO kg_edges (
                                relationship_id, source_entity_id, target_entity_id,
                                relationship_type, properties, confidence,
                                source_collection, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                            ON CONFLICT DO NOTHING
                        """,
                            rel_id,
                            rel["source_id"],
                            rel["target_id"],
                            rel["type"],
                            f'{{"evidence": "{rel["evidence"]}"}}',
                            rel["confidence"],
                            coll,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert relation {rel_id}: {e}")
            else:
                for rel in domain_rels[:5]:
                    logger.info(
                        f"  [DOMAIN] {rel['type']}: {rel['source_id'][:30]} → {rel['target_id'][:30]}"
                    )

            logger.info(f"Domain rules: {len(domain_rels)} relationships")

        # Final summary
        logger.info(f"\n{'=' * 60}")
        logger.info("ENHANCEMENT SUMMARY")
        logger.info(f"{'=' * 60}")
        logger.info(f"Entities normalized: {total_normalized}")
        logger.info(f"Hierarchical relations: {total_hierarchical}")
        logger.info(f"Domain relations: {total_domain}")

        if dry_run:
            logger.info("\nDRY RUN - No changes made. Use --apply to apply changes.")
        else:
            # Final stats
            total_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
            total_edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
            orphans = await conn.fetchval("""
                SELECT COUNT(*) FROM kg_nodes n
                WHERE NOT EXISTS (
                    SELECT 1 FROM kg_edges e
                    WHERE e.source_entity_id = n.entity_id
                       OR e.target_entity_id = n.entity_id
                )
            """)

            logger.info(f"\nFinal KG: {total_nodes} nodes, {total_edges} edges")
            logger.info(f"Orphan rate: {orphans * 100 / total_nodes:.1f}%")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Advanced KG Enhancement")
    parser.add_argument("--collection", type=str, help="Specific collection to enhance")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed")

    args = parser.parse_args()

    dry_run = not args.apply or args.dry_run

    await run_enhancement(
        collection=args.collection,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    asyncio.run(main())
