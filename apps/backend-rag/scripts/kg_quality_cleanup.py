#!/usr/bin/env python3
"""
Knowledge Graph Quality Cleanup Script

Cleans up existing KG data by:
1. Removing noise entities (short names, generic terms, OCR errors)
2. Fixing entity type misclassifications
3. Merging duplicates
4. Removing orphan nodes (optionally)

Usage:
    # Dry run (show what would be cleaned)
    python -m scripts.kg_quality_cleanup --dry-run

    # Run cleanup on specific collection
    python -m scripts.kg_quality_cleanup --collection legal_unified_hybrid

    # Full cleanup including orphan removal
    python -m scripts.kg_quality_cleanup --remove-orphans
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher

import asyncpg

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kg_cleanup")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# CLEANUP RULES
# ============================================================================

# Minimum name length
MIN_NAME_LENGTH = 4

# Noise terms to remove
NOISE_TERMS = {
    "dan",
    "atau",
    "yang",
    "dari",
    "untuk",
    "dengan",
    "dalam",
    "pada",
    "ini",
    "itu",
    "tersebut",
    "bahwa",
    "oleh",
    "ke",
    "di",
    "tidak",
    "dak",
    "dau",
    "dbh",
    "apbn",
    "apbd",
    "the",
    "and",
    "for",
    "with",
    "from",
    "tahun",
    "bulan",
    "hari",
    "writ",
    "film",
}

# Patterns for noise entities
NOISE_PATTERNS = [
    r"^[A-Z]{1,3}$",  # Single letters or very short acronyms
    r"^\d+$",  # Numbers only
    r"^[!@#$%^&*()]+$",  # Punctuation only
    r"^huruf\s+[a-z]$",  # "Huruf A", etc.
    r"perizina!",  # OCR error
]

# Entity type corrections
TYPE_CORRECTIONS = {
    ("dak", "undang_undang"): "biaya",
    ("dau", "undang_undang"): "biaya",
    ("dbh", "undang_undang"): "biaya",
    ("apbn", "undang_undang"): "biaya",
    ("apbd", "undang_undang"): "biaya",
}

# Specific entity types that need number/year validation
REGULATION_TYPES = {
    "undang_undang",
    "peraturan_pemerintah",
    "perpres",
    "permen",
    "perda",
    "surat_edaran",
}


@dataclass
class CleanupStats:
    """Cleanup statistics"""

    total_nodes: int = 0
    nodes_deleted: int = 0
    nodes_corrected: int = 0
    duplicates_merged: int = 0
    orphans_removed: int = 0
    edges_deleted: int = 0


async def get_db_pool() -> asyncpg.Pool:
    """Get database connection pool"""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return await asyncpg.create_pool(db_url, min_size=2, max_size=10)


def is_noise_entity(name: str, entity_type: str) -> tuple[bool, str]:
    """Check if entity is noise, return (is_noise, reason)"""
    name_lower = name.lower().strip()

    # Check minimum length
    if len(name) < MIN_NAME_LENGTH:
        return True, f"too_short ({len(name)} chars)"

    # Check noise terms
    if name_lower in NOISE_TERMS:
        return True, f"noise_term ({name_lower})"

    # Check noise patterns
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return True, f"noise_pattern ({pattern})"

    # Check for OCR errors
    if re.search(r"[!@#$%^&*()\[\]{}|\\<>]", name):
        return True, "ocr_error"

    # Check regulation types without numbers
    if entity_type in REGULATION_TYPES and not re.search(r"\d", name) and len(name) < 20:
        return True, "generic_regulation"

    return False, ""


def get_corrected_type(name: str, current_type: str) -> str | None:
    """Get corrected entity type, or None if no correction needed"""
    name_lower = name.lower().strip()

    for (term, from_type), to_type in TYPE_CORRECTIONS.items():
        if name_lower == term and current_type == from_type:
            return to_type

    return None


def similarity(a: str, b: str) -> float:
    """Calculate string similarity"""
    return SequenceMatcher(None, a.upper(), b.upper()).ratio()


async def find_duplicates(
    conn: asyncpg.Connection,
    collection: str | None,
    threshold: float = 0.9,
) -> list[tuple[str, str, str, str]]:
    """Find duplicate entities within same type"""
    query = """
        SELECT entity_id, entity_type, name
        FROM kg_nodes
    """
    if collection:
        query += f" WHERE source_collection = '{collection}'"
    query += " ORDER BY entity_type, name"

    rows = await conn.fetch(query)

    # Group by type
    by_type: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        by_type.setdefault(row["entity_type"], []).append((row["entity_id"], row["name"]))

    duplicates = []
    for _entity_type, entities in by_type.items():
        if len(entities) < 2:
            continue

        # Sort by name length (longer = canonical)
        entities = sorted(entities, key=lambda x: len(x[1]), reverse=True)

        used = set()
        for i, (id1, name1) in enumerate(entities):
            if id1 in used:
                continue

            for _j, (id2, name2) in enumerate(entities[i + 1 :], start=i + 1):
                if id2 in used:
                    continue

                sim = similarity(name1, name2)
                if sim >= threshold:
                    duplicates.append((id1, id2, name1, name2))
                    used.add(id2)

    return duplicates


async def run_cleanup(
    collection: str | None = None,
    dry_run: bool = True,
    remove_orphans: bool = False,
    merge_duplicates: bool = True,
) -> CleanupStats:
    """Run the cleanup process"""
    stats = CleanupStats()

    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Get nodes to analyze
            query = "SELECT entity_id, entity_type, name FROM kg_nodes"
            if collection:
                query += f" WHERE source_collection = '{collection}'"

            rows = await conn.fetch(query)
            stats.total_nodes = len(rows)
            logger.info(f"Analyzing {stats.total_nodes} nodes...")

            # Step 1: Identify noise entities
            noise_entities = []
            for row in rows:
                is_noise, reason = is_noise_entity(row["name"], row["entity_type"])
                if is_noise:
                    noise_entities.append((row["entity_id"], row["name"], reason))

            logger.info(f"Found {len(noise_entities)} noise entities to remove")

            if not dry_run and noise_entities:
                # Delete noise entities and their edges
                entity_ids = [e[0] for e in noise_entities]
                for eid in entity_ids:
                    await conn.execute(
                        "DELETE FROM kg_edges WHERE source_entity_id = $1 OR target_entity_id = $1",
                        eid,
                    )
                    await conn.execute(
                        "DELETE FROM kg_nodes WHERE entity_id = $1",
                        eid,
                    )
                    stats.nodes_deleted += 1
                logger.info(f"Deleted {stats.nodes_deleted} noise entities")
            else:
                # Log samples
                for eid, name, reason in noise_entities[:10]:
                    logger.info(f"  [NOISE] {name} - {reason}")
                if len(noise_entities) > 10:
                    logger.info(f"  ... and {len(noise_entities) - 10} more")

            # Step 2: Fix entity type misclassifications
            type_fixes = []
            for row in rows:
                corrected = get_corrected_type(row["name"], row["entity_type"])
                if corrected:
                    type_fixes.append(
                        (row["entity_id"], row["name"], row["entity_type"], corrected)
                    )

            logger.info(f"Found {len(type_fixes)} entity type corrections")

            if not dry_run and type_fixes:
                for eid, name, old_type, new_type in type_fixes:
                    await conn.execute(
                        "UPDATE kg_nodes SET entity_type = $1 WHERE entity_id = $2",
                        new_type,
                        eid,
                    )
                    stats.nodes_corrected += 1
                logger.info(f"Corrected {stats.nodes_corrected} entity types")
            else:
                for eid, name, old_type, new_type in type_fixes[:10]:
                    logger.info(f"  [FIX] {name}: {old_type} -> {new_type}")

            # Step 3: Find and merge duplicates
            if merge_duplicates:
                duplicates = await find_duplicates(conn, collection)
                logger.info(f"Found {len(duplicates)} duplicate pairs")

                if not dry_run and duplicates:
                    for canonical_id, dup_id, can_name, dup_name in duplicates:
                        # Update edges to point to canonical
                        await conn.execute(
                            "UPDATE kg_edges SET source_entity_id = $1 WHERE source_entity_id = $2",
                            canonical_id,
                            dup_id,
                        )
                        await conn.execute(
                            "UPDATE kg_edges SET target_entity_id = $1 WHERE target_entity_id = $2",
                            canonical_id,
                            dup_id,
                        )
                        # Delete duplicate node
                        await conn.execute(
                            "DELETE FROM kg_nodes WHERE entity_id = $1",
                            dup_id,
                        )
                        stats.duplicates_merged += 1
                    logger.info(f"Merged {stats.duplicates_merged} duplicates")
                else:
                    for _can_id, dup_id, can_name, dup_name in duplicates[:10]:
                        logger.info(f"  [DUP] '{dup_name}' -> '{can_name}'")

            # Step 4: Remove orphan nodes (optional)
            if remove_orphans:
                orphans = await conn.fetch(
                    """
                    SELECT n.entity_id, n.name, n.entity_type
                    FROM kg_nodes n
                    WHERE NOT EXISTS (
                        SELECT 1 FROM kg_edges e
                        WHERE e.source_entity_id = n.entity_id
                           OR e.target_entity_id = n.entity_id
                    )
                """
                    + (f" AND n.source_collection = '{collection}'" if collection else "")
                )

                logger.info(f"Found {len(orphans)} orphan nodes")

                if not dry_run and orphans:
                    for orphan in orphans:
                        await conn.execute(
                            "DELETE FROM kg_nodes WHERE entity_id = $1",
                            orphan["entity_id"],
                        )
                        stats.orphans_removed += 1
                    logger.info(f"Removed {stats.orphans_removed} orphan nodes")
                else:
                    # Log sample orphans by type
                    orphan_types: dict[str, int] = {}
                    for orphan in orphans:
                        orphan_types[orphan["entity_type"]] = (
                            orphan_types.get(orphan["entity_type"], 0) + 1
                        )
                    for etype, count in sorted(orphan_types.items(), key=lambda x: -x[1])[:10]:
                        logger.info(f"  [ORPHAN] {etype}: {count}")

            # Final stats
            if not dry_run:
                final_nodes = await conn.fetchval(
                    "SELECT COUNT(*) FROM kg_nodes"
                    + (f" WHERE source_collection = '{collection}'" if collection else "")
                )
                final_edges = await conn.fetchval(
                    "SELECT COUNT(*) FROM kg_edges"
                    + (f" WHERE source_collection = '{collection}'" if collection else "")
                )
                logger.info(f"\nFinal counts: {final_nodes} nodes, {final_edges} edges")

    finally:
        await pool.close()

    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Quality Cleanup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Specific collection to clean (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without making changes",
    )
    parser.add_argument(
        "--remove-orphans",
        action="store_true",
        help="Also remove orphan nodes (nodes without relationships)",
    )
    parser.add_argument(
        "--no-merge-duplicates",
        action="store_true",
        help="Skip duplicate merging",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Knowledge Graph Quality Cleanup")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    stats = await run_cleanup(
        collection=args.collection,
        dry_run=args.dry_run,
        remove_orphans=args.remove_orphans,
        merge_duplicates=not args.no_merge_duplicates,
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total nodes analyzed: {stats.total_nodes}")
    logger.info(
        f"Noise entities {'to delete' if args.dry_run else 'deleted'}: {stats.nodes_deleted}"
    )
    logger.info(
        f"Entity types {'to correct' if args.dry_run else 'corrected'}: {stats.nodes_corrected}"
    )
    logger.info(f"Duplicates {'to merge' if args.dry_run else 'merged'}: {stats.duplicates_merged}")
    logger.info(f"Orphans {'to remove' if args.dry_run else 'removed'}: {stats.orphans_removed}")

    if args.dry_run:
        logger.info("\nTo apply changes, run without --dry-run flag")


if __name__ == "__main__":
    asyncio.run(main())
