"""
Golden Answer Service - Fast lookup of pre-generated FAQ answers

Provides sub-100ms lookup of cached answers for frequent queries.
Integrated into Sonnet workflow BEFORE RAG search.

Flow:
1. User query comes in
2. Check golden_answers table (10-20ms PostgreSQL lookup)
3. If match found → return cached answer immediately
4. If no match → proceed to normal RAG + Sonnet generation

This provides 250x speedup for ~50-60% of queries.
"""

import hashlib
import logging

import asyncpg
import numpy as np

# SECURITY: Lazy import of sentence_transformers to avoid PyTorch import issues during test collection
# SentenceTransformer will be imported inside methods when needed
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class GoldenAnswerService:
    """
    Fast lookup and retrieval of pre-generated golden answers
    """

    def __init__(self, database_url: str):
        """
        Initialize service

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None
        self.model: SentenceTransformer | None = None
        self.similarity_threshold = 0.80  # 80% similarity required

    async def connect(self):
        """Initialize PostgreSQL connection pool"""
        try:
            # PERFORMANCE FIX: Increased pool size from max=10 to max=20 for better concurrency
            # See: docs/debug/performance/database_report.md
            self.pool = await asyncpg.create_pool(
                self.database_url, min_size=5, max_size=20, command_timeout=30
            )
            logger.info("✅ GoldenAnswerService connected to PostgreSQL (pool: min=5, max=20)")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            raise

    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("GoldenAnswerService connection closed")

    def _load_model(self):
        """Lazy load embedding model"""
        if self.model is None:
            # Lazy import to avoid PyTorch import issues during test collection
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model for similarity matching...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

    async def lookup_golden_answer(self, query: str, _user_id: str | None = None) -> dict | None:
        """
        Lookup golden answer for user query

        Args:
            query: User query text
            user_id: User ID (for analytics)

        Returns:
            Dict with answer, sources, confidence if found, else None
        """
        if not self.pool:
            await self.connect()

        try:
            # Generate query hash for exact match
            query_hash = hashlib.md5(query.lower().strip().encode("utf-8")).hexdigest()

            # Step 1: Try exact match in query_clusters
            async with self.pool.acquire() as conn:
                exact_match = await conn.fetchrow(
                    """
                    SELECT
                        qc.cluster_id,
                        ga.canonical_question,
                        ga.answer,
                        ga.sources,
                        ga.confidence,
                        ga.usage_count
                    FROM query_clusters qc
                    JOIN golden_answers ga ON qc.cluster_id = ga.cluster_id
                    WHERE qc.query_hash = $1
                """,
                    query_hash,
                )

            if exact_match:
                logger.info(f"✅ Exact golden answer match: {exact_match['cluster_id']}")

                # Increment usage count
                await self._increment_usage(exact_match["cluster_id"])

                return {
                    "cluster_id": exact_match["cluster_id"],
                    "canonical_question": exact_match["canonical_question"],
                    "answer": exact_match["answer"],
                    "sources": exact_match["sources"],
                    "confidence": exact_match["confidence"],
                    "match_type": "exact",
                }

            # Step 2: Try semantic similarity match
            semantic_match = await self._semantic_lookup(query)

            if semantic_match:
                logger.info(
                    f"✅ Semantic golden answer match: {semantic_match['cluster_id']} (similarity: {semantic_match['similarity']:.2f})"
                )

                # Increment usage count
                await self._increment_usage(semantic_match["cluster_id"])

                return {
                    "cluster_id": semantic_match["cluster_id"],
                    "canonical_question": semantic_match["canonical_question"],
                    "answer": semantic_match["answer"],
                    "sources": semantic_match["sources"],
                    "confidence": semantic_match["confidence"],
                    "match_type": "semantic",
                    "similarity": semantic_match["similarity"],
                }

            # No match found
            logger.debug(f"❌ No golden answer found for: {query[:60]}...")
            return None

        except Exception as e:
            logger.error(f"❌ Golden answer lookup failed: {e}")
            return None

    async def _semantic_lookup(self, query: str) -> dict | None:
        """
        Find golden answer using semantic similarity

        Args:
            query: User query

        Returns:
            Best matching golden answer if similarity > threshold
        """
        if not self.pool:
            return None

        try:
            # Load embedding model
            self._load_model()

            # Get all canonical questions from golden_answers
            async with self.pool.acquire() as conn:
                golden_answers = await conn.fetch(
                    """
                    SELECT
                        cluster_id,
                        canonical_question,
                        answer,
                        sources,
                        confidence,
                        usage_count
                    FROM golden_answers
                    ORDER BY usage_count DESC
                    LIMIT 100
                """
                )

            if not golden_answers:
                return None

            # Generate embeddings
            query_embedding = self.model.encode([query])[0]
            canonical_questions = [ga["canonical_question"] for ga in golden_answers]
            canonical_embeddings = self.model.encode(canonical_questions)

            # Calculate similarities
            similarities = cosine_similarity([query_embedding], canonical_embeddings)[0]

            # Find best match above threshold
            best_idx = np.argmax(similarities)
            best_similarity = similarities[best_idx]

            if best_similarity >= self.similarity_threshold:
                best_match = golden_answers[best_idx]

                return {
                    "cluster_id": best_match["cluster_id"],
                    "canonical_question": best_match["canonical_question"],
                    "answer": best_match["answer"],
                    "sources": best_match["sources"],
                    "confidence": best_match["confidence"],
                    "similarity": float(best_similarity),
                }

            return None

        except Exception as e:
            logger.error(f"❌ Semantic lookup failed: {e}")
            return None

    async def _increment_usage(self, cluster_id: str):
        """
        Increment usage_count and update last_used_at for golden answer

        Args:
            cluster_id: Golden answer cluster ID
        """
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE golden_answers
                    SET
                        usage_count = usage_count + 1,
                        last_used_at = NOW()
                    WHERE cluster_id = $1
                """,
                    cluster_id,
                )

        except Exception as e:
            logger.warning(f"⚠️ Failed to increment usage for {cluster_id}: {e}")

    async def get_golden_answer_stats(self) -> dict:
        """
        Get statistics about golden answer usage

        Returns:
            Dict with statistics
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_golden_answers,
                    SUM(usage_count) as total_hits,
                    AVG(confidence) as avg_confidence,
                    MAX(usage_count) as max_usage,
                    MIN(usage_count) as min_usage
                FROM golden_answers
            """
            )

            top_10 = await conn.fetch(
                """
                SELECT
                    cluster_id,
                    canonical_question,
                    usage_count,
                    DATE(last_used_at) as last_used
                FROM golden_answers
                ORDER BY usage_count DESC
                LIMIT 10
            """
            )

        return {
            "total_golden_answers": stats["total_golden_answers"],
            "total_hits": stats["total_hits"] or 0,
            "avg_confidence": float(stats["avg_confidence"] or 0),
            "max_usage": stats["max_usage"] or 0,
            "min_usage": stats["min_usage"] or 0,
            "top_10": [
                {
                    "cluster_id": row["cluster_id"],
                    "question": row["canonical_question"],
                    "usage_count": row["usage_count"],
                    "last_used": row["last_used"].isoformat() if row["last_used"] else None,
                }
                for row in top_10
            ],
        }


