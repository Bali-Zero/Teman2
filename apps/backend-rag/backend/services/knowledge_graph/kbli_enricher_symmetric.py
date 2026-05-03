import asyncio
import json
import logging
import time
from typing import Any

import asyncpg

from backend.app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KBLI-Symmetric-Enricher")


class KBLIEnricher:
    def __init__(self, batch_size: int = 100, concurrency: int = 8, retries: int = 3) -> None:
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(concurrency)
        self.retries = retries
        self.db_url = settings.database_url

    async def get_db_pool(self) -> Any:
        return await asyncpg.create_pool(self.db_url)

    async def enrich_kbli_node(self, pool: asyncpg.Pool, code: str, intel: dict[str, Any]) -> bool:
        """Update PostgreSQL kg_nodes properties with discursive intelligence."""
        entity_id = f"kbli:{code}"
        attempt = 0

        while attempt < self.retries:
            async with self.semaphore:
                try:
                    async with pool.acquire() as conn:
                        # 1. Fetch current properties to avoid overwriting existing data
                        row = await conn.fetchrow(
                            "SELECT properties FROM kg_nodes WHERE entity_id = $1", entity_id,
                        )

                        if not row:
                            logger.warning(
                                f"⚠️ [KBLI:{code}] Node not found in Postgres. Creating placeholder node...",
                            )
                            # Create node if missing (optional, based on your preference)
                            await conn.execute(
                                """
                                INSERT INTO kg_nodes (entity_id, entity_type, name, properties, confidence)
                                VALUES ($1, 'kbli', $2, $3, 1.0)
                                """,
                                entity_id,
                                f"KBLI {code}",
                                json.dumps({}),
                            )
                            current_props = {}
                        else:
                            current_props = (
                                json.loads(row["properties"]) if row["properties"] else {}
                            )

                        # 2. Merge intelligence (The Circumstance)
                        updated_props = {
                            **current_props,
                            "intel_2026": {
                                "market_sentiment": intel.get("market_sentiment_2026"),
                                "bali_nuance": intel.get("bali_nuance"),
                                "operational_risks": intel.get("operational_hurdles"),
                                "investment_outlook": intel.get("strategic_roi"),
                                "legacy_bridge": intel.get("legacy_bridge"),
                                "last_updated": int(time.time()),
                                "source": "Gemini 3 PRO Deep Research",
                            },
                            "is_enriched": True,
                        }

                        # 3. Update node
                        await conn.execute(
                            """
                            UPDATE kg_nodes
                            SET properties = $1, updated_at = NOW()
                            WHERE entity_id = $2
                            """,
                            json.dumps(updated_props),
                            entity_id,
                        )

                        logger.info(f"✅ [KBLI:{code}] Symmetric enrichment complete in Postgres.")
                        return True

                except Exception as e:
                    attempt += 1
                    logger.error(
                        f"❌ [KBLI:{code}] Postgres update failed (Attempt {attempt}): {e}",
                    )
                    await asyncio.sleep(1 * attempt)

        return False

    async def run_batch(self, enriched_map: dict[str, Any]) -> None:
        """Run enrichment for a batch of codes."""
        pool = await self.get_db_pool()
        tasks = []

        logger.info(f"🚀 Starting symmetric enrichment for {len(enriched_map)} codes...")

        for code, intel in enriched_map.items():
            tasks.append(self.enrich_kbli_node(pool, code, intel))

        results = await asyncio.gather(*tasks)
        success_rate = sum(1 for r in results if r)

        logger.info(f"🏁 Symmetric Batch Complete. Success: {success_rate}/{len(enriched_map)}")
        await pool.close()


if __name__ == "__main__":
    # Questo script verrà chiamato passandogli il JSON della ricerca
    pass
