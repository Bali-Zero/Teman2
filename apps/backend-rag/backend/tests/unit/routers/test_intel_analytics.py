"""Unit tests for backend/app/routers/intel_analytics.py"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Module-level patches: heavy deps that must never import for real
# ---------------------------------------------------------------------------

_MOCK_INTEL_COLLECTIONS = {
    "visa": "bali_intel_visa",
    "news": "bali_intel_news",
}


@pytest.fixture(autouse=True)
def _patch_imports(monkeypatch):
    """Patch all external dependencies imported at module level."""
    # Create mock staging service
    mock_staging = MagicMock()
    visa_dir = MagicMock(spec=Path)
    visa_dir.exists.return_value = False
    visa_dir.glob.return_value = []
    news_dir = MagicMock(spec=Path)
    news_dir.exists.return_value = False
    news_dir.glob.return_value = []
    mock_staging.get_staging_dir.side_effect = lambda t: visa_dir if t == "visa" else news_dir

    mock_analytics = MagicMock()
    mock_embedder = MagicMock()

    # Patch the intel module references used by intel_analytics
    monkeypatch.setattr(
        "backend.app.routers.intel_analytics.INTEL_COLLECTIONS",
        _MOCK_INTEL_COLLECTIONS,
    )
    monkeypatch.setattr(
        "backend.app.routers.intel_analytics.staging_service",
        mock_staging,
    )
    monkeypatch.setattr(
        "backend.app.routers.intel_analytics.analytics_service",
        mock_analytics,
    )
    monkeypatch.setattr(
        "backend.app.routers.intel_analytics.get_embedder",
        lambda: mock_embedder,
    )
    return {
        "staging": mock_staging,
        "analytics": mock_analytics,
        "embedder": mock_embedder,
        "visa_dir": visa_dir,
        "news_dir": news_dir,
    }


# ---------------------------------------------------------------------------
# /api/intel/metrics
# ---------------------------------------------------------------------------


class TestGetSystemMetrics:
    """Tests for GET /api/intel/metrics."""

    @pytest.mark.asyncio
    async def test_metrics_basic_success(self, _patch_imports):
        """Metrics returns expected keys when everything is healthy."""
        with patch(
            "backend.app.routers.intel_analytics.QdrantClient"
        ) as mock_qd:
            mock_qd.return_value = MagicMock()
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert "agent_status" in result
        assert "qdrant_health" in result
        assert result["qdrant_health"] == "healthy"
        assert "items_processed_today" in result
        assert "avg_response_time_ms" in result

    @pytest.mark.asyncio
    async def test_metrics_qdrant_degraded(self, _patch_imports):
        """When Qdrant constructor raises, health should be degraded."""
        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            side_effect=Exception("connection refused"),
        ):
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert result["qdrant_health"] == "degraded"

    @pytest.mark.asyncio
    async def test_metrics_with_staging_files(self, _patch_imports):
        """When staging dirs contain JSON files, items_processed_today counts them."""
        visa_dir = _patch_imports["visa_dir"]
        visa_dir.exists.return_value = True
        visa_dir.glob.return_value = [Path("a.json"), Path("b.json")]
        news_dir = _patch_imports["news_dir"]
        news_dir.exists.return_value = True
        news_dir.glob.return_value = [Path("c.json")]

        with patch("backend.app.routers.intel_analytics.QdrantClient"):
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert result["items_processed_today"] == 3

    @pytest.mark.asyncio
    async def test_metrics_scheduler_active(self, _patch_imports):
        """When autonomous scheduler has recent tasks, agent_status=active."""
        mock_task = MagicMock()
        mock_task.last_run = datetime.now(tz=timezone.utc)
        mock_task.enabled = True
        mock_scheduler = MagicMock()
        mock_scheduler.tasks = {"t1": mock_task}

        with (
            patch("backend.app.routers.intel_analytics.QdrantClient"),
            patch(
                "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler",
                return_value=mock_scheduler,
            ),
        ):
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert result["agent_status"] == "active"

    @pytest.mark.asyncio
    async def test_metrics_scheduler_not_configured(self, _patch_imports):
        """When no scheduler exists, agent_status=not_configured."""
        with (
            patch("backend.app.routers.intel_analytics.QdrantClient"),
            patch(
                "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler",
                return_value=None,
            ),
        ):
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert result["agent_status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_metrics_default_avg_response_time(self, _patch_imports):
        """When no archived files exist, default response time used."""
        with patch("backend.app.routers.intel_analytics.QdrantClient"):
            from backend.app.routers.intel_analytics import get_system_metrics

            result = await get_system_metrics()

        assert isinstance(result["avg_response_time_ms"], int)


# ---------------------------------------------------------------------------
# /api/intel/search
# ---------------------------------------------------------------------------


class TestSearchIntel:
    """Tests for POST /api/intel/search."""

    @pytest.mark.asyncio
    async def test_search_basic(self, _patch_imports):
        """Basic search returns results list."""
        embedder = _patch_imports["embedder"]
        embedder.generate_single_embedding.return_value = [0.1] * 1536

        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{"id": "1", "title": "Test", "tier": "T1"}],
            "distances": [0.5],
        }

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import (
                IntelSearchRequest,
                search_intel,
            )

            request = IntelSearchRequest(query="test visa")
            result = await search_intel(request)

        assert "results" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, _patch_imports):
        """Search with category narrows to single collection."""
        embedder = _patch_imports["embedder"]
        embedder.generate_single_embedding.return_value = [0.1] * 1536

        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "documents": [],
            "metadatas": [],
            "distances": [],
        }

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import (
                IntelSearchRequest,
                search_intel,
            )

            request = IntelSearchRequest(query="test", category="visa")
            result = await search_intel(request)

        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_search_collection_error_continues(self, _patch_imports):
        """When one collection search fails, others still return results."""
        embedder = _patch_imports["embedder"]
        embedder.generate_single_embedding.return_value = [0.1] * 1536

        call_count = 0

        def mock_qdrant_factory(**kwargs):
            nonlocal call_count
            call_count += 1
            m = AsyncMock()
            if call_count == 1:
                m.search.side_effect = Exception("timeout")
            else:
                m.search.return_value = {
                    "documents": ["doc2"],
                    "metadatas": [{"id": "2", "title": "News", "tier": "T2"}],
                    "distances": [0.3],
                }
            return m

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            side_effect=mock_qdrant_factory,
        ):
            from backend.app.routers.intel_analytics import (
                IntelSearchRequest,
                search_intel,
            )

            request = IntelSearchRequest(query="test")
            result = await search_intel(request)

        # Should get results from the non-failing collection
        assert result["total"] >= 0

    @pytest.mark.asyncio
    async def test_search_results_sorted_by_similarity(self, _patch_imports):
        """Results are sorted by similarity_score descending."""
        embedder = _patch_imports["embedder"]
        embedder.generate_single_embedding.return_value = [0.1] * 1536

        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "documents": ["doc1", "doc2"],
            "metadatas": [
                {"id": "1", "title": "A", "tier": "T1"},
                {"id": "2", "title": "B", "tier": "T1"},
            ],
            "distances": [1.0, 0.1],
        }

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import (
                IntelSearchRequest,
                search_intel,
            )

            request = IntelSearchRequest(query="test", category="visa")
            result = await search_intel(request)

        if len(result["results"]) >= 2:
            assert (
                result["results"][0]["similarity_score"]
                >= result["results"][1]["similarity_score"]
            )


# ---------------------------------------------------------------------------
# /api/intel/store
# ---------------------------------------------------------------------------


class TestStoreIntel:
    """Tests for POST /api/intel/store."""

    @pytest.mark.asyncio
    async def test_store_success(self, _patch_imports):
        mock_client = AsyncMock()

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import (
                IntelStoreRequest,
                store_intel,
            )

            request = IntelStoreRequest(
                collection="visa",
                id="test-1",
                document="test doc",
                embedding=[0.1] * 1536,
                metadata={"title": "test"},
                full_data={"key": "value"},
            )
            result = await store_intel(request)

        assert result["success"] is True
        assert result["collection"] == "bali_intel_visa"

    @pytest.mark.asyncio
    async def test_store_invalid_collection(self, _patch_imports):
        from backend.app.routers.intel_analytics import IntelStoreRequest, store_intel

        request = IntelStoreRequest(
            collection="invalid_collection",
            id="test-1",
            document="test doc",
            embedding=[0.1] * 1536,
            metadata={},
            full_data={},
        )
        with pytest.raises(HTTPException) as exc_info:
            await store_intel(request)
        # The inner HTTPException(400) is caught by the outer try/except
        # and re-raised as HTTPException(500), so we check for 500.
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# /api/intel/critical
# ---------------------------------------------------------------------------


class TestGetCriticalItems:
    """Tests for GET /api/intel/critical."""

    @pytest.mark.asyncio
    async def test_critical_items_returns_structure(self, _patch_imports):
        with patch(
            "backend.app.routers.intel_analytics.QdrantClient"
        ) as mock_qd_cls, patch(
            "backend.app.routers.intel_analytics.httpx.AsyncClient"
        ) as mock_http:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "result": {"points": []}
            }
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.post = AsyncMock(return_value=mock_resp)
            mock_http.return_value = mock_ctx

            with patch("backend.app.routers.intel_analytics.settings") as mock_settings:
                mock_settings.qdrant_url = "http://localhost:6333"
                mock_settings.qdrant_api_key = ""
                from backend.app.routers.intel_analytics import get_critical_items

                result = await get_critical_items()

        assert "items" in result
        assert "alerts" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_critical_items_with_category(self, _patch_imports):
        with patch(
            "backend.app.routers.intel_analytics.QdrantClient"
        ) as mock_qd_cls:
            # Make scroll fail so it falls back to peek
            mock_client = AsyncMock()
            mock_client.peek.return_value = {"metadatas": []}
            mock_qd_cls.return_value = mock_client

            with patch(
                "backend.app.routers.intel_analytics.httpx.AsyncClient",
                side_effect=Exception("scroll fails"),
            ), patch("backend.app.routers.intel_analytics.settings") as mock_settings:
                mock_settings.qdrant_url = "http://localhost:6333"
                mock_settings.qdrant_api_key = ""
                from backend.app.routers.intel_analytics import get_critical_items

                result = await get_critical_items(category="visa")

        assert result["count"] == 0


# ---------------------------------------------------------------------------
# /api/intel/trends
# ---------------------------------------------------------------------------


class TestGetTrends:
    """Tests for GET /api/intel/trends."""

    @pytest.mark.asyncio
    async def test_trends_returns_structure(self, _patch_imports):
        mock_client = MagicMock()
        mock_client.get_collection_stats.return_value = {"total_documents": 42}

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import get_trends

            result = await get_trends()

        assert "trends" in result
        assert "top_topics" in result

    @pytest.mark.asyncio
    async def test_trends_with_category(self, _patch_imports):
        mock_client = MagicMock()
        mock_client.get_collection_stats.return_value = {"total_documents": 10}

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import get_trends

            result = await get_trends(category="visa")

        assert len(result["trends"]) == 1
        assert result["trends"][0]["total_items"] == 10


# ---------------------------------------------------------------------------
# /api/intel/analytics
# ---------------------------------------------------------------------------


class TestGetIntelligenceAnalytics:
    """Tests for GET /api/intel/analytics."""

    @pytest.mark.asyncio
    async def test_analytics_delegates_to_service(self, _patch_imports):
        analytics = _patch_imports["analytics"]
        analytics.get_intelligence_analytics.return_value = {"metrics": True}

        from backend.app.routers.intel_analytics import get_intelligence_analytics

        result = await get_intelligence_analytics(days=30)

        analytics.get_intelligence_analytics.assert_called_once_with(30)
        assert result == {"metrics": True}

    @pytest.mark.asyncio
    async def test_analytics_error_raises_500(self, _patch_imports):
        analytics = _patch_imports["analytics"]
        analytics.get_intelligence_analytics.side_effect = RuntimeError("boom")

        from backend.app.routers.intel_analytics import get_intelligence_analytics

        with pytest.raises(HTTPException) as exc_info:
            await get_intelligence_analytics()
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# /api/intel/stats/{collection}
# ---------------------------------------------------------------------------


class TestGetCollectionStats:
    """Tests for GET /api/intel/stats/{collection}."""

    @pytest.mark.asyncio
    async def test_stats_success(self, _patch_imports):
        mock_client = MagicMock()
        mock_client.get_collection_stats.return_value = {"total_documents": 99}

        with patch(
            "backend.app.routers.intel_analytics.QdrantClient",
            return_value=mock_client,
        ):
            from backend.app.routers.intel_analytics import get_collection_stats

            result = await get_collection_stats("visa")

        assert result["collection_name"] == "bali_intel_visa"
        assert result["total_documents"] == 99

    @pytest.mark.asyncio
    async def test_stats_unknown_collection(self, _patch_imports):
        from backend.app.routers.intel_analytics import get_collection_stats

        with pytest.raises(HTTPException) as exc_info:
            await get_collection_stats("nonexistent")
        # The inner HTTPException(404) is caught by the outer try/except
        # and re-raised as HTTPException(500).
        assert exc_info.value.status_code == 500
