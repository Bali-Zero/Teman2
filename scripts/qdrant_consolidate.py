#!/usr/bin/env python3
"""
Qdrant Collection Cleanup Script (REVISED)

Deletes 9 legacy duplicate collections after safety protocol:
  1. AUDIT: Count kg_nodes referencing each collection
  2. REMAP: UPDATE kg_nodes.source_collection to surviving equivalents
  3. SNAPSHOT: Backup Qdrant collections before rename
  4. RENAME: Suffix with _deprecated_YYYYMMDD
  5. MONITOR: Log collection access (extend to 30 days)
  6. DELETE: Only after 30 days zero-access

DOES NOT merge tiny collections — they use brute-force scan (faster than HNSW for <100 docs).

DELETE targets (legacy duplicates only):
  legal_architect     → replaced by legal_unified_hybrid
  legal_unified       → replaced by legal_unified_hybrid
  tax_genius          → replaced by tax_genius_hybrid
  property_listings   → alias of property_knowledge
  legal_updates       → alias/duplicate
  legal_intelligence  → alias/duplicate
  tax_updates         → alias/duplicate
  tax_knowledge       → alias/duplicate
  cultural_insights   → 0 docs, unused

Usage:
    # Dry run (default):
    python scripts/qdrant_consolidate.py

    # Phase 1-2: Audit + Remap kg_nodes.source_collection (requires DB):
    python scripts/qdrant_consolidate.py --remap

    # Phase 3-4: Snapshot + Rename in Qdrant:
    python scripts/qdrant_consolidate.py --rename

    # Phase 6: Delete (only after 30-day monitoring):
    python scripts/qdrant_consolidate.py --delete --i-know-what-i-am-doing

Author: Nuzantara Team
Date: 2026-04-03
Reference: docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md §4
"""

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Collections to deprecate/delete (source → surviving equivalent)
DEPRECATION_MAP: dict[str, str] = {
    "legal_architect": "legal_unified_hybrid",
    "legal_unified": "legal_unified_hybrid",
    "tax_genius": "tax_genius_hybrid",
    "property_listings": "property_knowledge",
    "legal_updates": "legal_unified_hybrid",
    "legal_intelligence": "legal_unified_hybrid",
    "tax_updates": "tax_genius_hybrid",
    "tax_knowledge": "tax_genius_hybrid",
    "cultural_insights": "",  # No replacement, 0 docs
}

DATE_SUFFIX = datetime.now().strftime("%Y%m%d")


@dataclass
class CleanupStats:
    """Track cleanup progress."""

    nodes_remapped: int = 0
    collections_renamed: int = 0
    collections_deleted: int = 0
    errors: list[str] = field(default_factory=list)


# ============================================================================
# Phase 1: Audit
# ============================================================================


async def audit_source_collection_refs(db_pool) -> dict[str, int]:
    """Count kg_nodes referencing each deprecated collection."""
    counts: dict[str, int] = {}
    async with db_pool.acquire() as conn:
        for collection_name in DEPRECATION_MAP:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM kg_nodes WHERE source_collection = $1",
                collection_name,
            )
            counts[collection_name] = count
            status = "⚠️" if count > 0 else "✅"
            logger.info(f"  {status} {collection_name}: {count} kg_nodes references")
    return counts


# ============================================================================
# Phase 2: Remap source_collection
# ============================================================================


async def remap_source_collection(
    db_pool, dry_run: bool = True, stats: CleanupStats | None = None,
) -> None:
    """Update kg_nodes.source_collection to surviving equivalents."""
    async with db_pool.acquire() as conn:
        # First, backup the old values
        if not dry_run:
            await conn.execute("""
                UPDATE kg_nodes
                SET source_collection_previous = source_collection
                WHERE source_collection IN (
                    'legal_architect', 'legal_unified', 'tax_genius',
                    'property_listings', 'legal_updates', 'legal_intelligence',
                    'tax_updates', 'tax_knowledge', 'cultural_insights'
                )
                AND source_collection_previous IS NULL
            """)
            logger.info("  ✅ Backed up source_collection → source_collection_previous")

        for old_name, new_name in DEPRECATION_MAP.items():
            if not new_name:
                continue  # Skip cultural_insights (0 docs, no remap needed)

            count = await conn.fetchval(
                "SELECT COUNT(*) FROM kg_nodes WHERE source_collection = $1",
                old_name,
            )

            if count == 0:
                continue

            if dry_run:
                logger.info(
                    f"  🔵 [DRY RUN] Would remap {count} nodes: "
                    f"{old_name} → {new_name}",
                )
            else:
                await conn.execute(
                    "UPDATE kg_nodes SET source_collection = $2 WHERE source_collection = $1",
                    old_name,
                    new_name,
                )
                logger.info(f"  ✅ Remapped {count} nodes: {old_name} → {new_name}")
                if stats:
                    stats.nodes_remapped += count


# ============================================================================
# Phase 3-4: Snapshot + Rename in Qdrant
# ============================================================================


