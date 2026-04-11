"""
Idempotent ingest pipeline for politics KB hierarchical retrieval.

Upserts parent and child chunks into Qdrant collection kb_politics_hier_v1.
Re-running produces the same vector IDs — no duplicates.

IMPORTANT: Uses local embeddings only. No API keys required.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from backend.kb.politics.hierarchical.chunker import Chunk, HierarchicalChunker
from backend.kb.politics.hierarchical.embedder import LocalEmbedder

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_politics_hier_v1"

# Qdrant upsert batch size (points per request)
UPSERT_BATCH_SIZE = 50


class HierarchicalIngestor:
    """Ingest politics KB into Qdrant with hierarchical parent-child chunks."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = COLLECTION_NAME,
        embedder: LocalEmbedder | None = None,
    ) -> None:
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection = collection_name
        self._embedder = embedder or LocalEmbedder()
        self._chunker = HierarchicalChunker()
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        """Close HTTP client."""
        self._client.close()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't exist."""
        dims = self._embedder.dimensions
        url = f"{self._qdrant_url}/collections/{self._collection}"

        resp = self._client.get(url)
        if resp.status_code == 200:
            logger.info(f"Collection {self._collection} already exists")
            return

        payload = {
            "vectors": {
                "size": dims,
                "distance": "Cosine",
            },
        }
        resp = self._client.put(url, json=payload)
        resp.raise_for_status()
        logger.info(f"Created collection {self._collection} ({dims} dims)")

    def _upsert_batch(self, points: list[dict[str, Any]]) -> None:
        """Upsert a batch of points to Qdrant."""
        url = f"{self._qdrant_url}/collections/{self._collection}/points"
        payload = {"points": points}
        resp = self._client.put(url, json=payload)
        resp.raise_for_status()

    def _chunk_to_point(self, chunk: Chunk, vector: list[float]) -> dict[str, Any]:
        """Convert a Chunk + vector into a Qdrant point.

        Payload is flat (no nested dicts) per project convention.
        """
        payload: dict[str, Any] = {
            "text": chunk.text,
            "chunk_type": chunk.chunk_type,
            "record_id": chunk.record_id,
            "record_type": chunk.record_type,
            "source_path": chunk.source_path,
            "offset": chunk.offset,
            "language": chunk.language,
            "domain": "politics-id",
        }
        if chunk.parent_id is not None:
            payload["parent_id"] = chunk.parent_id
        # Merge record-level metadata (flat)
        for k, v in chunk.metadata.items():
            if k not in payload and v is not None:
                payload[k] = v

        return {
            "id": chunk.id,
            "vector": vector,
            "payload": payload,
        }

    def ingest_directory(self, root: Path) -> dict[str, Any]:
        """Ingest all JSONL files under a politics KB directory.

        Args:
            root: Path to politics/id/ directory.

        Returns:
            Stats dict with counts and timing.
        """
        start = time.perf_counter()
        root = Path(root)

        # Chunk all files
        logger.info(f"Chunking directory: {root}")
        chunks = self._chunker.chunk_directory(root)
        if not chunks:
            return {"success": False, "error": "No chunks produced", "docs": 0}

        parents = [c for c in chunks if c.chunk_type == "parent"]
        children = [c for c in chunks if c.chunk_type == "child"]

        # Embed all chunks
        logger.info(f"Embedding {len(chunks)} chunks...")
        vectors = self._embedder.embed_chunks(chunks)

        # Ensure collection exists
        self._ensure_collection()

        # Upsert in batches
        points = [
            self._chunk_to_point(chunk, vec)
            for chunk, vec in zip(chunks, vectors)
        ]

        upserted = 0
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            self._upsert_batch(batch)
            upserted += len(batch)
            logger.debug(f"Upserted {upserted}/{len(points)} points")

        elapsed = time.perf_counter() - start

        stats = {
            "success": True,
            "collection": self._collection,
            "docs_processed": len(parents),
            "parents": len(parents),
            "children": len(children),
            "total_vectors": len(chunks),
            "embedding_model": self._embedder.model_name,
            "embedding_dims": self._embedder.dimensions,
            "runtime_seconds": round(elapsed, 2),
        }
        logger.info(f"Ingest complete: {stats}")
        return stats

    def ingest_chunks(self, chunks: list[Chunk]) -> dict[str, Any]:
        """Ingest pre-chunked data (useful for testing).

        Args:
            chunks: List of Chunk objects to ingest.

        Returns:
            Stats dict.
        """
        if not chunks:
            return {"success": False, "error": "No chunks", "total_vectors": 0}

        vectors = self._embedder.embed_chunks(chunks)
        self._ensure_collection()

        points = [
            self._chunk_to_point(chunk, vec)
            for chunk, vec in zip(chunks, vectors)
        ]

        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            self._upsert_batch(batch)

        return {
            "success": True,
            "total_vectors": len(chunks),
            "parents": sum(1 for c in chunks if c.chunk_type == "parent"),
            "children": sum(1 for c in chunks if c.chunk_type == "child"),
        }
