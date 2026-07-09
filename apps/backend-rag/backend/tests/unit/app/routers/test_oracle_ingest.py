"""
Tests for Oracle INGEST Router — GET /api/oracle/collections + POST /api/oracle/ingest

Regression coverage for the live prod 500:
    'SearchService' object has no attribute 'collections'

`SearchService` never had a `.collections` dict attribute — collection access
always went through `SearchService.collection_manager` (a `CollectionManager`
instance). The router code accessed `service.collections` directly, which
raises `AttributeError` on any real `SearchService` instance and surfaces as
an HTTP 500 via the router's broad `except Exception` handler.

These tests call the router coroutines directly (no live DB/Qdrant/network)
against a mock that mirrors the REAL `SearchService`/`CollectionManager`
shape: an object that raises AttributeError on `.collections` (proving guilt
for the old code) but exposes the real `collection_manager` surface
(`get_all_collections`, `get_collection`, `list_collections`) that the fixed
code must use (proving innocence for the fix).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers.oracle_ingest import (
    DocumentChunk,
    IngestRequest,
    ingest_documents,
    list_collections,
)


class _NoDunderCollections:
    """
    Stand-in for the real `SearchService`.

    Deliberately has NO `.collections` attribute (matching production:
    `SearchService.__init__` never sets `self.collections`) so that any
    code path still doing `service.collections` raises AttributeError,
    exactly like the live 500 captured in prod.
    """


def _make_fake_qdrant_client(name: str, total_documents: int = 5) -> MagicMock:
    client = MagicMock()
    client.get_stats = AsyncMock(return_value={"total_documents": total_documents})
    client.upsert_documents = AsyncMock(return_value=None)
    return client


def _make_service_with_collection_manager(collections: dict[str, MagicMock]) -> _NoDunderCollections:
    service = _NoDunderCollections()
    manager = MagicMock()
    manager.get_all_collections.return_value = dict(collections)
    manager.get_collection.side_effect = lambda name: collections.get(name)
    manager.list_collections.return_value = list(collections.keys())
    manager._collections_cache = dict(collections)
    service.collection_manager = manager  # type: ignore[attr-defined]
    return service


# ============================================================================
# GUILT: the old `service.collections` access pattern is not present on a
# realistic SearchService double — accessing it raises AttributeError, which
# is exactly the prod symptom ("'SearchService' object has no attribute
# 'collections'").
# ============================================================================


def test_guilt_bare_service_has_no_collections_attribute():
    service = _NoDunderCollections()
    with pytest.raises(AttributeError):
        _ = service.collections  # type: ignore[attr-defined]


# ============================================================================
# INNOCENCE: GET /api/oracle/collections via the fixed handler
# ============================================================================


@pytest.mark.asyncio
async def test_list_collections_returns_real_collections_via_collection_manager():
    fake_visa = _make_fake_qdrant_client("visa_oracle", total_documents=1612)
    fake_pricing = _make_fake_qdrant_client("bali_zero_pricing_hybrid", total_documents=29)
    service = _make_service_with_collection_manager(
        {"visa_oracle": fake_visa, "bali_zero_pricing_hybrid": fake_pricing}
    )

    result: dict[str, Any] = await list_collections(service=service)  # type: ignore[arg-type]

    assert result["success"] is True
    assert set(result["collections"]) == {"visa_oracle", "bali_zero_pricing_hybrid"}
    assert result["details"]["visa_oracle"]["document_count"] == 1612
    assert result["details"]["bali_zero_pricing_hybrid"]["document_count"] == 29
    # get_stats is async and must actually be awaited (not called sync)
    fake_visa.get_stats.assert_awaited_once()
    fake_pricing.get_stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_collections_handles_empty_collection_manager():
    service = _make_service_with_collection_manager({})

    result = await list_collections(service=service)  # type: ignore[arg-type]

    assert result["success"] is True
    assert result["collections"] == []
    assert result["details"] == {}


@pytest.mark.asyncio
async def test_list_collections_per_collection_stats_error_is_isolated():
    """A single collection's get_stats() failure must not 500 the whole endpoint."""
    broken = MagicMock()
    broken.get_stats = AsyncMock(side_effect=RuntimeError("qdrant unreachable"))
    healthy = _make_fake_qdrant_client("visa_oracle", total_documents=10)
    service = _make_service_with_collection_manager({"broken_col": broken, "visa_oracle": healthy})

    result = await list_collections(service=service)  # type: ignore[arg-type]

    assert result["success"] is True
    assert result["details"]["broken_col"]["document_count"] == 0
    assert "error" in result["details"]["broken_col"]
    assert result["details"]["visa_oracle"]["document_count"] == 10


# ============================================================================
# INNOCENCE: POST /api/oracle/ingest — sibling call-sites (W89 class-audit)
# also went through `service.collections`; verify they now use
# collection_manager correctly for both the "known collection" and
# "unknown collection" branches.
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_known_collection_uses_collection_manager_get_collection(monkeypatch):
    fake_client = _make_fake_qdrant_client("visa_oracle")
    service = _make_service_with_collection_manager({"visa_oracle": fake_client})

    fake_embedder = MagicMock()
    fake_embedder.generate_batch_embeddings = AsyncMock(return_value=[[0.1, 0.2]])
    monkeypatch.setattr(
        "backend.app.routers.oracle_ingest.create_embeddings_generator",
        lambda: fake_embedder,
    )

    request = IngestRequest(
        collection="visa_oracle",
        documents=[DocumentChunk(content="some legal text here", metadata={"law_id": "X"})],
    )

    response = await ingest_documents(request=request, service=service)  # type: ignore[arg-type]

    assert response.success is True
    assert response.documents_ingested == 1
    fake_client.upsert_documents.assert_awaited_once()
    service.collection_manager.get_collection.assert_called_with("visa_oracle")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ingest_unknown_collection_reports_not_found_without_attributeerror():
    service = _make_service_with_collection_manager({"visa_oracle": _make_fake_qdrant_client("visa_oracle")})

    request = IngestRequest(
        collection="totally_unknown_collection",
        documents=[DocumentChunk(content="some legal text here", metadata={"law_id": "X"})],
    )

    response = await ingest_documents(request=request, service=service)  # type: ignore[arg-type]

    assert response.success is False
    assert response.message == "Collection not found"
    assert "totally_unknown_collection" in (response.error or "")
    assert "visa_oracle" in (response.error or "")
