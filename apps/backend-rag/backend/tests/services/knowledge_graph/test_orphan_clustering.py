"""Tests for orphan semantic clustering via local nomic-embed-text embeddings."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.services.knowledge_graph import orphan_clustering
from backend.services.knowledge_graph.orphan_clustering import (
    OrphanCluster,
    cluster_orphans_by_semantic_similarity,
)


def _orphan(entity_id: str, name: str = "Entity", etype: str = "concept") -> dict[str, Any]:
    return {
        "id": entity_id,
        "type": etype,
        "name": name,
        "properties": {"description": f"desc-{entity_id}"},
    }


class TestCluster:
    @pytest.mark.asyncio
    async def test_cluster_groups_similar_entities(self) -> None:
        """Three near-identical vectors cluster; two orthogonal ones don't."""
        # Three similar (close to [1,0,0,...]) + two orthogonal
        similar = [1.0, 0.01, 0.0, 0.0]
        ortho_a = [0.0, 1.0, 0.0, 0.0]
        ortho_b = [0.0, 0.0, 1.0, 0.0]
        fake_embeddings = [
            list(similar),
            [0.99, 0.02, 0.0, 0.0],
            [0.98, 0.0, 0.01, 0.0],
            list(ortho_a),
            list(ortho_b),
        ]

        call_order = iter(fake_embeddings)

        async def fake_embed(
            client: httpx.AsyncClient, url: str, model: str, text: str,
        ) -> list[float]:
            return next(call_order)

        orphans = [_orphan(f"orph_{i}") for i in range(5)]

        with patch.object(orphan_clustering, "_embed_one", side_effect=fake_embed):
            clusters = await cluster_orphans_by_semantic_similarity(
                orphans,
                cosine_threshold=0.9,
                min_cluster_size=3,
                max_concurrent_embeddings=5,
            )

        assert len(clusters) == 1
        cluster = clusters[0]
        assert isinstance(cluster, OrphanCluster)
        assert set(cluster.member_ids) == {"orph_0", "orph_1", "orph_2"}
        assert cluster.cluster_id.startswith("sem_cluster_")
        assert len(cluster.centroid_embedding) == 4
        assert cluster.avg_pairwise_cosine > 0.9

    @pytest.mark.asyncio
    async def test_cluster_skips_below_min_size(self) -> None:
        """A cluster of size 2 is discarded when min_cluster_size=3."""
        # Two similar + two dissimilar
        fake_embeddings = [
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        call_order = iter(fake_embeddings)

        async def fake_embed(*_args: Any, **_kwargs: Any) -> list[float]:
            return next(call_order)

        orphans = [_orphan(f"orph_{i}") for i in range(4)]

        with patch.object(orphan_clustering, "_embed_one", side_effect=fake_embed):
            clusters = await cluster_orphans_by_semantic_similarity(
                orphans,
                cosine_threshold=0.9,
                min_cluster_size=3,
            )

        assert clusters == []

    @pytest.mark.asyncio
    async def test_cluster_fails_open_on_embedding_error(self) -> None:
        """When Ollama is unreachable, returns [] without raising."""

        async def fake_embed(*_args: Any, **_kwargs: Any) -> list[float] | None:
            return None  # simulate httpx ConnectionError swallowed inside _embed_one

        orphans = [_orphan(f"orph_{i}") for i in range(5)]

        with patch.object(orphan_clustering, "_embed_one", side_effect=fake_embed):
            clusters = await cluster_orphans_by_semantic_similarity(orphans)

        assert clusters == []

    @pytest.mark.asyncio
    async def test_cluster_empty_input(self) -> None:
        """Empty input returns empty list without calling Ollama."""
        mock_embed = AsyncMock()
        with patch.object(orphan_clustering, "_embed_one", mock_embed):
            clusters = await cluster_orphans_by_semantic_similarity([])

        assert clusters == []
        mock_embed.assert_not_called()


class TestEmbedOneFailsOpen:
    @pytest.mark.asyncio
    async def test_embed_one_returns_none_on_httpx_error(self) -> None:
        """_embed_one swallows httpx errors and returns None."""

        class BrokenClient:
            async def post(self, *_args: Any, **_kwargs: Any) -> Any:
                raise httpx.ConnectError("connection refused")

        result = await orphan_clustering._embed_one(
            BrokenClient(),  # type: ignore[arg-type]
            "http://localhost:11434",
            "nomic-embed-text",
            "some text",
        )
        assert result is None


class TestEnhanceKGFlag:
    @pytest.mark.asyncio
    async def test_enhance_kg_skips_ollama_when_flag_false(self) -> None:
        """When detect_orphan_communities=False, clustering is never invoked."""
        from backend.services.knowledge_graph import advanced_quality

        # Fake asyncpg connection that no-ops every query we exercise.
        class FakeConn:
            async def fetch(self, _sql: str, *_args: Any) -> list[Any]:
                return []

            async def fetchval(self, _sql: str, *_args: Any) -> int:
                return 0

            async def execute(self, _sql: str, *_args: Any) -> str:
                return "OK"

            async def close(self) -> None:
                return None

        async def fake_connect(_url: str) -> FakeConn:
            return FakeConn()

        mock_cluster = AsyncMock(return_value=[])

        with (
            patch.dict("os.environ", {"DATABASE_URL": "postgresql://fake/test"}),
            patch.object(advanced_quality.asyncpg, "connect", side_effect=fake_connect),
            patch.object(
                orphan_clustering,
                "cluster_orphans_by_semantic_similarity",
                mock_cluster,
            ),
        ):
            stats = await advanced_quality.enhance_kg_quality(
                collection="test_collection",
                apply_normalization=False,
                detect_hierarchy=False,
                apply_domain_rules=False,
                detect_orphan_communities=False,
                dry_run=True,
            )

        assert stats.semantic_clusters_formed == 0
        assert stats.entities_clustered == 0
        mock_cluster.assert_not_called()