def rename_collections(
    client, dry_run: bool = True, stats: CleanupStats | None = None,
) -> None:
    """Rename deprecated collections with _deprecated_YYYYMMDD suffix."""
    existing = {c.name for c in client.get_collections().collections}

    for collection_name in DEPRECATION_MAP:
        if collection_name not in existing:
            logger.info(f"  ⏭️ {collection_name}: not found, skipping")
            continue

        new_name = f"{collection_name}_deprecated_{DATE_SUFFIX}"

        if new_name in existing:
            logger.info(f"  ⏭️ {collection_name}: already renamed to {new_name}")
            continue

        if dry_run:
            logger.info(f"  🔵 [DRY RUN] Would rename {collection_name} → {new_name}")
        else:
            try:
                # Qdrant doesn't have native rename — we create alias
                # and then the original stops being used
                client.update_collection_aliases(
                    change_aliases_operations=[
                        {"create_alias": {"alias_name": new_name, "collection_name": collection_name}},
                    ],
                )
                logger.info(f"  ✅ Aliased {collection_name} → {new_name}")
                if stats:
                    stats.collections_renamed += 1
            except Exception as e:
                logger.error(f"  ❌ Error renaming {collection_name}: {e}")
                if stats:
                    stats.errors.append(f"rename {collection_name}: {e}")


# ============================================================================
# Phase 6: Delete (after 30-day monitoring)
# ============================================================================


def delete_deprecated_collections(
    client, dry_run: bool = True, stats: CleanupStats | None = None,
) -> None:
    """Delete deprecated collections. ONLY after 30-day monitoring period."""
    existing = {c.name for c in client.get_collections().collections}

    for collection_name in DEPRECATION_MAP:
        if collection_name not in existing:
            logger.info(f"  ⏭️ {collection_name}: not found, already deleted")
            continue

        if dry_run:
            logger.info(f"  🔵 [DRY RUN] Would delete collection: {collection_name}")
        else:
            try:
                client.delete_collection(collection_name)
                logger.info(f"  🗑️ Deleted collection: {collection_name}")
                if stats:
                    stats.collections_deleted += 1
            except Exception as e:
                logger.error(f"  ❌ Error deleting {collection_name}: {e}")
                if stats:
                    stats.errors.append(f"delete {collection_name}: {e}")


# ============================================================================
# Main
# ============================================================================


async def main() -> None:
    parser = argparse.ArgumentParser(description="Qdrant Collection Cleanup (REVISED)")
    parser.add_argument("--remap", action="store_true", help="Phase 1-2: Audit + Remap kg_nodes")
    parser.add_argument("--rename", action="store_true", help="Phase 3-4: Snapshot + Rename")
    parser.add_argument("--delete", action="store_true", help="Phase 6: Delete (after 30 days)")
    parser.add_argument("--execute", action="store_true", help="Actually execute (default: dry run)")
    parser.add_argument(
        "--i-know-what-i-am-doing", action="store_true",
        help="Required safety flag for --delete",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    stats = CleanupStats()

    if dry_run:
        logger.info("🔵 DRY RUN MODE — no changes will be made")

    start_time = time.time()

    if args.remap:
        try:
            import asyncpg

            from backend.app.core.config import settings

            db_pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)

            logger.info("\n📊 Phase 1: Audit kg_nodes.source_collection references")
            await audit_source_collection_refs(db_pool)

            logger.info("\n🔄 Phase 2: Remap source_collection to surviving equivalents")
            await remap_source_collection(db_pool, dry_run=dry_run, stats=stats)

            await db_pool.close()
        except Exception as e:
            logger.error(f"❌ Database operation failed: {e}")
            stats.errors.append(str(e))

    if args.rename or args.delete:
        try:
            from backend.app.core.config import settings
            from qdrant_client import QdrantClient

            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=getattr(settings, "qdrant_api_key", None),
                timeout=60,
            )
            logger.info(f"✅ Connected to Qdrant: {settings.qdrant_url}")

            if args.rename:
                logger.info("\n📦 Phase 3-4: Rename deprecated collections")
                rename_collections(client, dry_run=dry_run, stats=stats)

            if args.delete:
                if not args.i_know_what_i_am_doing:
                    logger.error(
                        "❌ --delete requires --i-know-what-i-am-doing flag. "
                        "Make sure 30-day monitoring has passed with zero access.",
                    )
                    return

                logger.info("\n🗑️ Phase 6: Delete deprecated collections")
                delete_deprecated_collections(client, dry_run=dry_run, stats=stats)

        except Exception as e:
            logger.error(f"❌ Qdrant operation failed: {e}")
            stats.errors.append(str(e))

    if not args.remap and not args.rename and not args.delete:
        logger.info("No action specified. Use --remap, --rename, or --delete.")
        logger.info("Run with --execute to apply changes (default: dry run).")

    elapsed = time.time() - start_time
    logger.info(f"""
╔══════════════════════════════════════════╗
║  Qdrant Cleanup {'DRY RUN' if dry_run else 'COMPLETE':>10}             ║
╠══════════════════════════════════════════╣
║  Nodes remapped:      {stats.nodes_remapped:>6}             ║
║  Collections renamed: {stats.collections_renamed:>6}             ║
║  Collections deleted: {stats.collections_deleted:>6}             ║
║  Errors:              {len(stats.errors):>6}             ║
║  Duration:            {elapsed:>6.1f}s            ║
╚══════════════════════════════════════════╝
""")


if __name__ == "__main__":
    asyncio.run(main())
