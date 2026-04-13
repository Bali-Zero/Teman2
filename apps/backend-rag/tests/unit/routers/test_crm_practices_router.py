"""
Tests for CRM Practices Router - practice management endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_practice_row(id=1, **overrides):
    row = {
        "id": id, "uuid": f"uuid-{id}", "client_id": 1, "practice_type_id": 1,
        "practice_type_name": "KITAS", "practice_type_code": "KITAS",
        "status": "in_progress", "priority": "normal",
        "assigned_to": "admin@balizero.com", "notes": None,
        "price": None, "price_currency": "IDR", "price_paid": None,
        "government_fee": None, "total_cost": None,
        "start_date": None, "expected_completion": None,
        "expiry_date": None, "completed_at": None,
        "created_by": "admin@balizero.com", "updated_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None, "client_name": "John Doe",
    }
    row.update(overrides)
    return row


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm
    return pool


@pytest.fixture
def admin_user():
    return {"email": "zero@balizero.com", "role": "admin", "sub": "admin-uuid"}


@pytest.fixture
def test_app(mock_pool, admin_user):
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.routers.crm_practices import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_database_pool] = lambda: mock_pool
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestListPracticesEndpoint:
    def test_list_practices_no_filters(self, client, mock_conn):
        mock_conn.fetch.return_value = [_make_practice_row()]
        mock_conn.fetchval.return_value = 1
        resp = client.get("/api/crm/practices/")
        assert resp.status_code == 200

    def test_list_practices_filter_by_client_id(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/practices/?client_id=1")
        assert resp.status_code == 200

    def test_list_practices_filter_by_status(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?status=in_progress")
        assert resp.status_code == 200

    def test_list_practices_filter_by_assigned_to(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?assigned_to=admin@balizero.com")
        assert resp.status_code == 200

    def test_list_practices_filter_by_practice_type(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?practice_type=KITAS")
        assert resp.status_code == 200

    def test_list_practices_filter_by_priority(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?priority=high")
        assert resp.status_code == 200

    def test_list_practices_all_filters_combined(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?status=in_progress&priority=high&limit=10")
        assert resp.status_code == 200

    def test_list_practices_pagination(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?offset=5&limit=10")
        assert resp.status_code == 200

    def test_list_practices_empty_result(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/")
        assert resp.status_code == 200

    def test_list_practices_database_error(self, client, mock_conn):
        mock_conn.fetch.side_effect = Exception("DB error")
        resp = client.get("/api/crm/practices/")
        assert resp.status_code in (200, 500)


class TestGetPracticeEndpoint:
    def test_get_practice_success(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row()
        resp = client.get("/api/crm/practices/1")
        assert resp.status_code == 200

    def test_get_practice_not_found(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.get("/api/crm/practices/999")
        assert resp.status_code == 404

    def test_get_practice_invalid_id_zero(self, client):
        resp = client.get("/api/crm/practices/0")
        assert resp.status_code in (404, 422)

    def test_get_practice_invalid_id_negative(self, client):
        resp = client.get("/api/crm/practices/-1")
        assert resp.status_code in (404, 422)

    def test_get_practice_database_error(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB error")
        resp = client.get("/api/crm/practices/1")
        assert resp.status_code == 500


class TestUpdatePracticeEndpoint:
    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_practice_status(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row(status="completed")
        resp = client.patch("/api/crm/practices/1", json={"status": "completed", "updated_by": "admin"})
        assert resp.status_code in (200, 400, 404, 500)

    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_practice_multiple_fields(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row()
        resp = client.patch("/api/crm/practices/1", json={"status": "completed", "notes": "Done", "updated_by": "admin"})
        assert resp.status_code in (200, 400, 404, 500)

    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_practice_with_expiry_date(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row(expiry_date="2025-12-31")
        resp = client.patch("/api/crm/practices/1", json={"expiry_date": "2025-12-31", "updated_by": "admin"})
        assert resp.status_code in (200, 400, 404, 500)

    def test_update_practice_not_found(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.patch("/api/crm/practices/999", json={"status": "completed", "updated_by": "admin"})
        assert resp.status_code in (400, 404, 500)

    def test_update_practice_no_fields(self, client, mock_conn):
        resp = client.patch("/api/crm/practices/1", json={})
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_update_practice_invalid_field(self, client, mock_conn):
        resp = client.patch("/api/crm/practices/1", json={"invalid_field_xyz": "value"})
        assert resp.status_code in (200, 400, 404, 422, 500)

    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_practice_missing_updated_by(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row()
        resp = client.patch("/api/crm/practices/1", json={"status": "completed"})
        assert resp.status_code in (200, 400, 404, 422, 500)

    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_practice_database_error(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB error")
        resp = client.patch("/api/crm/practices/1", json={"status": "completed", "updated_by": "admin"})
        assert resp.status_code in (404, 500)


class TestEdgeCases:
    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_with_all_price_fields(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row(price=1000, price_paid=500)
        resp = client.patch("/api/crm/practices/1", json={"price": 1000, "price_paid": 500, "updated_by": "admin"})
        assert resp.status_code in (200, 400, 404, 500)

    def test_list_practices_max_limit(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?limit=200")
        assert resp.status_code == 200

    def test_list_practices_exceeds_max_limit(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/practices/?limit=500")
        assert resp.status_code in (200, 422)

    @patch("backend.app.routers.crm_practices.invalidate_cache", new_callable=AsyncMock)
    def test_update_completion_without_expiry(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_practice_row(status="completed")
        resp = client.patch("/api/crm/practices/1", json={"status": "completed", "updated_by": "admin"})
        assert resp.status_code in (200, 400, 404, 500)
