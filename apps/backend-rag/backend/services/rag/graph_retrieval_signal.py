"""Graph Retrieval Signal — GraphRAG 2.0

Generates a ranked list of document IDs from graph traversal,
to be used as the third signal in trimodal RRF fusion (vector + BM25 + graph).

The graph signal answers: "Which documents are connected to KG entities
relevant to this query?"

Scoring: entity_confidence × num_kg_paths_through_chunk

Usage:
    signal = GraphRetrievalSignal(db_pool)
    results = await signal.get_ranked_docs(query)
    # results: [GraphRetrievalResult(point_id, collection, score), ...]
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.services.knowledge_graph.entity_linker import extract_mentions

logger = logging.getLogger(__name__)


@dataclass
class GraphRetrievalResult:
    """A document ranked by its graph connectivity."""

    point_id: str
    collection_name: str
    score: float = 0.0
    linked_entities: list[str] = field(default_factory=list)


class GraphRetrievalSignal:
    """Generates graph-based document rankings for trimodal retrieval."""

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def get_ranked_docs(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[GraphRetrievalResult]:
        """Get documents ranked by graph relevance to query.

        Algorithm:
        1. Extract entity mentions from query (regex patterns)
        2. Fuzzy match mentions against kg_nodes
        3. For matched entities: get source_chunk_ids from kg_nodes
        4. For matched entities: get linked docs from kg_entity_mentions
        5. Score each document: entity_confidence × num_linked_entities

        Args:
            query: User query text
            max_results: Maximum documents to return

        Returns:
            Ranked list of GraphRetrievalResult
        """
        start = time.time()

        # Step 1: Extract entity mentions from query
        mentions = extract_mentions(query)
        if not mentions:
            return []

        mention_texts = [m["text"] for m in mentions]

        # Step 2: Fuzzy match against kg_nodes
        matched_entity_ids: list[str] = []
        entity_confidences: dict[str, float] = {}

        async with self._pool.acquire() as conn:
            for mention_text in mention_texts:
                # Try exact match first
                row = await conn.fetchrow(
                    "SELECT entity_id, confidence FROM kg_nodes "
                    "WHERE LOWER(name) = LOWER($1) LIMIT 1",
                    mention_text,
                )
                if not row:
                    # Fuzzy match
                    row = await conn.fetchrow(
                        "SELECT entity_id, confidence FROM kg_nodes "
                        "WHERE similarity(name, $1) >= 0.7 "
                        "ORDER BY similarity(name, $1) DESC LIMIT 1",
                        mention_text,
                    )
                if row:
                    eid = row["entity_id"]
                    if eid not in entity_confidences:
                        matched_entity_ids.append(eid)
                        entity_confidences[eid] = float(row["confidence"] or 1.0)

        if not matched_entity_ids:
            return []

        # Step 3: Get source_chunk_ids from kg_nodes (direct links)
        doc_scores: dict[tuple[str, str], float] = {}  # (point_id, collection) → score
        doc_entities: dict[tuple[str, str], list[str]] = {}

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT entity_id, source_collection, source_chunk_ids "
                "FROM kg_nodes WHERE entity_id = ANY($1)",
                matched_entity_ids,
            )
            for row in rows:
                eid = row["entity_id"]
                collection = row["source_collection"] or ""
                chunk_ids = row["source_chunk_ids"] or []
                conf = entity_confidences.get(eid, 0.7)

                for cid in chunk_ids:
                    if not cid:
                        continue
                    key = (cid, collection)
                    doc_scores[key] = doc_scores.get(key, 0.0) + conf
                    doc_entities.setdefault(key, []).append(eid)

        # Step 4: Get linked docs from kg_entity_mentions
        async with self._pool.acquire() as conn:
            mention_rows = await conn.fetch(
                "SELECT entity_id, collection_name, point_id, confidence "
                "FROM kg_entity_mentions "
                "WHERE entity_id = ANY($1) AND confidence >= 0.7",
                matched_entity_ids,
            )
            for row in mention_rows:
                eid = row["entity_id"]
                key = (row["point_id"], row["collection_name"])
                mention_conf = float(row["confidence"])
                entity_conf = entity_confidences.get(eid, 0.7)
                # Score: entity confidence × mention confidence
                score = entity_conf * mention_conf
                doc_scores[key] = doc_scores.get(key, 0.0) + score
                doc_entities.setdefault(key, []).append(eid)

        # Step 5: Build ranked results
        results = [
            GraphRetrievalResult(
                point_id=key[0],
                collection_name=key[1],
                score=score,
                linked_entities=list(set(doc_entities.get(key, []))),
            )
            for key, score in doc_scores.items()
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:max_results]

        elapsed = time.time() - start
        logger.info(
            "[GraphSignal] %d mentions → %d entities → %d docs (%.1fms)",
            len(mentions),
            len(matched_entity_ids),
            len(results),
            elapsed * 1000,
        )
        return results
