"""
Coverage tests for backend/app/routers/crm_practices.py

Endpoints covered:
- POST /api/crm/practices/            — create_practice
- GET  /api/crm/practices/            — list_practices
- GET  /api/crm/practices/active      — get_active_practices
- GET  /api/crm/practices/renewals/upcoming — get_upcoming_renewals
- GET  /api/crm/practices/types/catalog     — get_practice_types_catalog
- GET  /api/crm/practices/{id}        — get_practice
- PATCH /api/crm/practices/{id}       — update_practice
- DELETE /api/crm/practices/{id}      — delete_practice
- GET  /api/crm/practices/stats/overview    — get_practices_stats
- POST /api/crm/practices/{id}/regenerate-invoice
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_fixture(mock_current_user, mock_db_pool):
    """Set up FastAPI app with auth + DB dependency overrides."""
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.main_cloud import app

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def practice_row():
    """Minimal mock practice row as returned from asyncpg."""
    return {
        "id": 1,
        "uuid": str(uuid.uuid4()),
        "client_id": 42,
        "practice_type_id": 10,
        "status": "inquiry",
        "priority": "normal",
        "quoted_price": Decimal("15000000"),
        "actual_price": None,
        "payment_status": "unpaid",
        "assigned_to": "test@balizero.com",
        "start_date": None,
        "completion_date": None,
        "expiry_date": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "created_by": "test@balizero.com",
        "client_visible": True,
        "notes": None,
        "internal_notes": None,
        "documents": [],
        "missing_documents": [],
        "client_summary": None,
    }


# ---------------------------------------------------------------------------
# POST / — create_practice
# ---------------------------------------------------------------------------


class TestCreatePractice:
    @pytest.mark.asyncio
    async def test_create_practice_success(self, client_fixture, mock_db_conn, practice_row):
        """Creates a practice and returns 200 with PracticeResponse shape."""
        practice_type_row = {
            "id": 10,
            "base_price": Decimal("15000000"),
            "category": "kitas",
            "name": "KITAS Sponsor",
        }
        client_row = {"assigned_to": "test@balizero.com"}

        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[practice_type_row, client_row, practice_row]
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=client_fixture), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/crm/practices/",
                    json={
                        "client_id": 42,
                        "practice_type_code": "KITAS_SPONSOR",
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == 42
        assert data["status"] == "inquiry"

    @pytest.mark.asyncio
    async def test_create_practice_type_not_found(self, client_fixture, mock_db_conn):
        """Returns 404 when practice type code is not found."""
        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/practices/",
                json={"client_id": 42, "practice_type_code": "NONEXISTENT"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_practice_invalid_status(self, client_fixture):
        """Invalid status value → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/practices/",
                json={
                    "client_id": 42,
                    "practice_type_code": "KITAS",
                    "status": "invalid_status",
                },
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_practice_invalid_priority(self, client_fixture):
        """Invalid priority → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/practices/",
                json={
                    "client_id": 42,
                    "practice_type_code": "KITAS",
                    "priority": "extra_urgent",
                },
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_practice_negative_client_id(self, client_fixture):
        """client_id <= 0 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/practices/",
                json={"client_id": 0, "practice_type_code": "KITAS"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_practice_negative_price(self, client_fixture):
        """Negative quoted_price → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/practices/",
                json={"client_id": 1, "practice_type_code": "KITAS", "quoted_price": -1000},
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET / — list_practices
# ---------------------------------------------------------------------------


class TestListPractices:
    @pytest.mark.asyncio
    async def test_list_practices_success(self, client_fixture, mock_db_conn):
        """Returns a list of practices."""
        mock_db_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "client_name": "John",
                    "client_email": "j@t.com",
                    "client_phone": "+62",
                    "client_lead": "a@b.com",
                    "practice_type_name": "KITAS",
                    "practice_type_code": "KITAS_SPONSOR",
                    "practice_category": "kitas",
                    "status": "on_process",
                    "priority": "normal",
                    "uuid": str(uuid.uuid4()),
                    "client_id": 42,
                    "practice_type_id": 10,
                    "quoted_price": None,
                    "actual_price": None,
                    "payment_status": "unpaid",
                    "assigned_to": "test@balizero.com",
                    "start_date": None,
                    "completion_date": None,
                    "expiry_date": None,
                    "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                }
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/")

        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    async def test_list_practices_empty(self, client_fixture, mock_db_conn):
        """Returns empty list when no practices found."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_practices_with_filters(self, client_fixture, mock_db_conn):
        """Query params are accepted without errors."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/api/crm/practices/?status=on_process&priority=high&limit=10&offset=0"
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_practices_db_error(self, client_fixture, mock_db_conn):
        """DB error → 500."""
        mock_db_conn.fetch = AsyncMock(side_effect=Exception("DB down"))

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /active — get_active_practices
# ---------------------------------------------------------------------------


class TestGetActivePractices:
    @pytest.mark.asyncio
    async def test_active_practices_admin(self, client_fixture, mock_db_conn):
        """Admin user gets all active practices."""
        mock_db_conn.fetch = AsyncMock(
            return_value=[{"id": 1, "status": "on_process", "assigned_to": "a@b.com"}]
        )

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/active")

        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.asyncio
    async def test_active_practices_empty(self, client_fixture, mock_db_conn):
        """Returns empty list when no active practices."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/active")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_active_practices_db_error(self, client_fixture, mock_db_conn):
        """DB error → 500."""
        mock_db_conn.fetch = AsyncMock(side_effect=Exception("timeout"))

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/active")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /renewals/upcoming — get_upcoming_renewals
# ---------------------------------------------------------------------------


