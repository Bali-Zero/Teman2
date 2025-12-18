"""
Golden Router Service
Instrada query a documenti specifici basandosi su "Golden Routes" (query canoniche).
Usa similarità semantica per matchare query utente → query canonica → documento.
"""

import asyncio
import json
import logging

import asyncpg
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoldenRouterService:
    """
    Router intelligente che mappa query utente a documenti specifici.
    Non è una cache di risposte, ma una cache di "intenti di routing".
    """

    def __init__(
        self,
        embeddings_generator=None,
        golden_answer_service=None,
        search_service=None,
    ):
        """
        Initialize GoldenRouterService.

        Args:
            embeddings_generator: Embeddings generator (legacy)
            golden_answer_service: GoldenAnswerService instance (for test compatibility)
            search_service: SearchService instance (for test compatibility)
        """
        self.embeddings = embeddings_generator
        self.golden_answer_service = golden_answer_service
        self.search_service = search_service
        self.db_pool = None
        self.routes_cache = []  # Cache in-memory delle rotte attive
        self.route_embeddings = None  # Matrix of embeddings for routes
        self.similarity_threshold = 0.85

    async def _get_db_pool(self):
        """Get or create DB pool"""
        if not self.db_pool:
            try:
                self.db_pool = await asyncpg.create_pool(
                    settings.database_url, min_size=1, max_size=5
                )
            except Exception as e:
                logger.error(f"Failed to create DB pool: {e}")
                raise
        return self.db_pool

    async def initialize(self):
        """Carica le Golden Routes dal DB in memoria"""
        logger.info("🌟 Initializing Golden Router...")
        pool = await self._get_db_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT route_id, canonical_query, document_ids, chapter_ids, collections, routing_hints
                FROM golden_routes
                WHERE usage_count >= 0 -- Load all for now
            """
            )

            self.routes_cache = []
            canonical_queries = []

            for row in rows:
                self.routes_cache.append(
                    {
                        "route_id": row["route_id"],
                        "canonical_query": row["canonical_query"],
                        "document_ids": row["document_ids"],
                        "chapter_ids": row["chapter_ids"],
                        "collections": row["collections"],
                        "hints": (
                            json.loads(row["routing_hints"])
                            if isinstance(row["routing_hints"], str)
                            else row["routing_hints"]
                        ),
                    }
                )
                canonical_queries.append(row["canonical_query"])

            if canonical_queries:
                # Generate embeddings in background to avoid blocking startup
                import asyncio

                asyncio.create_task(self._generate_embeddings_background(canonical_queries))
                logger.info(
                    f"🌟 Loaded {len(self.routes_cache)} Golden Routes (Embeddings generating in background...)"
                )
            else:
                logger.warning("⚠️ No Golden Routes found in DB")
                self.route_embeddings = None

    async def _generate_embeddings_background(self, queries: list[str]):
        """Generate embeddings in background with caching"""
        try:
            import os

            CACHE_FILE = "golden_route_embeddings.json"

            # 1. Try Load from Cache
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)

                    # Verify cache validity (simple length check)
                    if isinstance(cache_data, list) and len(cache_data) == len(queries):
                        # Convert list back to numpy array
                        self.route_embeddings = np.array(cache_data)
                        logger.info(
                            f"✅ Loaded {len(queries)} embeddings from cache ({CACHE_FILE})"
                        )
                        return
                    else:
                        logger.warning("⚠️ Cache mismatch (count differs). Regenerating...")
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Failed to load cache: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load cache: {e}")

            # 2. Generate Fresh
            logger.info(f"⏳ Generating embeddings for {len(queries)} routes...")
            embeddings = await self.embeddings.generate_embeddings_async(queries)

            # Fallback if sync
            if not embeddings and queries:
                loop = asyncio.get_running_loop()
                embeddings = await loop.run_in_executor(
                    None, self.embeddings.generate_embeddings, queries
                )

            self.route_embeddings = np.array(embeddings)

            # 3. Save to Cache (convert numpy array to list for JSON serialization)
            try:
                embeddings_list = self.route_embeddings.tolist()
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(embeddings_list, f)
                logger.info(f"💾 Saved embeddings to {CACHE_FILE}")
            except (TypeError, ValueError) as e:
                logger.warning(f"⚠️ Failed to serialize embeddings to JSON: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save cache: {e}")

            logger.info("✅ Golden Route Embeddings Ready!")
        except Exception as e:
            logger.error(f"❌ Failed to generate route embeddings: {e}")

    async def route(self, query: str, user_id: str | None = None) -> dict | None:
        """
        Trova la rotta migliore per la query.
        Ritorna None se nessuna rotta supera la soglia.

        Args:
            query: User query
            user_id: Optional user ID (for test compatibility)

        Returns:
            Route dict or None
        """
        # If golden_answer_service is available, use it (for test compatibility)
        if self.golden_answer_service:
            try:
                result = await self.golden_answer_service.find_similar(query)
                if result and result.get("similarity", 0) >= self.similarity_threshold:
                    return {
                        "answer": result.get("answer"),
                        "similarity": result.get("similarity"),
                        "score": result.get("similarity", 0),
                    }
            except Exception as e:
                logger.warning(f"GoldenAnswerService.find_similar failed: {e}")

        # Fallback to original routing logic
        if not self.routes_cache or self.route_embeddings is None:
            return None

        if not self.embeddings:
            return None

        # 1. Embed query
        query_embedding = self.embeddings.generate_query_embedding(query)
        query_vec = np.array(query_embedding).reshape(1, -1)

        # 2. Calcola similarità
        similarities = cosine_similarity(query_vec, self.route_embeddings)[0]

        # 3. Trova best match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        if best_score >= self.similarity_threshold:
            route = self.routes_cache[best_idx]
            logger.info(
                f"🌟 Golden Route Matched! '{query}' -> '{route['canonical_query']}' (score: {best_score:.2f})"
            )

            # Update usage stats async
            await self._update_usage_stats(route["route_id"])

            return {
                "route_id": route["route_id"],
                "document_ids": route["document_ids"],
                "chapter_ids": route["chapter_ids"],
                "collections": route["collections"],
                "score": float(best_score),
                "hints": route["hints"],
            }

        return None

    async def _update_usage_stats(self, route_id: str):
        """Aggiorna contatore utilizzo rotta"""
        try:
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE golden_routes
                    SET usage_count = usage_count + 1, updated_at = NOW()
                    WHERE route_id = $1
                """,
                    route_id,
                )
        except Exception as e:
            logger.warning(f"Failed to update route stats: {e}")

    async def add_route(
        self,
        canonical_query: str,
        document_ids: list[str],
        chapter_ids: list[str] = None,
        collections: list[str] = None,
    ) -> str:
        """Aggiunge una nuova Golden Route"""
        import uuid

        route_id = f"route_{uuid.uuid4().hex[:8]}"

        pool = await self._get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO golden_routes (
                    route_id, canonical_query, document_ids, chapter_ids, collections
                ) VALUES ($1, $2, $3, $4, $5)
            """,
                route_id,
                canonical_query,
                document_ids,
                chapter_ids or [],
                collections or ["legal_unified"],
            )

        # Reload cache
        await self.initialize()
        return route_id

    async def close(self):
        if self.db_pool:
            await self.db_pool.close()
