"""Qdrant upsert wrapper with retry + timeout for GARUDA indexer.

CRITICAL: Qdrant upsert must always happen BEFORE any Postgres write.
This invariant is enforced in pipeline.py — do not break the call order.
"""

import asyncio
import logging
import os
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)

COLLECTION_NAME = "garuda_assets"
MAX_RETRIES = 3
RETRY_DELAY_S = 2.0
TIMEOUT_S = 30.0


class QdrantWriter:
    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None

    def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=os.environ["QDRANT_URL"],
                api_key=os.getenv("QDRANT_API_KEY"),
                timeout=TIMEOUT_S,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def upsert(
        self,
        file_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """Upsert single point with retry. Raises on all retries exhausted."""
        point = PointStruct(id=file_id, vector=vector, payload=payload)

        for attempt in range(MAX_RETRIES):
            try:
                client = self._get_client()
                await client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=[point],
                )
                return  # success
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(
                        "Qdrant upsert failed after %d retries: %s",
                        MAX_RETRIES,
                        e,
                    )
                    raise
                logger.warning(
                    "Qdrant upsert attempt %d/%d failed: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
                await asyncio.sleep(RETRY_DELAY_S * (attempt + 1))

    async def mark_archived(self, file_id: str) -> None:
        """Set archived=True in Qdrant payload (tombstone)."""
        client = self._get_client()
        await client.set_payload(
            collection_name=COLLECTION_NAME,
            points=[file_id],
            payload={"archived": True},
        )