class TestUpcomingRenewals:
    @pytest.mark.asyncio
    async def test_upcoming_renewals_success(self, client_fixture, mock_db_conn):
        """Returns renewals within specified days."""
        mock_db_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "days_until_expiry": 30,
                    "expiry_date": "2026-05-10",
                    "assigned_to": "a@b.com",
                }
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/renewals/upcoming?days=60")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_upcoming_renewals_default_days(self, client_fixture, mock_db_conn):
        """Default 90 days is used when not specified."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/renewals/upcoming")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /types/catalog — get_practice_types_catalog
# ---------------------------------------------------------------------------


class TestPracticeTypesCatalog:
    @pytest.mark.asyncio
    async def test_catalog_success(self, client_fixture, mock_db_conn):
        """Returns categories and services."""
        mock_db_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "code": "KITAS_SPONSOR",
                    "name": "KITAS Sponsor",
                    "description": "KITAS with company sponsor",
                    "category": "kitas",
                    "base_price": Decimal("15000000"),
                    "typical_duration_days": 30,
                }
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/types/catalog")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "total_services" in data
        assert data["total_services"] == 1

    @pytest.mark.asyncio
    async def test_catalog_empty(self, client_fixture, mock_db_conn):
        """Returns empty categories list when no practice types."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/types/catalog")

        assert response.status_code == 200
        data = response.json()
        assert data["total_services"] == 0


# ---------------------------------------------------------------------------
# GET /{practice_id} — get_practice
# ---------------------------------------------------------------------------


class TestGetPractice:
    @pytest.mark.asyncio
    async def test_get_practice_found(self, client_fixture, mock_db_conn, practice_row):
        """Returns practice data for valid ID."""
        full_row = {
            **practice_row,
            "client_name": "John",
            "client_email": "j@t.com",
            "client_phone": "+62",
            "client_lead": "a@b.com",
            "practice_type_name": "KITAS",
            "practice_type_code": "KITAS_SPONSOR",
            "practice_category": "kitas",
            "required_documents": [],
        }
        mock_db_conn.fetchrow = AsyncMock(return_value=full_row)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    @pytest.mark.asyncio
    async def test_get_practice_not_found(self, client_fixture, mock_db_conn):
        """Returns 404 when practice doesn't exist."""
        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_practice_invalid_id(self, client_fixture):
        """Non-positive practice_id → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/practices/0")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /{practice_id} — update_practice
# ---------------------------------------------------------------------------


class TestUpdatePractice:
    @pytest.mark.asyncio
    async def test_update_practice_status(self, client_fixture, mock_db_conn, practice_row):
        """Admin can update practice status."""
        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "test@balizero.com",
            "assigned_to": "test@balizero.com",
        }
        updated_row = {**practice_row, "status": "waiting_documents"}
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, updated_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            with patch(
                "backend.app.routers.crm_practices.validate_transition", return_value=None
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=client_fixture), base_url="http://test"
                ) as ac:
                    response = await ac.patch(
                        "/api/crm/practices/1",
                        json={"status": "waiting_documents"},
                    )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_practice_not_found(self, client_fixture, mock_db_conn):
        """Returns 404 when practice doesn't exist."""
        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "test@balizero.com",
            "assigned_to": "test@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, None])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            with patch(
                "backend.app.routers.crm_practices.validate_transition", return_value=None
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=client_fixture), base_url="http://test"
                ) as ac:
                    response = await ac.patch(
                        "/api/crm/practices/999",
                        json={"status": "waiting_documents"},
                    )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_practice_no_fields(self, client_fixture, mock_db_conn):
        """Empty update body → 400."""
        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "test@balizero.com",
            "assigned_to": "test@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(return_value=old_row)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.patch("/api/crm/practices/1", json={})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_practice_non_admin_forbidden(self, mock_db_pool):
        """Non-admin user trying to update another's practice → 403."""
        from backend.app.dependencies import get_current_user, get_database_pool
        from backend.app.main_cloud import app

        client_user = {
            "id": "other-user-uuid",
            "email": "other@example.com",
            "role": "team",
            "full_name": "Other User",
        }
        app.dependency_overrides[get_current_user] = lambda: client_user
        app.dependency_overrides[get_database_pool] = lambda: mock_db_pool

        # Practice owned by a different user
        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "another@balizero.com",
            "assigned_to": "another@balizero.com",
        }
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=old_row)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.patch(
                "/api/crm/practices/1",
                json={"status": "waiting_documents"},
            )

        app.dependency_overrides.clear()
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /{practice_id} — delete_practice
# ---------------------------------------------------------------------------


