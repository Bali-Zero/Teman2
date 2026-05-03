"""
Hierarchical retriever for politics KB — hybrid (dense + sparse) mode.

Query flow:
1. Embed query (dense + BM25 sparse)
2. Search children via Qdrant prefetch + RRF fusion
3. Aggregate scores by parent_id
4. Retrieve parent texts
5. Return parents sorted by aggregated child score

Hybrid search combines:
- Dense: semantic similarity (paraphrase-multilingual-MiniLM-L12-v2)
- Sparse: BM25 keyword matching for exact dates, names, abbreviations
- Fusion: Reciprocal Rank Fusion (RRF) via Qdrant query API
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.kb.politics.hierarchical.embedder import BM25SparseEncoder, LocalEmbedder
from backend.kb.politics.hierarchical.ingest import COLLECTION_NAME

logger = logging.getLogger(__name__)

DEFAULT_CHILD_LIMIT = 20
DEFAULT_PARENT_LIMIT = 5


@dataclass
class RetrievalResult:
    """A parent document with aggregated child evidence."""

    parent_id: str
    parent_text: str
    score: float
    record_id: str
    record_type: str
    children: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class HierarchicalRetriever:
    """Query -> child search -> parent aggregation -> rerank.

    Supports hybrid (dense + sparse) and dense-only modes.
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = COLLECTION_NAME,
        embedder: LocalEmbedder | None = None,
        sparse_encoder: BM25SparseEncoder | None = None,
        child_limit: int = DEFAULT_CHILD_LIMIT,
        parent_limit: int = DEFAULT_PARENT_LIMIT,
    ) -> None:
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection = collection_name
        self._embedder = embedder or LocalEmbedder()
        self._sparse_encoder = sparse_encoder
        self._child_limit = child_limit
        self._parent_limit = parent_limit
        self._client = httpx.Client(timeout=15.0)

    def close(self) -> None:
        """Close HTTP client."""
        self._client.close()

    @property
    def is_hybrid(self) -> bool:
        return self._sparse_encoder is not None

    def retrieve(
        self,
        query: str,
        child_limit: int | None = None,
        parent_limit: int | None = None,
        filter_record_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve parents ranked by child match quality.

        Uses hybrid search (dense + sparse + RRF) when sparse_encoder is set,
        otherwise falls back to dense-only.
        """
        c_limit = child_limit or self._child_limit
        p_limit = parent_limit or self._parent_limit

        # Embed query
        dense_vec = self._embedder.embed_query(query)
        if not dense_vec:
            logger.error("Failed to embed query")
            return []

        sparse_vec: dict[str, Any] | None = None
        if self._sparse_encoder:
            sparse_vec = self._sparse_encoder.encode_query(query)

        # Search children
        if sparse_vec and sparse_vec.get("indices"):
            children = self._search_children_hybrid(
                dense_vec, sparse_vec, c_limit, filter_record_type,
            )
        else:
            children = self._search_children_dense(
                dense_vec, c_limit, filter_record_type,
            )

        if not children:
            logger.info(f"No children found for query: {query[:80]}")
            return []

        # Aggregate by parent
        parent_groups = self._aggregate_by_parent(children)

        # Fetch parent texts
        parent_ids = list(parent_groups.keys())
        parent_docs = self._fetch_parents(parent_ids)

        # Build results
        results: list[RetrievalResult] = []
        for pid, group in parent_groups.items():
            parent_doc = parent_docs.get(pid, {})
            agg_score = sum(c["score"] for c in group)

            results.append(RetrievalResult(
                parent_id=pid,
                parent_text=parent_doc.get("text", ""),
                score=agg_score,
                record_id=parent_doc.get("record_id", ""),
                record_type=parent_doc.get("record_type", ""),
                children=group,
                metadata={k: v for k, v in parent_doc.items() if k != "text"},
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:p_limit]

    def _child_filter(self, filter_record_type: str | None) -> dict[str, Any]:
        """Build Qdrant filter for child chunks."""
        must: list[dict[str, Any]] = [
            {"key": "chunk_type", "match": {"value": "child"}},
        ]
        if filter_record_type:
            must.append({"key": "record_type", "match": {"value": filter_record_type}})
        return {"must": must}

    def _search_children_hybrid(
        self,
        dense_vec: list[float],
        sparse_vec: dict[str, Any],
        limit: int,
        filter_record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search children using Qdrant hybrid prefetch + RRF fusion."""
        url = f"{self._qdrant_url}/collections/{self._collection}/points/query"

        filt = self._child_filter(filter_record_type)

        payload = {
            "prefetch": [
                {
                    "query": {"name": "dense", "vector": dense_vec},
                    "using": "dense",
                    "limit": limit,
                    "filter": filt,
                },
                {
                    "query": {"name": "sparse", "vector": sparse_vec},
                    "using": "sparse",
                    "limit": limit,
                    "filter": filt,
                },
            ],
            "query": {"fusion": "rrf"},
            "limit": limit,
            "with_payload": True,
        }

        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.warning(f"Hybrid search failed, falling back to dense: {e}")
            return self._search_children_dense(dense_vec, limit, filter_record_type)

        return self._parse_search_results(data)

    def _search_children_dense(
        self,
        dense_vec: list[float],
        limit: int,
        filter_record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search children using dense vectors only."""
        url = f"{self._qdrant_url}/collections/{self._collection}/points/query"

        filt = self._child_filter(filter_record_type)

        payload = {
            "query": {"name": "dense", "vector": dense_vec},
            "using": "dense",
            "limit": limit,
            "with_payload": True,
            "filter": filt,
        }

        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Qdrant child search failed: {e}")
            return []

        return self._parse_search_results(data)

    def _parse_search_results(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse Qdrant search/query response into child dicts."""
        results = []
        for hit in data.get("result", data.get("points", [])):
            p = hit.get("payload", {})
            results.append({
                "id": hit.get("id"),
                "score": hit.get("score", 0.0),
                "text": p.get("text", ""),
                "parent_id": p.get("parent_id"),
                "record_id": p.get("record_id", ""),
                "record_type": p.get("record_type", ""),
            })
        return results

    def _aggregate_by_parent(
        self, children: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group children by parent_id."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for child in children:
            pid = child.get("parent_id")
            if pid is None:
                continue
            groups.setdefault(pid, []).append(child)
        return groups

    def _fetch_parents(self, parent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch parent documents from Qdrant by their IDs."""
        if not parent_ids:
            return {}

        url = f"{self._qdrant_url}/collections/{self._collection}/points"
        payload = {"ids": parent_ids, "with_payload": True}

        try:
            resp = self._client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Qdrant parent fetch failed: {e}")
            return {}

        parents: dict[str, dict[str, Any]] = {}
        for point in data.get("result", []):
            pid = point.get("id")
            p = point.get("payload", {})
            parents[pid] = {
                "text": p.get("text", ""),
                "record_id": p.get("record_id", ""),
                "record_type": p.get("record_type", ""),
                "name": p.get("name", ""),
                "domain": p.get("domain", ""),
            }

        return parents
