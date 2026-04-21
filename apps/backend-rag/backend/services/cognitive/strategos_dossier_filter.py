"""Qdrant-backed semantic reranker for Strategos dossier selection.

Fuses cosine-similarity (dense vector) with ``confidence_0_1`` (SQL-side score)
via Reciprocal Rank Fusion. Fail-open: on any Qdrant error the original rows
are returned untouched so the weekly brief never blocks on an infra hiccup.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Protocol

from qdrant_client.http import models as qdrant_models

logger = logging.getLogger(__name__)


class _Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class QdrantDossierFilter:
    """Rerank dossier rows via RRF(cosine, confidence) using Qdrant."""

    def __init__(
        self,
        qdrant_client: Any,
        embedder: _Embedder,
        collection: str,
        rrf_k: int = 60,
    ) -> None:
        if not collection:
            raise ValueError("collection name is required")
        self.qdrant = qdrant_client
        self.embedder = embedder
        self.collection = collection
        self.rrf_k = rrf_k

    async def rank(
        self,
        dossier_rows: list[dict],
        seed_text: str,
        top_k: int | None = None,
    ) -> list[dict]:
        """RRF-fuse cosine-sim (dense) with confidence_0_1 (raw) and return top_k.

        Fail-open: on any Qdrant-related exception, return ``dossier_rows`` unchanged.
        Rows without a Qdrant hit do not contribute to the cosine ranking (they
        still contribute via confidence) — this keeps RRF faithful to the
        definition (absent candidates get no reciprocal-rank term from a ranker
        that did not rank them).
        """
        if not dossier_rows:
            return dossier_rows
        try:
            seed_vec = await self.embedder.embed(seed_text)
            ids = [r["id"] for r in dossier_rows]
            scored = await self._qdrant_retrieve_with_scores(ids, seed_vec)

            # Cosine ranking: only rows actually returned by Qdrant.
            present_rows = [r for r in dossier_rows if r["id"] in scored]
            by_cos = sorted(
                present_rows,
                key=lambda r: scored[r["id"]],
                reverse=True,
            )
            # Confidence ranking: all rows participate.
            by_conf = sorted(
                dossier_rows,
                key=lambda r: float(r.get("confidence_0_1") or 0.0),
                reverse=True,
            )

            rrf_scores: dict[Any, float] = {}
            for rank, row in enumerate(by_cos, start=1):
                rrf_scores[row["id"]] = (
                    rrf_scores.get(row["id"], 0.0) + 1.0 / (self.rrf_k + rank)
                )
            for rank, row in enumerate(by_conf, start=1):
                rrf_scores[row["id"]] = (
                    rrf_scores.get(row["id"], 0.0) + 1.0 / (self.rrf_k + rank)
                )

            ranked = sorted(
                dossier_rows,
                key=lambda r: rrf_scores.get(r["id"], 0.0),
                reverse=True,
            )
            return ranked[:top_k] if top_k else ranked
        except Exception as exc:  # noqa: BLE001 — intentional fail-open
            logger.warning("QdrantDossierFilter fail-open: %s", exc)
            return dossier_rows

    async def _qdrant_retrieve_with_scores(
        self,
        ids: list,
        seed_vec: list[float],
    ) -> dict[Any, float]:
        """Query Qdrant filtered by dossier_id ∈ ids; return {id → cosine score}.

        Uses ``query_points`` (qdrant-client ≥ 1.10). Sync clients are
        dispatched via ``run_in_executor`` — detection happens BEFORE the call
        so a sync client never runs on the event loop.
        """
        str_ids = [str(i) for i in ids]
        query_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="dossier_id",
                    match=qdrant_models.MatchAny(any=str_ids),
                ),
            ],
        )
        kwargs = {
            "collection_name": self.collection,
            "query": seed_vec,
            "query_filter": query_filter,
            "limit": max(len(ids), 1),
            "with_payload": True,
        }

        qp = self.qdrant.query_points
        if inspect.iscoroutinefunction(qp):
            response = await qp(**kwargs)
        else:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: qp(**kwargs))

        points = getattr(response, "points", None) or []

        # Build {original_id → score}. Match by payload.dossier_id first, fall
        # back to the point id itself if the payload field is absent.
        id_lookup = {str(i): i for i in ids}
        scores: dict[Any, float] = {}
        for hit in points:
            payload = getattr(hit, "payload", None) or {}
            raw_key = payload.get("dossier_id") or getattr(hit, "id", None)
            if raw_key is None:
                continue
            key = str(raw_key)
            if key not in id_lookup:
                continue
            score = float(getattr(hit, "score", 0.0) or 0.0)
            existing = scores.get(id_lookup[key], float("-inf"))
            if score > existing:
                scores[id_lookup[key]] = score
        return scores
