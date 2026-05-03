"""Tests for portal matters listing endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.app.routers.portal_matters import _shape_matter


def _row(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "KITAS",
        "category": "visa",
        "status": "in_progress",
        "missing_documents": "passport_scan, bank_statement",
        "expiry_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def test_shape_matter_maps_category_and_progress() -> None:
    matter = _shape_matter(_row())
    assert matter["type"] == "visa"
    assert matter["progress"] == 60  # 'in_progress' → 60
    assert matter["pending_docs"] == ["passport_scan", "bank_statement"]
    assert matter["next_deadline"].startswith("2026-12-31")


def test_shape_matter_unknown_category_becomes_other() -> None:
    matter = _shape_matter(_row(category="random"))
    assert matter["type"] == "other"


def test_shape_matter_empty_docs() -> None:
    matter = _shape_matter(_row(missing_documents=None))
    assert matter["pending_docs"] == []


def test_shape_matter_docs_as_list() -> None:
    matter = _shape_matter(_row(missing_documents=["passport", "visa"]))
    assert matter["pending_docs"] == ["passport", "visa"]


@pytest.mark.asyncio
async def test_list_matters_endpoint_returns_empty_when_table_missing() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers.portal import get_current_client
    from backend.app.routers.portal_matters import router

    app = FastAPI()
    app.include_router(router)

    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("relation 'practices' does not exist")

    class _PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _PoolCtx()

    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[get_database_pool] = lambda: _Pool()

    client = TestClient(app)
    r = client.get("/api/portal/matters")
    assert r.status_code == 200
    assert r.json() == {"matters": []}
