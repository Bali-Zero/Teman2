"""
Unit tests for GET /api/ingest/stats (backend/app/routers/ingest.py).

Regression test for a live production 500:
    'QdrantClient' object has no attribute 'get_collection_stats'

Root cause: the handler called `db.get_collection_stats()` (sync, no such
method) on `backend.core.qdrant_db.QdrantClient`, whose real API is the
async `get_stats()` method. The mock in the legacy test suite
(apps/backend-rag/tests/unit/routers/test_ingest_router.py) used a bare
MagicMock() that happily accepted the phantom attribute, so the bug never
surfaced in CI.

These tests patch QdrantClient with `spec=QdrantClient` (or assert against
the real class's attribute set) so a call to a non-existent method raises
AttributeError exactly like production did -- proving guilt on the old
code and innocence on the fixed code.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.ingest import get_ingestion_stats
from backend.core.qdrant_db import QdrantClient


@pytest.mark.asyncio
async def test_get_ingestion_stats_uses_real_qdrant_client_api():
    """
    Guilt check: QdrantClient has no `get_collection_stats` attribute.

    A spec'd mock enforces this -- if the handler still called the phantom
    method, this test would raise AttributeError, exactly mirroring the
    live prod crash.
    """
    with patch("backend.app.routers.ingest.QdrantClient") as mock_client_class:
        mock_instance = AsyncMock(spec=QdrantClient)
        mock_instance.collection_name = "knowledge_base"
        mock_instance.qdrant_url = "http://localhost:6333"
        mock_instance.get_stats.return_value = {
            "collection_name": "knowledge_base",
            "total_documents": 42,
            "vector_size": 1536,
            "distance": "Cosine",
            "status": "green",
        }
        mock_client_class.return_value = mock_instance

        # spec=QdrantClient means calling a nonexistent method would raise
        # AttributeError -- confirm the phantom method truly does not exist.
        assert not hasattr(mock_instance, "get_collection_stats")

        result = await get_ingestion_stats()

    assert result["status"] == "success"
    assert result["collection"] == "knowledge_base"
    assert result["total_documents"] == 42
    assert result["tiers_distribution"] == {}
    mock_instance.get_stats.assert_awaited_once()
    mock_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ingestion_stats_defaults_when_qdrant_returns_error_shape():
    """
    QdrantClient.get_stats() never raises -- on HTTP failure it returns
    {"collection_name": ..., "error": ...} without total_documents. The
    handler must degrade gracefully (default 0) instead of KeyError-ing.
    """
    with patch("backend.app.routers.ingest.QdrantClient") as mock_client_class:
        mock_instance = AsyncMock(spec=QdrantClient)
        mock_instance.collection_name = "knowledge_base"
        mock_instance.qdrant_url = "http://localhost:6333"
        mock_instance.get_stats.return_value = {
            "collection_name": "knowledge_base",
            "error": "HTTP 503",
        }
        mock_client_class.return_value = mock_instance

        result = await get_ingestion_stats()

    assert result["status"] == "success"
    assert result["collection"] == "knowledge_base"
    assert result["total_documents"] == 0
    mock_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ingestion_stats_closes_client_and_raises_500_on_exception():
    """Connection-level exceptions still map to HTTP 500, and the client is closed."""
    with patch("backend.app.routers.ingest.QdrantClient") as mock_client_class:
        mock_instance = AsyncMock(spec=QdrantClient)
        mock_instance.collection_name = "knowledge_base"
        mock_instance.qdrant_url = "http://localhost:6333"
        mock_instance.get_stats.side_effect = RuntimeError("connection refused")
        mock_client_class.return_value = mock_instance

        with pytest.raises(HTTPException) as exc_info:
            await get_ingestion_stats()

    assert exc_info.value.status_code == 500
    assert "connection refused" in exc_info.value.detail
    mock_instance.close.assert_awaited_once()
