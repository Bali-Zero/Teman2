"""
Hierarchical retriever for politics KB.

Query flow:
1. Embed query
2. Search children in Qdrant (top-K nearest)
3. Aggregate scores by parent_id
4. Retrieve parent texts
5. Rerank parents by aggregated child scores
6. Return parents with child evidence

This gives better recall than flat retrieval because fine-grained claims
match specific queries, while parents provide full context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.kb.politics.hierarchical.embedder import LocalEmbedder
from backend.kb.politics.hierarchical.ingest import COLLECTION_NAME

logger = logging.getLogger(__name__)

# Number of children to fetch per query
DEFAULT_CHILD_LIMIT = 20

# Number of parents to return
DEFAULT_PARENT_LIMIT = 5


@dataclass
class RetrievalResult:
    """A parent document with aggregated child evidence."""

    parent_id: str
    parent_text: str
    score: float  # Aggregated score from child matches
    record_id: str
    record_type: str
    children: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class HierarchicalRetriever:
    """Query → child search → parent aggregation → rerank."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = COLLECTION_NAME,
        embedder: LocalEmbedder | None = None,
        child_limit: int = DEFAULT_CHILD_LIMIT,
        parent_limit: int = DEFAULT_PARENT_LIMIT,
    ) -> None:
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection = collection_name
        self._embedder = embedder or LocalEmbedder()
        self._child_limit = child_limit
        self._parent_limit = parent_limit
        self._client = httpx.Client(timeout=15.0)

    def close(self) -> None:
        """Close HTTP client."""
        self._client.close()

    def retrieve(
        self,
        query: str,
        child_limit: int | None = None,
        parent_limit: int | None = None,
        filter_record_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve parents ranked by child match quality.

        Args:
            query: Search query (Indonesian or English).
            child_limit: Override default child search limit.
            parent_limit: Override default parent return limit.
            filter_record_type: Optional filter by record type (person, party, etc.).

        Returns:
            List of RetrievalResult sorted by score (descending).
        """
        c_limit = child_limit or self._child_limit
        p_limit = parent_limit or self._parent_limit

        # 1. Embed query
        query_vector = self._embedder.embed_query(query)
        if not query_vector:
            logger.error("Failed to embed query")
            return []

        # 2. Search children
        children = self._search_children(query_vector, c_limit, filter_record_type)
        if not children:
            logger.info(f"No children found for query: {query[:80]}")
            return []

        # 3. Aggregate by parent
        parent_groups = self._aggregate_by_parent(children)

        # 4. Fetch parent texts
        parent_ids = list(parent_groups.keys())
        parent_docs = self._fetch_parents(parent_ids)

        # 5. Build results sorted by aggregated score
        results: list[RetrievalResult] = []
        for pid, group in parent_groups.items():
            parent_doc = parent_docs.get(pid, {})
            parent_text = parent_doc.get("text", "")
            record_id = parent_doc.get("record_id", "")
            record_type = parent_doc.get("record_type", "")

            # Aggregation: sum of child scores (rewards multiple matching claims)
            agg_score = sum(c["score"] for c in group)

            results.append(RetrievalResult(
                parent_id=pid,
                parent_text=parent_text,
                score=agg_score,
                record_id=record_id,
                record_type=record_type,
                children=group,
                metadata={k: v for k, v in parent_doc.items() if k not in ("text",)},
            ))

        # Sort by aggregated score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:p_limit]

    def _search_children(
        self,
        query_vector: list[float],
        limit: int,
        filter_record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search Qdrant for child chunks matching the query vector."""
        url = f"{self._qdrant_url}/collections/{self._collection}/points/search"

        # Filter: only children (chunk_type == "child")
        must_conditions: list[dict[str, Any]] = [
            {"key": "chunk_type", "match": {"value": "child"}},
        ]
        if filter_record_type:
            must_conditions.append(
                {"key": "record_type", "match": {"value": filter_record_type}},
            )

        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "filter": {"must": must_conditions},
        }

        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for hit in data.get("result", []):
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

        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

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
