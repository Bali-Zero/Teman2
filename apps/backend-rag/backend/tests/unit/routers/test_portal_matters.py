"""Tests for portal matters listing and detail endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.app.routers.portal_matters import (
    _client_safe_intelligence_from_rows,
    _sanitize_client_label,
    _sanitize_client_text,
    _shape_matter,
    _shape_matter_detail,
)


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


def test_shape_matter_detail_adds_plain_language_status() -> None:
    matter = _shape_matter_detail(_row(status="waiting_documents"))

    assert matter["status_label"] == "Waiting for documents"
    assert matter["description"] == "We are waiting for the documents listed below."
    assert matter["next_step"] == "Upload requested documents"


def test_client_safe_intelligence_hides_source_fields_and_backend_jargon() -> None:
    rows = [
        {
            "company_name": "PT Safe Client Story",
            "approved_at": datetime(2026, 5, 17, tzinfo=timezone.utc),
            "facts": [
                {
                    "category": "identity",
                    "label": "Drive source",
                    "detail": (
                        "KG/OCR found this in https://drive.google.com/file/d/raw-id/view "
                        "and drive.google.com/file/d/bare-id/view from source_file_ids and NotebookLM."
                    ),
                    "source_file_ids": ["raw-drive-id"],
                    "confidence": "confirmed",
                },
                {
                    "category": "gap",
                    "label": "Internal source gap",
                    "detail": "Run OCR on the source folder before client approval.",
                    "source_file_ids": ["raw-gap-id"],
                    "confidence": "medium",
                },
                {
                    "category": "next_action",
                    "label": "Backend task",
                    "detail": "Review the company status with the client.",
                    "source_file_ids": ["raw-next-id"],
                    "confidence": "medium",
                },
            ],
        }
    ]

    result = _client_safe_intelligence_from_rows(rows)
    serialized = json.dumps(result)

    assert result["available"] is True
    assert result["company_name"] == "PT Safe Client Story"
    assert result["summary"]
    assert result["facts"][0]["label"] == "Document record"
    assert result["missing_items"] == [
        "Review the document on the document record before client approval."
    ]
    assert result["next_steps"] == ["Review the company status with the client."]
    assert "drive.google.com" not in serialized
    assert "source_file_ids" not in serialized
    assert "raw-drive-id" not in serialized
    assert "Drive source" not in serialized
    assert "KG" not in serialized
    assert "OCR" not in serialized
    assert "NotebookLM" not in serialized
    assert "Backend" not in serialized


def test_client_safe_sanitizers_preserve_ordinary_words() -> None:
    assert _sanitize_client_text("Please bring your drive license copy.") == (
        "Please bring your drive license copy."
    )
    assert _sanitize_client_label("Backend office status") == "Backend office status"


def test_client_safe_intelligence_preserves_plain_company_name_and_confidence() -> None:
    rows = [
        {
            "company_name": "Backend Office PT",
            "approved_at": datetime(2026, 5, 17, tzinfo=timezone.utc),
            "facts": [
                {
                    "category": "identity",
                    "label": "Backend office status",
                    "detail": "The company is ready for client review.",
                    "confidence": "kg-verified",
                }
            ],
        }
    ]

    result = _client_safe_intelligence_from_rows(rows)

    assert result["company_name"] == "Backend Office PT"
    assert result["facts"][0]["label"] == "Backend office status"
    assert result["facts"][0]["confidence"] == "medium"


def test_client_safe_intelligence_withholds_when_multiple_companies_match() -> None:
    rows = [
        {
            "company_name": "PT One",
            "approved_at": datetime(2026, 5, 17, tzinfo=timezone.utc),
            "facts": [{"category": "identity", "detail": "One", "label": "Company"}],
        },
        {
            "company_name": "PT Two",
            "approved_at": datetime(2026, 5, 17, tzinfo=timezone.utc),
            "facts": [{"category": "identity", "detail": "Two", "label": "Company"}],
        },
    ]

    result = _client_safe_intelligence_from_rows(rows)

    assert result["available"] is False
    assert result["summary"] is None
    assert result["facts"] == []


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


@pytest.mark.asyncio
async def test_get_matter_detail_returns_client_safe_approved_intelligence() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers.portal import get_current_client
    from backend.app.routers.portal_matters import router

    app = FastAPI()
    app.include_router(router)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = _row(id=9, title="Company Setup", category="company")
    mock_conn.fetch.return_value = [
        {
            "company_name": "PT Safe Client Story",
            "approved_at": datetime(2026, 5, 17, tzinfo=timezone.utc),
            "facts": [
                {
                    "category": "identity",
                    "label": "Company status",
                    "detail": "The company profile is approved for client review.",
                    "source_file_ids": ["hidden-source"],
                    "confidence": "confirmed",
                },
                {
                    "category": "next_action",
                    "label": "Next step",
                    "detail": "Confirm the next filing date.",
                    "source_file_ids": ["hidden-next"],
                    "confidence": "medium",
                },
            ],
        }
    ]

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
    r = client.get("/api/portal/matters/9")

    assert r.status_code == 200
    payload = r.json()
    assert payload["matter"]["id"] == 9
    assert payload["matter"]["approved_intelligence"]["available"] is True
    assert payload["matter"]["approved_intelligence"]["facts"] == [
        {
            "category": "identity",
            "label": "Company status",
            "detail": "The company profile is approved for client review.",
            "confidence": "confirmed",
        }
    ]
    assert "source_file_ids" not in json.dumps(payload)
    fetch_sql = mock_conn.fetch.await_args.args[0]
    assert "snap.client_id = $1" in fetch_sql
    assert "active_company_scope" in fetch_sql
    assert "ccl.status = 'active'" in fetch_sql
    assert "ccl.end_date IS NULL" in fetch_sql
    assert "HAVING (SELECT COUNT(*) FROM active_company_scope) = 1" in fetch_sql
    assert "LIMIT 1" in fetch_sql


@pytest.mark.asyncio
async def test_get_matter_detail_does_not_fetch_intelligence_for_tax_matter() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers.portal import get_current_client
    from backend.app.routers.portal_matters import router

    app = FastAPI()
    app.include_router(router)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = _row(id=11, title="Monthly Tax", category="tax")

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
    r = client.get("/api/portal/matters/11")

    assert r.status_code == 200
    assert r.json()["matter"]["approved_intelligence"]["available"] is False
    mock_conn.fetch.assert_not_awaited()