# Convenience function for testing
async def test_service():
    """Test golden answer service"""
    import logging

    from app.core.config import settings

    logger = logging.getLogger(__name__)

    if not settings.database_url:
        logger.error("DATABASE_URL not set")
        return

    service = GoldenAnswerService(settings.database_url)

    try:
        await service.connect()

        logger.info("\nTESTING GOLDEN ANSWER LOOKUP")
        logger.info("=" * 60)

        # Test query
        test_query = "How to get KITAS in Indonesia?"

        logger.info(f"\nQuery: {test_query}")
        result = await service.lookup_golden_answer(test_query)

        if result:
            logger.info("\nMATCH FOUND!")
            logger.info(f"Match type: {result['match_type']}")
            logger.info(f"Cluster ID: {result['cluster_id']}")
            logger.info(f"Canonical: {result['canonical_question']}")
            logger.info(f"Confidence: {result['confidence']}")
            logger.info("\nAnswer:")
            logger.info(result["answer"][:300] + "...")
            logger.info(f"\nSources: {len(result.get('sources', []))}")
        else:
            logger.warning("\nNo match found")

        # Get stats
        logger.info("\nGOLDEN ANSWER STATISTICS")
        logger.info("=" * 60)
        stats = await service.get_golden_answer_stats()
        logger.info(f"Total golden answers: {stats['total_golden_answers']}")
        logger.info(f"Total cache hits: {stats['total_hits']}")
        logger.info(f"Average confidence: {stats['avg_confidence']:.2f}")

    finally:
        await service.close()


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(test_service())
