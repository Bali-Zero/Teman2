"""Tests for backend.services.knowledge_graph.incremental_builder"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from backend.services.knowledge_graph.incremental_builder import (
    KGIncrementalBuilder,
    run_knowledge_graph_incremental_build,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_pool() -> MagicMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


@pytest.fixture
def pool() -> MagicMock:
    return _make_pool()


@pytest.fixture
def builder(pool: MagicMock) -> KGIncrementalBuilder:
    return KGIncrementalBuilder(db_pool=pool)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_with_pool(self, pool: MagicMock) -> None:
        b = KGIncrementalBuilder(db_pool=pool)
        assert b.db_pool is pool
        assert b._gemini_client is None

    def test_without_pool(self) -> None:
        b = KGIncrementalBuilder()
        assert b.db_pool is None

    def test_class_constants(self) -> None:
        assert KGIncrementalBuilder.MAX_CHUNKS_PER_RUN == 1500
        assert KGIncrementalBuilder.MAX_RPM == 15
        assert len(KGIncrementalBuilder.HIGH_PRIORITY_COLLECTIONS) == 5


# ---------------------------------------------------------------------------
# _get_gemini_client
# ---------------------------------------------------------------------------

class TestGetGeminiClient:
    @patch("backend.services.knowledge_graph.incremental_builder.settings")
    def test_no_api_key_returns_none(self, mock_settings: MagicMock) -> None:
        mock_settings.google_api_key = None
        mock_settings.google_ai_studio_key = None
        mock_settings.google_imagen_api_key = None

        b = KGIncrementalBuilder()
        with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": MagicMock()}):
            result = b._get_gemini_client()
        assert result is None

    @patch("backend.services.knowledge_graph.incremental_builder.settings")
    def test_import_error_returns_none(self, mock_settings: MagicMock) -> None:
        mock_settings.google_api_key = "test-key-123456"

        b = KGIncrementalBuilder()
        # Force ImportError by ensuring google.genai is not importable
        with patch("builtins.__import__", side_effect=ImportError("no google")):
            result = b._get_gemini_client()
        assert result is None

    @patch("backend.services.knowledge_graph.incremental_builder.settings")
    def test_caches_client(self, mock_settings: MagicMock) -> None:
        mock_settings.google_api_key = "test-key-123456"

        mock_genai = MagicMock()
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance

        b = KGIncrementalBuilder()
        with patch.dict("sys.modules", {"google": MagicMock(genai=mock_genai), "google.genai": mock_genai}):
            with patch("backend.services.knowledge_graph.incremental_builder.settings", mock_settings):
                result1 = b._get_gemini_client()
                result2 = b._get_gemini_client()

        # Should return same instance (cached)
        assert result1 is result2


# ---------------------------------------------------------------------------
# get_processed_chunk_ids
# ---------------------------------------------------------------------------

class TestGetProcessedChunkIds:
    @pytest.mark.asyncio
    async def test_no_pool_returns_empty(self) -> None:
        b = KGIncrementalBuilder(db_pool=None)
        result = await b.get_processed_chunk_ids()
        assert result == set()

    @pytest.mark.asyncio
    async def test_returns_chunk_ids(self, pool: MagicMock) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = [
            {"chunk_id": "c1"},
            {"chunk_id": "c2"},
            {"chunk_id": "c3"},
            {"chunk_id": None},  # Should be filtered out
        ]
        b = KGIncrementalBuilder(db_pool=pool)
        result = await b.get_processed_chunk_ids()
        assert result == {"c1", "c2", "c3"}

    @pytest.mark.asyncio
    async def test_db_error_returns_empty(self, pool: MagicMock) -> None:
        conn = pool.acquire.return_value.__aenter__.return_value
        conn.fetch.side_effect = RuntimeError("DB down")
        b = KGIncrementalBuilder(db_pool=pool)
        result = await b.get_processed_chunk_ids()
        assert result == set()


# ---------------------------------------------------------------------------
# run_incremental_extraction
# ---------------------------------------------------------------------------

class TestRunIncrementalExtraction:
    @pytest.mark.asyncio
    async def test_no_pool_returns_skipped(self) -> None:
        b = KGIncrementalBuilder(db_pool=None)
        result = await b.run_incremental_extraction()
        assert result["status"] == "skipped"
        assert result["reason"] == "no_database"

    @pytest.mark.asyncio
    async def test_no_gemini_returns_skipped(self, builder: KGIncrementalBuilder) -> None:
        with patch.object(builder, "_get_gemini_client", return_value=None):
            # Need to also mock the script import to avoid file system dependency
            mock_extractor = MagicMock()
            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_extractor}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.resolve", return_value=MagicMock()):
                        result = await builder.run_incremental_extraction()

        assert result["status"] == "skipped"
        assert result["reason"] == "no_gemini_client"

    @pytest.mark.asyncio
    async def test_uses_default_collections(self, builder: KGIncrementalBuilder) -> None:
        """When no collections passed, uses HIGH_PRIORITY_COLLECTIONS."""
        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            # Mock the extractor import and instantiation
            mock_extractor_cls = MagicMock()
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.run = AsyncMock(return_value={
                "chunks_processed": 10,
                "entities_extracted": 5,
                "relationships_extracted": 3,
            })
            mock_extractor_cls.return_value = mock_extractor_instance

            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        # Patch asyncio.sleep to avoid waiting
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await builder.run_incremental_extraction()

            assert result["collections_processed"] == 5
            assert result["total_chunks"] == 50  # 10 per collection x 5

    @pytest.mark.asyncio
    async def test_custom_collections(self, builder: KGIncrementalBuilder) -> None:
        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_extractor_cls = MagicMock()
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.run = AsyncMock(return_value={
                "chunks_processed": 5,
                "entities_extracted": 2,
                "relationships_extracted": 1,
            })
            mock_extractor_cls.return_value = mock_extractor_instance

            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await builder.run_incremental_extraction(
                                collections=["visa_oracle", "tax_genius_hybrid"],
                            )

            assert result["collections_processed"] == 2

    @pytest.mark.asyncio
    async def test_daily_limit_respected(self, builder: KGIncrementalBuilder) -> None:
        """Stops processing when MAX_CHUNKS_PER_RUN is exhausted."""
        builder.MAX_CHUNKS_PER_RUN = 20  # Lower limit for test

        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_extractor_cls = MagicMock()
            mock_extractor_instance = MagicMock()
            # Each collection consumes 15 chunks
            mock_extractor_instance.run = AsyncMock(return_value={
                "chunks_processed": 15,
                "entities_extracted": 5,
                "relationships_extracted": 2,
            })
            mock_extractor_cls.return_value = mock_extractor_instance

            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await builder.run_incremental_extraction(
                                collections=["c1", "c2", "c3"],
                            )

            # First collection uses 15 of 20 quota, second should use remaining 5
            # Third should be skipped (quota exhausted)
            assert result["collections_processed"] <= 2

    @pytest.mark.asyncio
    async def test_retry_on_collection_error(self, builder: KGIncrementalBuilder) -> None:
        """Retries with exponential backoff on error."""
        call_count = 0

        async def flaky_run(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Transient error")
            return {
                "chunks_processed": 5,
                "entities_extracted": 2,
                "relationships_extracted": 1,
            }

        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_extractor_cls = MagicMock()
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.run = AsyncMock(side_effect=flaky_run)
            mock_extractor_cls.return_value = mock_extractor_instance

            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await builder.run_incremental_extraction(
                                collections=["c1"],
                                max_retries=3,
                            )

            assert result["collections_processed"] == 1
            assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, builder: KGIncrementalBuilder) -> None:
        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_extractor_cls = MagicMock()
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.run = AsyncMock(side_effect=RuntimeError("Permanent error"))
            mock_extractor_cls.return_value = mock_extractor_instance

            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            result = await builder.run_incremental_extraction(
                                collections=["c1"],
                                max_retries=2,
                            )

            assert result["collections_failed"] == 1
            assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_extractor_init_error(self, builder: KGIncrementalBuilder) -> None:
        """Returns error when KGIncrementalExtractor fails to initialize."""
        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_extractor_cls = MagicMock(side_effect=RuntimeError("init boom"))
            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = mock_extractor_cls

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = "http://localhost:6333"
                        mock_settings.qdrant_api_key = "test"
                        mock_settings.google_api_key = "test"
                        result = await builder.run_incremental_extraction(collections=["c1"])

        assert result["status"] == "error"
        assert "init boom" in result["error"]

    @pytest.mark.asyncio
    async def test_no_qdrant_url(self, builder: KGIncrementalBuilder) -> None:
        """Returns error when QDRANT_URL is not configured."""
        with patch.object(builder, "_get_gemini_client", return_value=MagicMock()):
            mock_module = MagicMock()
            mock_module.KGIncrementalExtractor = MagicMock()

            with patch.dict("sys.modules", {"kg_incremental_extraction": mock_module}):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch(
                        "backend.services.knowledge_graph.incremental_builder.settings",
                    ) as mock_settings:
                        mock_settings.qdrant_url = None
                        mock_settings.qdrant_api_key = None
                        with patch.dict("os.environ", {}, clear=False):
                            # Remove QDRANT_URL from env too
                            import os
                            orig = os.environ.pop("QDRANT_URL", None)
                            try:
                                result = await builder.run_incremental_extraction(
                                    collections=["c1"],
                                )
                            finally:
                                if orig is not None:
                                    os.environ["QDRANT_URL"] = orig

        assert result["status"] == "error"
        assert "QDRANT_URL" in result["error"]


# ---------------------------------------------------------------------------
# run_knowledge_graph_incremental_build (module-level entry point)
# ---------------------------------------------------------------------------

class TestEntryPoint:
    @pytest.mark.asyncio
    @patch(
        "backend.services.knowledge_graph.incremental_builder.KGIncrementalBuilder.run_incremental_extraction",
        new_callable=AsyncMock,
        return_value={"status": "ok", "collections_processed": 3},
    )
    async def test_entry_point(self, mock_run: AsyncMock) -> None:
        pool = _make_pool()
        result = await run_knowledge_graph_incremental_build(pool)
        assert result["status"] == "ok"
        mock_run.assert_awaited_once()
