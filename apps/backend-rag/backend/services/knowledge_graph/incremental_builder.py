"""
Knowledge Graph Incremental Builder Service
Integrates with AutonomousScheduler for automatic incremental KG updates
"""

import asyncio
import logging
from typing import Any

import asyncpg

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class KGIncrementalBuilder:
    """
    Service for incremental knowledge graph building from Qdrant collections.

    Features:
    - Tracks processed chunks via source_chunk_ids
    - Processes only new/modified chunks
    - Uses Gemini via Google AI Studio (cost-effective)
    - Robust error handling with retry
    """

    # High priority collections to process
    HIGH_PRIORITY_COLLECTIONS = [
        "legal_unified_hybrid",
        "kbli_2025_final",
        "tax_genius_hybrid",
        "visa_oracle",
        "balizero_news",  # Intel articles, news
    ]

    # Google AI Studio Free Tier Limits
    MAX_CHUNKS_PER_RUN = 1500  # Daily limit: 1,500 requests per day
    MAX_RPM = 15  # Rate limit: 15 requests per minute

    def __init__(self, db_pool: asyncpg.Pool | None = None) -> None:
        """
        Initialize KG Incremental Builder.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        self._gemini_client: Any | None = None

    def _get_gemini_client(self) -> Any | None:
        """Get or create Gemini client using Google AI Studio"""
        if self._gemini_client is None:
            try:
                from google import genai

                # Use GOOGLE_API_KEY (Google AI Studio)
                api_key = (
                    settings.google_api_key
                    or settings.google_ai_studio_key
                    or settings.google_imagen_api_key
                )

                if not api_key:
                    logger.warning("⚠️ GOOGLE_API_KEY not set - KG extraction will be skipped")
                    return None

                # Initialize with Google AI Studio API key
                self._gemini_client = genai.Client(api_key=api_key)
                logger.info(
                    f"✅ Gemini client initialized with Google AI Studio (API key: {api_key[:10]}...)",
                )
            except ImportError:
                logger.warning("⚠️ google-genai SDK not available")
                return None
            except Exception as e:
                logger.error("❌ Failed to initialize Gemini client: %s", e)
                return None

        return self._gemini_client

    async def get_processed_chunk_ids(self) -> set[str]:
        """Get all chunk IDs already processed in KG"""
        if not self.db_pool:
            return set()

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT chunk_id
                    FROM (
                        SELECT unnest(source_chunk_ids) as chunk_id
                        FROM kg_nodes
                        WHERE source_chunk_ids IS NOT NULL
                            AND array_length(source_chunk_ids, 1) > 0
                        UNION ALL
                        SELECT unnest(source_chunk_ids) as chunk_id
                        FROM kg_edges
                        WHERE source_chunk_ids IS NOT NULL
                            AND array_length(source_chunk_ids, 1) > 0
                    ) combined
                    """,
                )
                chunk_ids = {row["chunk_id"] for row in rows if row["chunk_id"]}
                logger.info(f"Found {len(chunk_ids):,} already processed chunks")
                return chunk_ids
        except Exception as e:
            logger.error("Error fetching processed chunks: %s", e)
            return set()

    async def run_incremental_extraction(
        self,
        collections: list[str] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Run incremental KG extraction from Qdrant collections.

        Args:
            collections: List of collection names (defaults to HIGH_PRIORITY_COLLECTIONS)
            max_retries: Maximum retries per collection on error

        Returns:
            Statistics dictionary
        """
        if not self.db_pool:
            logger.warning("⚠️ Database pool not available - skipping KG extraction")
            return {"status": "skipped", "reason": "no_database"}

        collections = collections or self.HIGH_PRIORITY_COLLECTIONS

        # Import incremental extractor
        try:
            import os
            import sys
            from pathlib import Path

            # Resolve scripts directory relative to this file
            # This file: backend/services/knowledge_graph/incremental_builder.py
            # Target:    scripts/kg_incremental_extraction.py
            # Path:      ../../../../scripts (4 levels up from knowledge_graph/)
            this_file = Path(__file__).resolve()
            candidate_paths = [
                this_file.parent.parent.parent.parent / "scripts",  # backend-rag/scripts
                this_file.parent.parent.parent.parent.parent / "scripts",  # apps/scripts (fallback)
                Path(os.environ.get("BACKEND_RAG_ROOT", "")) / "scripts",  # env override
            ]

            scripts_path = None
            for candidate in candidate_paths:
                if candidate.exists() and (candidate / "kg_incremental_extraction.py").exists():
                    scripts_path = candidate
                    break

            if scripts_path is None:
                logger.error(
                    f"❌ kg_incremental_extraction.py not found. Tried: "
                    f"{[str(p) for p in candidate_paths]}",
                )
                return {"status": "error", "error": "kg_incremental_extraction.py not found"}

            if str(scripts_path) not in sys.path:
                sys.path.insert(0, str(scripts_path))

            from kg_incremental_extraction import KGIncrementalExtractor

            logger.info("✅ KGIncrementalExtractor loaded from %s", scripts_path)
        except ImportError as e:
            logger.error("❌ Failed to import KGIncrementalExtractor: %s", e)
            logger.error("   Scripts path resolved: %s", scripts_path)
            return {"status": "error", "error": str(e)}

        # Get Gemini client
        gemini_client = self._get_gemini_client()
        if not gemini_client:
            logger.warning("⚠️ Gemini client not available - skipping KG extraction")
            return {"status": "skipped", "reason": "no_gemini_client"}

        # Initialize extractor
        try:
            # Ensure Qdrant settings are available
            qdrant_url = getattr(settings, "qdrant_url", None) or os.environ.get("QDRANT_URL")
            qdrant_api_key = (
                getattr(settings, "qdrant_api_key", None) or os.environ.get("QDRANT_API_KEY") or ""
            )

            if not qdrant_url:
                logger.error("❌ QDRANT_URL not configured")
                return {"status": "error", "error": "QDRANT_URL not configured"}

            extractor = KGIncrementalExtractor(
                db_pool=self.db_pool,
                qdrant_url=qdrant_url,
                qdrant_api_key=qdrant_api_key,
                gemini_client=gemini_client,
            )
        except Exception as e:
            logger.error("❌ Failed to initialize KGIncrementalExtractor: %s", e)
            return {"status": "error", "error": str(e)}

        # Process each collection with retry
        total_stats = {
            "collections_processed": 0,
            "collections_failed": 0,
            "total_chunks": 0,
            "total_entities": 0,
            "total_relationships": 0,
            "errors": [],
        }

        # Limit total chunks to respect free tier daily limit
        max_chunks_remaining = self.MAX_CHUNKS_PER_RUN

        for collection in collections:
            if max_chunks_remaining <= 0:
                logger.warning(
                    f"⚠️ Daily limit reached ({self.MAX_CHUNKS_PER_RUN} chunks). "
                    f"Skipping remaining collections.",
                )
                break

            logger.info(
                "🕸️ Processing collection: %s (remaining daily quota: %s chunks)",
                collection,
                max_chunks_remaining,
            )

            for attempt in range(max_retries):
                try:
                    # Run extraction for this collection with limit
                    stats = await extractor.run(
                        collections=[collection],
                        limit=max_chunks_remaining,  # Limit to remaining daily quota
                        dry_run=False,
                    )

                    chunks_this_run = stats.get("chunks_processed", 0)
                    total_stats["collections_processed"] += 1
                    total_stats["total_chunks"] += chunks_this_run
                    total_stats["total_entities"] += stats.get("entities_extracted", 0)
                    total_stats["total_relationships"] += stats.get("relationships_extracted", 0)
                    max_chunks_remaining -= chunks_this_run

                    logger.info(
                        f"✅ {collection}: {chunks_this_run} chunks, "
                        f"{stats.get('entities_extracted', 0)} entities, "
                        f"{stats.get('relationships_extracted', 0)} relationships "
                        f"(remaining: {max_chunks_remaining} chunks)",
                    )
                    # Rate limit: wait between collections to respect MAX_RPM
                    await asyncio.sleep(60.0 / self.MAX_RPM)
                    break  # Success, move to next collection

                except Exception as e:
                    error_msg = f"{collection} (attempt {attempt + 1}/{max_retries}): {e}"
                    logger.error("❌ Error processing %s", error_msg)

                    if attempt == max_retries - 1:
                        # Last attempt failed
                        total_stats["collections_failed"] += 1
                        total_stats["errors"].append(error_msg)
                        logger.error(
                            "❌ Failed to process %s after %s attempts",
                            collection,
                            max_retries,
                        )
                    else:
                        # Retry with exponential backoff
                        wait_time = 2**attempt
                        logger.info("⏳ Retrying %s in %ss...", collection, wait_time)
                        await asyncio.sleep(wait_time)

        logger.info(
            f"🕸️ KG Incremental Extraction Complete: "
            f"{total_stats['collections_processed']}/{len(collections)} collections, "
            f"{total_stats['total_chunks']:,} chunks, "
            f"{total_stats['total_entities']:,} entities, "
            f"{total_stats['total_relationships']:,} relationships",
        )

        return total_stats


async def run_knowledge_graph_incremental_build(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Main function for scheduled KG incremental build.

    This function is called by AutonomousScheduler every 24 hours.

    Args:
        db_pool: Database connection pool

    Returns:
        Statistics dictionary
    """
    builder = KGIncrementalBuilder(db_pool=db_pool)
    return await builder.run_incremental_extraction()


# ---------------------------------------------------------------------------
# Live init path (service_initializer §10f) — scheduler-necropsy 2026-07-14.
# The AutonomousScheduler is dead in prod AND ENABLE_KG_INCREMENTAL was never
# set on Fly, so this feeder was doubly unarmed: KG frozen at 88k processed
# chunks while collections kept growing (W90 freshness drift). Same pattern
# as the WhatsApp guardian §10d: standalone loop, scheduler's own Redis lock
# key for dedupe, verdict persisted to system_settings (disk=store, chat=view).
# ---------------------------------------------------------------------------


async def _persist_kg_verdict(db_pool: asyncpg.Pool, stats: dict[str, Any]) -> None:
    """Upsert the last-run verdict so liveness is a DB probe, not a log grep."""
    import json
    from datetime import datetime, timezone

    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "status": stats.get("status", "ok"),
        "collections_processed": stats.get("collections_processed"),
        "total_chunks": stats.get("total_chunks"),
        "total_entities": stats.get("total_entities"),
        "total_relationships": stats.get("total_relationships"),
        "errors": (stats.get("errors") or [])[:5],
    }
    await db_pool.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ('kg_incremental_last', $1, now())
        ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = now()
        """,
        json.dumps(payload),
    )


async def _kg_incremental_loop(db_pool: asyncpg.Pool, interval_seconds: int) -> None:
    """Daily incremental KG extraction on the live path."""
    from backend.services.misc.autonomous_scheduler import _acquire_task_lock

    await asyncio.sleep(120)  # let the app finish booting before Qdrant scans
    while True:
        try:
            if await _acquire_task_lock("kg_incremental_builder", interval_seconds):
                stats = await run_knowledge_graph_incremental_build(db_pool)
                try:
                    await _persist_kg_verdict(db_pool, stats)
                except Exception as e:
                    logger.error("[kg-incremental] verdict persist failed: %s", e)
            else:
                logger.debug("[kg-incremental] another worker holds the lock")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the loop must survive anything
            logger.error("[kg-incremental] run crashed: %s", e, exc_info=True)
        await asyncio.sleep(interval_seconds)


def start_kg_incremental_task(
    db_pool: asyncpg.Pool | None,
    interval_seconds: int = 86400,
) -> asyncio.Task | None:
    """Spawn the KG incremental loop on the running event loop (kill-switch aware).

    Default ON: the free-tier caps are enforced in-code (MAX_CHUNKS_PER_RUN,
    MAX_RPM) and extraction is dedup-idempotent via processed chunk ids, so
    an armed default is safe; ENABLE_KG_INCREMENTAL=false is the kill switch.
    """
    import os

    if os.environ.get("ENABLE_KG_INCREMENTAL", "true").lower() in {"false", "0", "no"}:
        logger.info("[kg-incremental] disabled via ENABLE_KG_INCREMENTAL")
        return None
    if db_pool is None:
        logger.warning("[kg-incremental] no db_pool — loop not started")
        return None
    task = asyncio.get_event_loop().create_task(
        _kg_incremental_loop(db_pool, interval_seconds), name="kg_incremental_builder"
    )
    logger.info(
        "✅ KG incremental builder loop started (%dh interval, Gemini free tier caps)",
        interval_seconds // 3600,
    )
    return task
