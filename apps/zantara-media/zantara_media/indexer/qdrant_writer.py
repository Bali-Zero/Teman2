"""Qdrant upsert wrapper with retry + timeout for GARUDA indexer.

CRITICAL: Qdrant upsert must always happen BEFORE any Postgres write.
This invariant is enforced in pipeline.py — do not break the call order.
"""

import asyncio
import logging
import os
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)

COLLECTION_NAME = "garuda_assets"
MAX_RETRIES = 3
RETRY_DELAY_S = 2.0
TIMEOUT_S = 30.0

# Deterministic namespace UUID for mapping Drive file_id strings to Qdrant point IDs.
# Qdrant requires unsigned int or UUID as point ID — Drive file_id is a base64-ish string.
_DRIVE_UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # RFC 4122 DNS ns


def drive_file_id_to_point_id(file_id: str) -> str:
    """Map Drive file_id string → deterministic UUID5 (stable across runs)."""
    return str(uuid.uuid5(_DRIVE_UUID_NAMESPACE, file_id))


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
        """Upsert single point with retry. Raises on all retries exhausted.

        file_id (Drive string) is mapped to a deterministic UUID5 for Qdrant's ID constraint.
        The original Drive file_id is preserved in the payload.
        """
        point_id = drive_file_id_to_point_id(file_id)
        payload = {**payload, "file_id": file_id}  # ensure payload keeps the Drive ID
        point = PointStruct(id=point_id, vector=vector, payload=payload)

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
        """Set archived=True in Qdrant payload (tombstone).

        If the point doesn't exist (never indexed), logs and returns — not an error.
        """
        from qdrant_client.http.exceptions import UnexpectedResponse

        point_id = drive_file_id_to_point_id(file_id)
        client = self._get_client()
        try:
            await client.set_payload(
                collection_name=COLLECTION_NAME,
                points=[point_id],
                payload={"archived": True},
            )
        except UnexpectedResponse as e:
            if getattr(e, "status_code", None) == 404:
                logger.debug(
                    "mark_archived: point %s not found in Qdrant (never indexed), skipping",
                    file_id,
                )
                return
            raise
