"""Semantic clustering of KG orphan entities via local nomic-embed-text embeddings.

Orphans are kg_nodes without any kg_edges — invisible to GraphRAG multi-hop.
This module groups them into synthetic SEMANTIC_CLUSTER nodes using
single-linkage clustering over cosine similarity of locally-computed
embeddings (Ollama /api/embeddings, default model nomic-embed-text).

These embeddings live ONLY in PostgreSQL (centroid_embedding on the cluster
record). They must never be written into the 12 Qdrant collections that use
text-embedding-3-small at 1536 dims (FROZEN per project rules).
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any

import httpx

from backend.app.utils.async_utils import gather_with_concurrency

logger = logging.getLogger(__name__)


@dataclass
class OrphanCluster:
    """A cluster of semantically-similar orphan entities."""

    cluster_id: str
    member_ids: list[str]
    centroid_embedding: list[float]
    avg_pairwise_cosine: float


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _mean(vectors: list[list[float]]) -> list[float]:
    """Elementwise mean of vectors. All vectors must share dimensionality."""
    if not vectors:
        return []
    n = len(vectors)
    d = len(vectors[0])
    out = [0.0] * d
    for v in vectors:
        for i in range(d):
            out[i] += v[i]
    return [x / n for x in out]


async def _embed_one(
    client: httpx.AsyncClient,
    ollama_url: str,
    model: str,
    text: str,
) -> list[float] | None:
    """Embed a single text. Returns None on any failure (fail-open)."""
    try:
        resp = await client.post(
            f"{ollama_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        embedding = resp.json().get("embedding")
        if not isinstance(embedding, list) or not embedding:
            logger.warning("Ollama returned empty/invalid embedding for text of len %d", len(text))
            return None
        return embedding
    except Exception as exc:
        logger.warning("Ollama embedding call failed: %s", exc)
        return None


def _entity_text(entity: dict[str, Any]) -> str:
    """Build the text used for embedding a single entity."""
    name = entity.get("name", "") or ""
    etype = entity.get("type", "") or ""
    props = entity.get("properties") or {}
    desc = ""
    if isinstance(props, dict):
        raw_desc = props.get("description") or ""
        if isinstance(raw_desc, str):
            desc = raw_desc[:300]
    return f"{name} ({etype}). {desc}".strip()


async def cluster_orphans_by_semantic_similarity(
    orphan_entities: list[dict[str, Any]],
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "nomic-embed-text",
    cosine_threshold: float = 0.78,
    min_cluster_size: int = 3,
    max_concurrent_embeddings: int = 5,
) -> list[OrphanCluster]:
    """Cluster orphan entities by semantic similarity via local embeddings.

    Single-linkage over the cosine-threshold graph. Clusters with fewer than
    ``min_cluster_size`` members are discarded. On embedding failure (Ollama
    down, timeout, etc.) the affected entity is dropped from the candidate
    pool; the function never raises for such failures (fail-open).

    Args:
        orphan_entities: Entities shaped as ``{"id", "type", "name", "properties"}``.
        ollama_url: Ollama HTTP base URL.
        embed_model: Embedding model tag (default ``nomic-embed-text``).
        cosine_threshold: Pair is linked iff cosine >= this value.
        min_cluster_size: Singletons and pairs (below this) are discarded.
        max_concurrent_embeddings: Concurrency cap on the Ollama calls.

    Returns:
        List of OrphanCluster. Empty list if no cluster reaches
        ``min_cluster_size`` or if fewer than ``min_cluster_size`` entities
        had successful embeddings.
    """
    if not orphan_entities:
        return []

    texts = [_entity_text(e) for e in orphan_entities]

    async with httpx.AsyncClient() as client:
        embeddings: list[list[float] | None] = await gather_with_concurrency(
            max_concurrent_embeddings,
            *(_embed_one(client, ollama_url, embed_model, t) for t in texts),
        )

    valid: list[tuple[int, list[float]]] = [
        (i, e) for i, e in enumerate(embeddings) if e is not None
    ]
    if len(valid) < min_cluster_size:
        logger.info(
            "Only %d valid embeddings from %d orphans, skipping clustering",
            len(valid),
            len(orphan_entities),
        )
        return []

    n = len(valid)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(valid[i][1], valid[j][1]) >= cosine_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    clusters: list[OrphanCluster] = []
    for group_indices in groups.values():
        if len(group_indices) < min_cluster_size:
            continue

        member_ids = [orphan_entities[valid[i][0]]["id"] for i in group_indices]
        member_vecs = [valid[i][1] for i in group_indices]
        centroid = _mean(member_vecs)

        cos_sum = 0.0
        pairs = 0
        for ii in range(len(member_vecs)):
            for jj in range(ii + 1, len(member_vecs)):
                cos_sum += _cosine(member_vecs[ii], member_vecs[jj])
                pairs += 1
        avg_cos = cos_sum / pairs if pairs > 0 else 0.0

        cid_key = "|".join(sorted(member_ids))
        cid = "sem_cluster_" + hashlib.sha1(cid_key.encode()).hexdigest()[:12]

        clusters.append(
            OrphanCluster(
                cluster_id=cid,
                member_ids=member_ids,
                centroid_embedding=centroid,
                avg_pairwise_cosine=avg_cos,
            ),
        )

    logger.info(
        "Formed %d orphan clusters from %d candidates (%d embedded)",
        len(clusters),
        len(orphan_entities),
        len(valid),
    )
    return clusters