class TestDeletePractice:
    @pytest.mark.asyncio
    async def test_delete_practice_success(self, client_fixture, mock_db_conn):
        """Admin can soft-delete (cancel) a practice."""
        ownership_row = {
            "created_by": "test@balizero.com",
            "assigned_to": "test@balizero.com",
        }
        deleted_row = {"id": 1}
        mock_db_conn.fetchrow = AsyncMock(side_effect=[ownership_row, deleted_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=client_fixture), base_url="http://test"
            ) as ac:
                response = await ac.delete("/api/crm/practices/1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_practice_not_found(self, client_fixture, mock_db_conn):
        """Returns 404 when practice does not exist."""
        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.delete("/api/crm/practices/999")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /stats/overview — get_practices_stats
# ---------------------------------------------------------------------------


class TestPracticesStats:
    @pytest.mark.asyncio
    async def test_stats_overview_success(self, client_fixture, mock_db_conn):
        """Returns stats dict with expected keys."""
        mock_db_conn.fetch = AsyncMock(
            side_effect=[
                [{"status": "on_process", "count": 5}, {"status": "completed", "count": 10}],
                [{"code": "KITAS_SPONSOR", "name": "KITAS", "count": 7}],
            ]
        )
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "total_revenue": Decimal("50000000"),
                    "paid_revenue": Decimal("30000000"),
                    "outstanding_revenue": Decimal("20000000"),
                },
                {"count": 5},
            ]
        )

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=client_fixture), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/crm/practices/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert "total_practices" in data
        assert "by_status" in data
        assert "by_type" in data
        assert "revenue" in data

    @pytest.mark.asyncio
    async def test_stats_overview_keys_present(self, client_fixture, mock_db_conn):
        """Stats overview returns expected keys regardless of data."""
        mock_db_conn.fetch = AsyncMock(return_value=[])
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"total_revenue": None, "paid_revenue": None, "outstanding_revenue": None},
                {"count": 0},
            ]
        )

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=client_fixture), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/crm/practices/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert "total_practices" in data
        assert "active_practices" in data
        assert "by_status" in data


# ---------------------------------------------------------------------------
# POST /{practice_id}/regenerate-invoice
# ---------------------------------------------------------------------------


class TestRegenerateInvoice:
    @pytest.mark.asyncio
    async def test_regenerate_invoice_success(self, client_fixture, mock_db_conn):
        """Triggers invoice regeneration for practice in sending_invoice status."""
        mock_db_conn.fetchrow = AsyncMock(return_value={"status": "sending_invoice"})

        mock_invoice_service = MagicMock()
        mock_invoice_service.regenerate_invoice = AsyncMock(
            return_value={
                "success": True,
                "invoice_number": "INV-2026-001",
                "drive_file_id": "file-abc",
                "drive_link": "https://drive.google.com/abc",
                "email_sent": True,
                "whatsapp_sent": False,
            }
        )

        with patch(
            "backend.app.routers.crm_practices.InvoiceAutomationService",
            return_value=mock_invoice_service,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=client_fixture), base_url="http://test"
            ) as ac:
                response = await ac.post("/api/crm/practices/1/regenerate-invoice")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["invoice_number"] == "INV-2026-001"

    @pytest.mark.asyncio
    async def test_regenerate_invoice_wrong_status(self, client_fixture, mock_db_conn):
        """Returns 400 when practice is not in sending_invoice status."""
        mock_db_conn.fetchrow = AsyncMock(return_value={"status": "on_process"})

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/crm/practices/1/regenerate-invoice")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_regenerate_invoice_not_found(self, client_fixture, mock_db_conn):
        """Returns 404 when practice does not exist."""
        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=client_fixture), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/crm/practices/999/regenerate-invoice")

        assert response.status_code == 404
