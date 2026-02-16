#!/usr/bin/env python3
"""
Nuzantara Knowledge Graph Cleanup Script

Phase 1.5: Normalize relationship types + handle orphan nodes

Operations:
1. Normalize relationship_type values to canonical UPPERCASE_SNAKE_CASE
2. Merge semantically equivalent relationship types
3. Map Indonesian-language types to English canonical equivalents
4. Report and optionally remove low-value orphan nodes

Usage:
    python scripts/maintenance/kg_cleanup.py --dry-run    # Preview changes
    python scripts/maintenance/kg_cleanup.py              # Apply changes
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# NORMALIZATION MAPPING
# ============================================================
# Maps non-canonical relationship types → canonical types
# Based on ontology.py (58 canonical types)
# ============================================================

RELATIONSHIP_NORMALIZATION: dict[str, str] = {
    # --- Case normalization ---
    "requires": "REQUIRES",

    # --- Indonesian → English ---
    "TENTANG": "REFERENCES",           # "about"
    "MENGESAHKAN": "AUTHORIZES",       # "ratifies"
    "MEMPERTIMBANGKAN": "REFERENCES",  # "considers"
    "MENETAPKAN": "DEFINES",           # "establishes/determines"
    "MELIBATKAN": "RELATED_TO",        # "involves"
    "MENANGANI": "RELATED_TO",         # "handles"
    "TERJADI_DI": "LOCATED_IN",        # "occurs at"
    "MENERIMA_USULAN_DARI": "RELATED_TO",  # "receives proposal from"
    "MENGANGKAT": "AUTHORIZES",        # "appoints"
    "MENGUSULKAN": "RELATED_TO",       # "proposes"
    "KEWENANGAN": "AUTHORIZED_BY",     # "authority"

    # --- Semantic deduplication (low-count → canonical) ---
    "SUPERSEDES": "REPLACES",          # 385 → canonical REPLACES
    "REQUIREMENT_OF": "REQUIRES",      # 250 → canonical REQUIRES
    "CROSS_REFERENCES": "REFERENCES",  # 228 → canonical REFERENCES
    "BLOCKS_IF_MISSING": "BLOCKED_BY", # 93 → canonical BLOCKED_BY
    "COVERED_BY": "REGULATED_BY",      # 15 → canonical REGULATED_BY
    "NEXT_STEP": "HAS_PROCEDURE",      # 13 → canonical HAS_PROCEDURE
    "PRODUCES": "RESULTS_IN",          # 10 → canonical RESULTS_IN
    "HAS": "CONTAINS",                 # 7 → canonical CONTAINS
    "STARTS_WITH": "HAS_PROCEDURE",    # 2
    "RECOMMENDS": "RELATED_TO",        # 2
    "CONSULTS": "RELATED_TO",          # 2
    "HAS_PROPERTY": "CONTAINS",        # 2
    "LEADS_TO": "RESULTS_IN",          # 2
    "ISSUES": "ISSUED_BY",             # 1
    "INVOLVES": "RELATED_TO",          # 1
    "PAYS": "HAS_FEE",                 # 1
    "INVESTIGATES": "RELATED_TO",      # 1
    "PROBES": "RELATED_TO",            # 1
    "HAS_OBJECTIVE": "RELATED_TO",     # 1
    "GOVERNED_BY": "REGULATED_BY",     # 1
    "REGULATES": "REGULATED_BY",       # 1
    "ESTABLISHED_IN": "LOCATED_IN",    # 1
    "DESCRIPTION": "RELATED_TO",       # 1 (noise)
    "CONVERTS_TO": "ENABLES",          # 1
    "CATEGORY": "CLASSIFIED_AS",       # 1
    "SPONSORED_BY": "AUTHORIZED_BY",   # 1
    "ALTERNATIVE_TO": "SIMILAR_TO",    # 1
    "ALIAS": "SAME_AS",               # 1
    "TREATS": "RELATED_TO",           # 1
    "UPGRADES_TO": "ENABLES",         # 1
    "AFTER": "PREREQUISITE_FOR",      # 1
    "LINKED_TO": "RELATED_TO",        # 1
    "MANAGES": "AUTHORIZED_BY",       # 1
}

# Types that are canonical and should NOT be touched
# (All 58 from ontology.py + reasonable extras with high counts)
CANONICAL_TYPES: set[str] = {
    # From ontology.py
    "PART_OF", "CONTAINS", "AMENDS", "REVOKES", "IMPLEMENTS",
    "REFERENCES", "REPLACES", "DERIVES_FROM",
    "REQUIRES", "PREREQUISITE_FOR", "DEPENDS_ON", "ENABLES",
    "ISSUED_BY", "ISSUED_TO", "AUTHORIZED_BY", "REGULATED_BY",
    "HAS_PROCEDURE", "HAS_REQUIREMENT", "HAS_DOCUMENT", "HAS_FEE",
    "HAS_DURATION", "HAS_VALIDITY",
    "APPLIES_TO", "EXEMPTS", "RESTRICTS", "PERMITS", "PROHIBITS",
    "VIOLATES", "PENALTY_FOR", "RESULTS_IN",
    "TAX_OBLIGATION", "TAX_RATE", "TAX_EXEMPT",
    "CLASSIFIED_AS", "BELONGS_TO",
    "LOCATED_IN", "JURISDICTION",
    "BLOCKED_BY", "ALLOWED_IF",
    "RELATED_TO", "SAME_AS", "SIMILAR_TO",
    "AUTHORIZES", "DEFINES",
    # High-count types not in ontology but semantically valid
    "REQUIRED_FOR",      # 8,000 - inverse of REQUIRES
    "DURATION_OF",       # 4,486 - inverse of HAS_DURATION
    "SECTOR_OF",         # 1,000 - inverse of BELONGS_TO
    "POSITION_FOR",      # 1,000 - specific employment context
    "CLASSIFIES",        # 1,000 - inverse of CLASSIFIED_AS
    "OPERATES_IN",       # 500 - business location context
    "CAUSES",            # 500 - causal
    "HOLDS",             # 500 - possession
    "GRANTS",            # 113 - permission granting
    "CAPITAL_OF",        # 110 - investment context
}


@dataclass
class CleanupStats:
    """Track cleanup operations."""
    edges_normalized: int = 0
    edges_by_mapping: dict[str, int] = field(default_factory=dict)
    orphans_found: int = 0
    orphans_removed: int = 0
    duplicate_edges_removed: int = 0
    errors: int = 0


async def normalize_relationships(
    pool: Any,
    dry_run: bool = True,
    stats: CleanupStats | None = None,
) -> CleanupStats:
    """Normalize relationship types to canonical UPPERCASE_SNAKE_CASE."""
    if stats is None:
        stats = CleanupStats()

    logger.info("=" * 60)
    logger.info("STEP 1: Relationship Type Normalization")
    logger.info("=" * 60)

    # Get current distribution
    rows = await pool.fetch(
        "SELECT relationship_type, COUNT(*) as cnt FROM kg_edges GROUP BY relationship_type ORDER BY cnt DESC"
    )

    total_edges = sum(r["cnt"] for r in rows)
    logger.info(f"Total edges: {total_edges:,}")
    logger.info(f"Distinct relationship types: {len(rows)}")

    # Identify edges to normalize
    to_normalize: list[tuple[str, str, int]] = []  # (old, new, count)
    already_canonical: list[tuple[str, int]] = []
    unknown: list[tuple[str, int]] = []

    for row in rows:
        rel_type = row["relationship_type"]
        count = row["cnt"]

        if rel_type in RELATIONSHIP_NORMALIZATION:
            target = RELATIONSHIP_NORMALIZATION[rel_type]
            to_normalize.append((rel_type, target, count))
        elif rel_type in CANONICAL_TYPES:
            already_canonical.append((rel_type, count))
        else:
            unknown.append((rel_type, count))

    logger.info(f"\nCanonical (no change needed): {len(already_canonical)} types, "
                f"{sum(c for _, c in already_canonical):,} edges")
    logger.info(f"To normalize: {len(to_normalize)} types, "
                f"{sum(c for _, _, c in to_normalize):,} edges")
    if unknown:
        logger.info(f"Unknown (not in mapping or canonical): {len(unknown)} types")
        for rel_type, count in unknown:
            logger.warning(f"  UNKNOWN: {rel_type} ({count:,} edges) - will be left as-is")

    # Apply normalizations
    if to_normalize:
        logger.info("\nNormalization plan:")
        for old_type, new_type, count in sorted(to_normalize, key=lambda x: -x[2]):
            logger.info(f"  {old_type} → {new_type} ({count:,} edges)")

        if not dry_run:
            logger.info("\nApplying normalizations...")
            for old_type, new_type, count in to_normalize:
                # Update relationship_type
                result = await pool.execute(
                    "UPDATE kg_edges SET relationship_type = $1 WHERE relationship_type = $2",
                    new_type, old_type,
                )
                affected = int(result.split(" ")[-1])
                stats.edges_normalized += affected
                stats.edges_by_mapping[f"{old_type} → {new_type}"] = affected
                logger.info(f"  ✅ {old_type} → {new_type}: {affected:,} edges updated")

                # Also update relationship_id to reflect new type
                await pool.execute(
                    """
                    UPDATE kg_edges
                    SET relationship_id = source_entity_id || '__' || LOWER(REPLACE($1, ' ', '_')) || '__' || target_entity_id
                    WHERE relationship_type = $1
                      AND relationship_id LIKE '%__' || LOWER(REPLACE($2, ' ', '_')) || '__%'
                    """,
                    new_type, old_type,
                )
        else:
            stats.edges_normalized = sum(c for _, _, c in to_normalize)
            for old_type, new_type, count in to_normalize:
                stats.edges_by_mapping[f"{old_type} → {new_type}"] = count

    return stats


async def remove_duplicate_edges(
    pool: Any,
    dry_run: bool = True,
    stats: CleanupStats | None = None,
) -> CleanupStats:
    """Remove duplicate edges that may have been created by normalization."""
    if stats is None:
        stats = CleanupStats()

    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Duplicate Edge Removal (post-normalization)")
    logger.info("=" * 60)

    # Find duplicates: same source + target + type, keep the one with highest confidence
    dupes = await pool.fetch(
        """
        SELECT source_entity_id, target_entity_id, relationship_type, COUNT(*) as cnt
        FROM kg_edges
        GROUP BY source_entity_id, target_entity_id, relationship_type
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        """
    )

    total_dupes = sum(r["cnt"] - 1 for r in dupes)  # -1 because we keep one
    logger.info(f"Duplicate edge groups: {len(dupes)}")
    logger.info(f"Total edges to deduplicate: {total_dupes:,}")

    if dupes and not dry_run:
        logger.info("Removing duplicates (keeping highest confidence)...")
        removed = 0
        for row in dupes:
            # Keep the edge with highest confidence (or most recent)
            result = await pool.execute(
                """
                DELETE FROM kg_edges
                WHERE ctid NOT IN (
                    SELECT ctid FROM kg_edges
                    WHERE source_entity_id = $1
                      AND target_entity_id = $2
                      AND relationship_type = $3
                    ORDER BY COALESCE(confidence, 0) DESC, created_at DESC NULLS LAST
                    LIMIT 1
                )
                AND source_entity_id = $1
                AND target_entity_id = $2
                AND relationship_type = $3
                """,
                row["source_entity_id"],
                row["target_entity_id"],
                row["relationship_type"],
            )
            removed += int(result.split(" ")[-1])
        stats.duplicate_edges_removed = removed
        logger.info(f"  ✅ Removed {removed:,} duplicate edges")
    else:
        stats.duplicate_edges_removed = total_dupes

    return stats


async def analyze_orphan_nodes(
    pool: Any,
    dry_run: bool = True,
    stats: CleanupStats | None = None,
) -> CleanupStats:
    """Analyze and optionally remove low-value orphan nodes."""
    if stats is None:
        stats = CleanupStats()

    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: Orphan Node Analysis")
    logger.info("=" * 60)

    # Find orphan nodes (no edges at all)
    orphans = await pool.fetch(
        """
        SELECT n.entity_id, n.name, n.entity_type,
               LENGTH(COALESCE(n.description, '')) as desc_len
        FROM kg_nodes n
        LEFT JOIN kg_edges e_src ON n.entity_id = e_src.source_entity_id
        LEFT JOIN kg_edges e_tgt ON n.entity_id = e_tgt.target_entity_id
        WHERE e_src.source_entity_id IS NULL
          AND e_tgt.target_entity_id IS NULL
        ORDER BY n.entity_type, n.name
        """
    )

    stats.orphans_found = len(orphans)
    logger.info(f"Total orphan nodes: {len(orphans):,}")

    # Categorize orphans
    type_counts: dict[str, int] = {}
    low_value: list[dict[str, Any]] = []
    high_value: list[dict[str, Any]] = []

    for o in orphans:
        etype = o["entity_type"]
        type_counts[etype] = type_counts.get(etype, 0) + 1

        # Low value: very short/empty description AND generic type
        if o["desc_len"] < 20:
            low_value.append(dict(o))
        else:
            high_value.append(dict(o))

    logger.info("\nOrphan nodes by type:")
    for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {etype:30s} {count:,}")

    logger.info(f"\nLow-value orphans (desc < 20 chars): {len(low_value):,}")
    logger.info(f"High-value orphans (desc >= 20 chars): {len(high_value):,}")

    # Show sample high-value orphans (these should be CONNECTED, not deleted)
    if high_value:
        logger.info("\nSample high-value orphans (should be connected, not deleted):")
        for o in high_value[:10]:
            logger.info(f"  [{o['entity_type']}] {o['name'][:60]} (desc: {o['desc_len']} chars)")

    # Only remove truly low-value orphans
    if low_value:
        logger.info(f"\n{'Would remove' if dry_run else 'Removing'} {len(low_value):,} low-value orphan nodes...")
        if not dry_run:
            ids = [o["entity_id"] for o in low_value]
            # Batch delete in chunks of 500
            for i in range(0, len(ids), 500):
                batch = ids[i : i + 500]
                placeholders = ", ".join(f"${j+1}" for j in range(len(batch)))
                result = await pool.execute(
                    f"DELETE FROM kg_nodes WHERE entity_id IN ({placeholders})",
                    *batch,
                )
                removed = int(result.split(" ")[-1])
                stats.orphans_removed += removed
            logger.info(f"  ✅ Removed {stats.orphans_removed:,} low-value orphan nodes")
        else:
            stats.orphans_removed = len(low_value)

    logger.info(f"\n⚠️  {len(high_value):,} high-value orphans preserved for future edge creation")

    return stats


async def generate_final_report(pool: Any) -> None:
    """Generate post-cleanup verification report."""
    logger.info("\n" + "=" * 60)
    logger.info("POST-CLEANUP VERIFICATION REPORT")
    logger.info("=" * 60)

    # Counts
    node_count = await pool.fetchval("SELECT COUNT(*) FROM kg_nodes")
    edge_count = await pool.fetchval("SELECT COUNT(*) FROM kg_edges")

    connected = await pool.fetchval(
        """
        SELECT COUNT(DISTINCT entity_id) FROM (
            SELECT DISTINCT source_entity_id AS entity_id FROM kg_edges
            UNION
            SELECT DISTINCT target_entity_id AS entity_id FROM kg_edges
        ) sub
        """
    )

    orphan_count = node_count - connected
    connectivity = (connected / node_count * 100) if node_count > 0 else 0

    logger.info(f"Total nodes:     {node_count:,}")
    logger.info(f"Total edges:     {edge_count:,}")
    logger.info(f"Connected nodes: {connected:,} ({connectivity:.1f}%)")
    logger.info(f"Orphan nodes:    {orphan_count:,}")
    logger.info(f"Avg edges/node:  {edge_count / node_count:.1f}" if node_count > 0 else "N/A")

    # Relationship type distribution (post-cleanup)
    rows = await pool.fetch(
        "SELECT relationship_type, COUNT(*) as cnt FROM kg_edges GROUP BY relationship_type ORDER BY cnt DESC"
    )
    logger.info(f"\nRelationship types (post-cleanup): {len(rows)}")
    for row in rows:
        if row["cnt"] >= 10:  # Only show types with 10+ edges
            logger.info(f"  {row['relationship_type']:30s} {row['cnt']:,}")

    # Entity type distribution
    rows = await pool.fetch(
        "SELECT entity_type, COUNT(*) as cnt FROM kg_nodes GROUP BY entity_type ORDER BY cnt DESC LIMIT 20"
    )
    logger.info(f"\nEntity types (top 20):")
    for row in rows:
        logger.info(f"  {row['entity_type']:30s} {row['cnt']:,}")


async def main() -> None:
    """Main entry point."""
    dry_run = "--dry-run" in sys.argv

    logger.info("=" * 60)
    logger.info("NUZANTARA KNOWLEDGE GRAPH CLEANUP")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE CLEANUP'}")
    logger.info(f"Normalizations defined: {len(RELATIONSHIP_NORMALIZATION)}")
    logger.info(f"Canonical types: {len(CANONICAL_TYPES)}")

    if dry_run:
        logger.info("\n⚠️  DRY RUN - No changes will be made to the database")

    # Resolve DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip('"')
                    break

    if not db_url:
        raise ValueError(
            "DATABASE_URL not set. Use:\n"
            "  DATABASE_URL='postgres://...' python scripts/maintenance/kg_cleanup.py"
        )

    logger.info(f"Database: {db_url[:50]}...")

    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    stats = CleanupStats()

    try:
        # Step 1: Normalize relationship types
        stats = await normalize_relationships(pool, dry_run=dry_run, stats=stats)

        # Step 2: Remove duplicates created by normalization
        stats = await remove_duplicate_edges(pool, dry_run=dry_run, stats=stats)

        # Step 3: Handle orphan nodes
        stats = await analyze_orphan_nodes(pool, dry_run=dry_run, stats=stats)

        # Final report
        if not dry_run:
            await generate_final_report(pool)

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Edges normalized:    {stats.edges_normalized:,}")
        logger.info(f"Duplicates removed:  {stats.duplicate_edges_removed:,}")
        logger.info(f"Orphans found:       {stats.orphans_found:,}")
        logger.info(f"Orphans removed:     {stats.orphans_removed:,}")
        logger.info(f"Errors:              {stats.errors}")

        if stats.edges_by_mapping:
            logger.info("\nNormalization details:")
            for mapping, count in sorted(stats.edges_by_mapping.items(), key=lambda x: -x[1]):
                logger.info(f"  {mapping}: {count:,}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
