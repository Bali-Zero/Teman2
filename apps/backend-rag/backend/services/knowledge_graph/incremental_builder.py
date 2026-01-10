"""
Knowledge Graph Incremental Builder Service
Integrates with AutonomousScheduler for automatic incremental KG updates
"""

import asyncio
import logging
import os
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
        "kbli_unified",
        "tax_genius_hybrid",
        "visa_oracle",
        "balizero_news_history",  # news_history
    ]

    # Google AI Studio Free Tier Limits
    MAX_CHUNKS_PER_RUN = 1,500  # Daily limit: 1,500 requests per day
    MAX_RPM = 15  # Rate limit: 15 requests per minute

    def __init__(self, db_pool: asyncpg.Pool | None = None):
        """
        Initialize KG Incremental Builder.
        
        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        self._gemini_client = None

    def _get_gemini_client(self):
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
                    logger.warning(
                        "⚠️ GOOGLE_API_KEY not set - KG extraction will be skipped"
                    )
                    return None

                # Initialize with Google AI Studio API key
                self._gemini_client = genai.Client(api_key=api_key)
                logger.info(
                    f"✅ Gemini client initialized with Google AI Studio (API key: {api_key[:10]}...)"
                )
            except ImportError:
                logger.warning("⚠️ google-genai SDK not available")
                return None
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
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
                    SELECT DISTINCT unnest(source_chunk_ids) as chunk_id
                    FROM kg_nodes
                    WHERE source_chunk_ids IS NOT NULL
                        AND array_length(source_chunk_ids, 1) > 0
                    UNION
                    SELECT DISTINCT unnest(source_chunk_ids) as chunk_id
                    FROM kg_edges
                    WHERE source_chunk_ids IS NOT NULL
                        AND array_length(source_chunk_ids, 1) > 0
                    """
                )
                chunk_ids = {row["chunk_id"] for row in rows if row["chunk_id"]}
                logger.info(f"Found {len(chunk_ids):,} already processed chunks")
                return chunk_ids
        except Exception as e:
            logger.error(f"Error fetching processed chunks: {e}")
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
            import sys
            import os
            from pathlib import Path

            # Add scripts directory to path
            scripts_path = Path(__file__).parent.parent.parent.parent.parent / "scripts"
            if scripts_path.exists():
                sys.path.insert(0, str(scripts_path))
            else:
                # Try alternative path
                scripts_path = Path(__file__).parent.parent.parent.parent / "scripts"
                sys.path.insert(0, str(scripts_path))

            from kg_incremental_extraction import KGIncrementalExtractor
        except ImportError as e:
            logger.error(f"❌ Failed to import KGIncrementalExtractor: {e}")
            logger.error(f"   Scripts path tried: {scripts_path}")
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
                getattr(settings, "qdrant_api_key", None)
                or os.environ.get("QDRANT_API_KEY")
                or ""
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
            logger.error(f"❌ Failed to initialize KGIncrementalExtractor: {e}")
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
                    f"Skipping remaining collections."
                )
                break

            logger.info(
                f"🕸️ Processing collection: {collection} "
                f"(remaining daily quota: {max_chunks_remaining} chunks)"
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
                    total_stats["total_relationships"] += stats.get(
                        "relationships_extracted", 0
                    )
                    max_chunks_remaining -= chunks_this_run

                    logger.info(
                        f"✅ {collection}: {chunks_this_run} chunks, "
                        f"{stats.get('entities_extracted', 0)} entities, "
                        f"{stats.get('relationships_extracted', 0)} relationships "
                        f"(remaining: {max_chunks_remaining} chunks)"
                    )
                    break  # Success, move to next collection

                except Exception as e:
                    error_msg = f"{collection} (attempt {attempt + 1}/{max_retries}): {e}"
                    logger.error(f"❌ Error processing {error_msg}")

                    if attempt == max_retries - 1:
                        # Last attempt failed
                        total_stats["collections_failed"] += 1
                        total_stats["errors"].append(error_msg)
                        logger.error(f"❌ Failed to process {collection} after {max_retries} attempts")
                    else:
                        # Retry with exponential backoff
                        wait_time = 2 ** attempt
                        logger.info(f"⏳ Retrying {collection} in {wait_time}s...")
                        await asyncio.sleep(wait_time)

        logger.info(
            f"🕸️ KG Incremental Extraction Complete: "
            f"{total_stats['collections_processed']}/{len(collections)} collections, "
            f"{total_stats['total_chunks']:,} chunks, "
            f"{total_stats['total_entities']:,} entities, "
            f"{total_stats['total_relationships']:,} relationships"
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
