"""
Idempotent ingest pipeline for politics KB hierarchical retrieval.

Supports hybrid mode (dense + BM25 sparse) for combined semantic and keyword
matching. Upserts to Qdrant with named vectors: "dense" + "sparse".

Re-running produces the same vector IDs — no duplicates.
IMPORTANT: Uses local embeddings only. No API keys required.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from backend.kb.politics.hierarchical.chunker import Chunk, HierarchicalChunker
from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder, LocalEmbedder

logger = logging.getLogger(__name__)

COLLECTION_NAME = "kb_politics_hier_v1"

# Qdrant upsert batch size (points per request)
UPSERT_BATCH_SIZE = 50


class HierarchicalIngestor:
    """Ingest politics KB into Qdrant with hierarchical parent-child chunks.

    Supports hybrid mode: dense vectors (semantic) + sparse vectors (BM25 keyword).
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = COLLECTION_NAME,
        embedder: LocalEmbedder | None = None,
        hybrid: bool = True,
    ) -> None:
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection = collection_name
        self._embedder = embedder or LocalEmbedder()
        self._chunker = HierarchicalChunker()
        self._client = httpx.Client(timeout=30.0)
        self._hybrid = hybrid
        self._sparse_encoder: BM25SparseEncoder | None = None

    def close(self) -> None:
        """Close HTTP client."""
        self._client.close()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection with named vectors if it doesn't exist."""
        dims = self._embedder.dimensions
        url = f"{self._qdrant_url}/collections/{self._collection}"

        resp = self._client.get(url)
        if resp.status_code == 200:
            logger.info(f"Collection {self._collection} already exists")
            return

        config: dict[str, Any] = {
            "vectors": {
                "dense": {
                    "size": dims,
                    "distance": "Cosine",
                },
            },
        }
        if self._hybrid:
            config["sparse_vectors"] = {
                "sparse": {},
            }

        resp = self._client.put(url, json=config)
        resp.raise_for_status()
        mode = "hybrid (dense+sparse)" if self._hybrid else "dense-only"
        logger.info(f"Created collection {self._collection} ({dims} dims, {mode})")

    def _upsert_batch(self, points: list[dict[str, Any]]) -> None:
        """Upsert a batch of points to Qdrant."""
        url = f"{self._qdrant_url}/collections/{self._collection}/points"
        payload = {"points": points}
        resp = self._client.put(url, json=payload)
        resp.raise_for_status()

    def _build_payload(self, chunk: Chunk) -> dict[str, Any]:
        """Build flat Qdrant payload from chunk."""
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
        for k, v in chunk.metadata.items():
            if k not in payload and v is not None:
                payload[k] = v
        return payload

    def _chunk_to_point(
        self,
        chunk: Chunk,
        dense_vec: list[float],
        sparse_vec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert a Chunk + vectors into a Qdrant point."""
        payload = self._build_payload(chunk)

        vector: Any
        if self._hybrid and sparse_vec:
            vector = {
                "dense": dense_vec,
                "sparse": sparse_vec,
            }
        else:
            vector = {"dense": dense_vec}

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

        # Dense embeddings
        logger.info(f"Embedding {len(chunks)} chunks (dense)...")
        dense_vecs = self._embedder.embed_chunks(chunks)

        # Sparse embeddings (BM25)
        sparse_vecs: list[dict[str, Any]] | None = None
        if self._hybrid:
            logger.info("Building BM25 sparse vectors...")
            texts = [c.text for c in chunks]
            self._sparse_encoder = BM25SparseEncoder()
            self._sparse_encoder.fit(texts)
            sparse_vecs = self._sparse_encoder.encode_documents(texts)

        # Ensure collection exists
        self._ensure_collection()

        # Build points
        points: list[dict[str, Any]] = []
        for i, (chunk, dvec) in enumerate(zip(chunks, dense_vecs)):
            svec = sparse_vecs[i] if sparse_vecs else None
            points.append(self._chunk_to_point(chunk, dvec, svec))

        # Upsert in batches
        upserted = 0
        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            self._upsert_batch(batch)
            upserted += len(batch)
            logger.debug(f"Upserted {upserted}/{len(points)} points")

        elapsed = time.perf_counter() - start

        stats: dict[str, Any] = {
            "success": True,
            "collection": self._collection,
            "docs_processed": len(parents),
            "parents": len(parents),
            "children": len(children),
            "total_vectors": len(chunks),
            "embedding_model": self._embedder.model_name,
            "embedding_dims": self._embedder.dimensions,
            "hybrid": self._hybrid,
            "runtime_seconds": round(elapsed, 2),
        }
        if self._sparse_encoder:
            stats["bm25_vocab_size"] = self._sparse_encoder.vocab_size
        logger.info(f"Ingest complete: {stats}")
        return stats

    def ingest_chunks(self, chunks: list[Chunk]) -> dict[str, Any]:
        """Ingest pre-chunked data (useful for testing)."""
        if not chunks:
            return {"success": False, "error": "No chunks", "total_vectors": 0}

        dense_vecs = self._embedder.embed_chunks(chunks)

        sparse_vecs: list[dict[str, Any]] | None = None
        if self._hybrid:
            texts = [c.text for c in chunks]
            self._sparse_encoder = BM25SparseEncoder()
            self._sparse_encoder.fit(texts)
            sparse_vecs = self._sparse_encoder.encode_documents(texts)

        self._ensure_collection()

        points: list[dict[str, Any]] = []
        for i, (chunk, dvec) in enumerate(zip(chunks, dense_vecs)):
            svec = sparse_vecs[i] if sparse_vecs else None
            points.append(self._chunk_to_point(chunk, dvec, svec))

        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[i : i + UPSERT_BATCH_SIZE]
            self._upsert_batch(batch)

        return {
            "success": True,
            "total_vectors": len(chunks),
            "parents": sum(1 for c in chunks if c.chunk_type == "parent"),
            "children": sum(1 for c in chunks if c.chunk_type == "child"),
        }
