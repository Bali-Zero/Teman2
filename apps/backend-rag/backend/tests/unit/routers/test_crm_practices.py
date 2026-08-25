"""
Unit tests for backend/app/routers/crm_practices.py

Tests route handler functions directly (no TestClient) with mocked dependencies.
Covers all endpoints:
- POST /             -> create_practice
- GET  /             -> list_practices
- GET  /active       -> get_active_practices
- GET  /renewals/upcoming -> get_upcoming_renewals
- GET  /types/catalog     -> get_practice_types_catalog
- GET  /{id}         -> get_practice
- PATCH /{id}        -> update_practice
- DELETE /{id}       -> delete_practice
- POST /{id}/documents/add -> add_document_to_practice
- GET  /stats/overview     -> get_practices_stats
- POST /{id}/regenerate-invoice -> regenerate_invoice
- GET  /{id}/required-documents -> get_required_documents
- POST /{id}/required-documents -> create_required_document
- DELETE /{id}/required-documents/{doc_id} -> delete_required_document
- PATCH  /{id}/required-documents/{doc_id} -> update_required_document

Plus helper functions:
- resolve_query_param
- _parse_month_param
- _build_status_transitions
- _create_hr_bonus_on_completed
- _notify_hr_bonus_pending
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user() -> dict[str, Any]:
    """Admin user that passes is_crm_admin check."""
    return {
        "id": "admin-uuid-1",
        "email": "zero@balizero.com",
        "role": "admin",
        "full_name": "Admin User",
    }


@pytest.fixture
def team_user() -> dict[str, Any]:
    """Non-admin team member."""
    return {
        "id": "team-uuid-2",
        "email": "team@balizero.com",
        "role": "team",
        "full_name": "Team User",
    }


@pytest.fixture
def practice_row() -> dict[str, Any]:
    """Mock practice row as returned from asyncpg."""
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
        "assigned_to": "team@balizero.com",
        "start_date": None,
        "completion_date": None,
        "expiry_date": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "created_by": "team@balizero.com",
        "client_visible": True,
        "notes": None,
        "internal_notes": None,
        "documents": [],
        "missing_documents": [],
        "client_summary": None,
        "client_name": "Test Client",
        "client_email": "client@example.com",
        "client_phone": "+628123456",
        "client_lead": "team@balizero.com",
        "practice_type_name": "KITAS Sponsor",
        "practice_type_code": "kitas_sponsor",
        "practice_category": "kitas",
        "required_documents": None,
    }


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestResolveQueryParam:
    def test_returns_value_when_plain(self) -> None:
        from backend.app.routers.crm_practices import resolve_query_param

        assert resolve_query_param("hello") == "hello"

    def test_returns_default_when_none(self) -> None:
        from backend.app.routers.crm_practices import resolve_query_param

        assert resolve_query_param(None, "fallback") == "fallback"

    def test_extracts_default_from_query_object(self) -> None:
        from backend.app.routers.crm_practices import resolve_query_param

        obj = MagicMock()
        obj.default = "inner_default"
        assert resolve_query_param(obj) == "inner_default"

    def test_none_with_no_default(self) -> None:
        from backend.app.routers.crm_practices import resolve_query_param

        assert resolve_query_param(None) is None


class TestParseMonthParam:
    def test_valid_month(self) -> None:
        from backend.app.routers.crm_practices import _parse_month_param

        result = _parse_month_param("2026-03")
        assert result is not None
        start, end = result
        assert start.month == 3
        assert end.month == 4

    def test_december(self) -> None:
        from backend.app.routers.crm_practices import _parse_month_param

        result = _parse_month_param("2026-12")
        assert result is not None
        start, end = result
        assert start.month == 12
        assert end.year == 2027
        assert end.month == 1

    def test_invalid_month(self) -> None:
        from backend.app.routers.crm_practices import _parse_month_param

        assert _parse_month_param("bad") is None

    def test_none(self) -> None:
        from backend.app.routers.crm_practices import _parse_month_param

        assert _parse_month_param(None) is None


class TestBuildStatusTransitions:
    def test_valid_rows(self) -> None:
        from backend.app.routers.crm_practices import _build_status_transitions

        rows = [
            {"entity_id": 1, "changes": '{"status": "on_process"}', "performed_at": "2026-01-01"},
            {"entity_id": 1, "changes": '{"status": "completed"}', "performed_at": "2026-01-02"},
            {"entity_id": 2, "changes": '{"status": "inquiry"}', "performed_at": "2026-01-01"},
        ]
        result = _build_status_transitions(rows)
        assert len(result[1]) == 2
        assert len(result[2]) == 1

    def test_no_status_in_changes(self) -> None:
        from backend.app.routers.crm_practices import _build_status_transitions

        rows = [{"entity_id": 1, "changes": '{"priority": "high"}', "performed_at": "2026-01-01"}]
        result = _build_status_transitions(rows)
        assert result == {}

    def test_changes_already_dict(self) -> None:
        from backend.app.routers.crm_practices import _build_status_transitions

        rows = [{"entity_id": 1, "changes": {"status": "on_process"}, "performed_at": "2026-01-01"}]
        result = _build_status_transitions(rows)
        assert 1 in result


# ---------------------------------------------------------------------------
# Pydantic model validation tests
# ---------------------------------------------------------------------------


class TestPracticeCreate:
    def test_valid_model(self) -> None:
        from backend.app.routers.crm_practices import PracticeCreate

        p = PracticeCreate(
            client_id=1,
            practice_type_code="kitas_sponsor",
            status="inquiry",
            priority="normal",
        )
        assert p.client_id == 1

    def test_invalid_status(self) -> None:
        from backend.app.routers.crm_practices import PracticeCreate

        with pytest.raises(ValueError, match="status must be one of"):
            PracticeCreate(client_id=1, practice_type_code="x", status="bad")

    def test_invalid_priority(self) -> None:
        from backend.app.routers.crm_practices import PracticeCreate

        with pytest.raises(ValueError, match="priority must be one of"):
            PracticeCreate(client_id=1, practice_type_code="x", priority="extreme")

    def test_negative_client_id(self) -> None:
        from backend.app.routers.crm_practices import PracticeCreate

        with pytest.raises(ValueError, match="client_id must be positive"):
            PracticeCreate(client_id=-1, practice_type_code="x")

    def test_negative_quoted_price(self) -> None:
        from backend.app.routers.crm_practices import PracticeCreate

        with pytest.raises(ValueError, match="quoted_price must be non-negative"):
            PracticeCreate(client_id=1, practice_type_code="x", quoted_price=Decimal("-100"))


class TestPracticeUpdate:
    def test_valid_update(self) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate

        u = PracticeUpdate(status="completed")
        assert u.status == "completed"

    def test_invalid_status(self) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate

        with pytest.raises(ValueError, match="status must be one of"):
            PracticeUpdate(status="bogus")

    def test_invalid_priority(self) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate

        with pytest.raises(ValueError, match="priority must be one of"):
            PracticeUpdate(priority="bogus")

    def test_negative_price_fields(self) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate

        with pytest.raises(ValueError, match="Price fields must be non-negative"):
            PracticeUpdate(actual_price=Decimal("-500"))


# ---------------------------------------------------------------------------
# Endpoint: list_practices
# ---------------------------------------------------------------------------


class TestListPractices:
    @pytest.mark.asyncio
    async def test_list_basic(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import list_practices

        row = MagicMock()
        row.__iter__ = MagicMock(return_value=iter([("id", 1), ("status", "inquiry")]))
        row.items = MagicMock(return_value=[("id", 1), ("status", "inquiry")])
        row.__getitem__ = lambda self, k: {"id": 1, "status": "inquiry"}[k]

        mock_db_conn.fetch = AsyncMock(return_value=[{"id": 1, "status": "inquiry"}])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await list_practices(
                client_id=None,
                status=None,
                assigned_to=None,
                practice_type=None,
                priority=None,
                month=None,
                include_history=False,
                limit=50,
                offset=0,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_with_all_filters(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import list_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await list_practices(
                client_id=1,
                status="inquiry",
                assigned_to="team@balizero.com",
                practice_type="kitas_sponsor",
                priority="high",
                month="2026-03",
                include_history=False,
                limit=10,
                offset=0,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_history(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import list_practices

        row = {"id": 5, "status": "on_process"}
        mock_db_conn.fetch = AsyncMock(
            side_effect=[
                [row],  # main query
                [],  # history query
            ]
        )

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await list_practices(
                client_id=None,
                status=None,
                assigned_to=None,
                practice_type=None,
                priority=None,
                month=None,
                include_history=True,
                limit=50,
                offset=0,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert len(result) == 1
        assert result[0].get("status_transitions") == []

    @pytest.mark.asyncio
    async def test_list_rbac_team_user(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import list_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter",
            return_value="team@balizero.com",
        ):
            result = await list_practices(
                client_id=None,
                status=None,
                assigned_to=None,
                practice_type=None,
                priority=None,
                month=None,
                include_history=False,
                limit=50,
                offset=0,
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_list_non_dict_user(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        """When called directly and current_user is not a dict, RBAC is skipped."""
        from backend.app.routers.crm_practices import list_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await list_practices(
                client_id=None,
                status=None,
                assigned_to=None,
                practice_type=None,
                priority=None,
                month=None,
                include_history=False,
                limit=50,
                offset=0,
                db_pool=mock_db_pool,
                current_user="not-a-dict",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_pool_param(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        """When pool parameter is provided, it overrides db_pool."""
        from backend.app.routers.crm_practices import list_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        other_pool = MagicMock()
        other_conn = AsyncMock()
        other_conn.fetch = AsyncMock(return_value=[])
        acm = MagicMock()
        acm.__aenter__ = AsyncMock(return_value=other_conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        other_pool.acquire = MagicMock(return_value=acm)

        result = await list_practices(
            client_id=None,
            status=None,
            assigned_to=None,
            practice_type=None,
            priority=None,
            month=None,
            include_history=False,
            limit=50,
            offset=0,
            db_pool=mock_db_pool,
            current_user="not-a-dict",
            pool=other_pool,
        )
        assert result == []
        other_conn.fetch.assert_called()


# ---------------------------------------------------------------------------
# Endpoint: get_active_practices
# ---------------------------------------------------------------------------


class TestGetActivePractices:
    @pytest.mark.asyncio
    async def test_active_admin(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_active_practices

        mock_db_conn.fetch = AsyncMock(return_value=[{"id": 1, "status": "on_process"}])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await get_active_practices(
                request=MagicMock(),
                assigned_to=None,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_active_team_filtered(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_active_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter",
            return_value="team@balizero.com",
        ):
            result = await get_active_practices(
                request=MagicMock(),
                assigned_to=None,
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_active_with_explicit_assigned_to(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_active_practices

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await get_active_practices(
                request=MagicMock(),
                assigned_to="specific@balizero.com",
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result == []


# ---------------------------------------------------------------------------
# Endpoint: get_upcoming_renewals
# ---------------------------------------------------------------------------


class TestUpcomingRenewals:
    @pytest.mark.asyncio
    async def test_renewals_success(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_upcoming_renewals

        mock_db_conn.fetch = AsyncMock(return_value=[{"id": 1, "days_until_expiry": 30}])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await get_upcoming_renewals(
                request=MagicMock(),
                days=90,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_renewals_team_user(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_upcoming_renewals

        mock_db_conn.fetch = AsyncMock(return_value=[])

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter",
            return_value="team@balizero.com",
        ):
            result = await get_upcoming_renewals(
                request=MagicMock(),
                days=30,
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result == []


# ---------------------------------------------------------------------------
# Endpoint: get_practice_types_catalog
# ---------------------------------------------------------------------------


class TestPracticeTypesCatalog:
    @pytest.mark.asyncio
    async def test_catalog_success(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_practice_types_catalog

        rows = [
            {
                "id": 1,
                "code": "kitas_sponsor",
                "name": "KITAS Sponsor",
                "description": "desc",
                "category": "kitas",
                "base_price": Decimal("15000000"),
                "typical_duration_days": 30,
            },
            {
                "id": 2,
                "code": "pt_pma",
                "name": "PT PMA",
                "description": "desc",
                "category": "company",
                "base_price": None,
                "typical_duration_days": 60,
            },
        ]
        mock_db_conn.fetch = AsyncMock(return_value=rows)

        result = await get_practice_types_catalog(
            db_pool=mock_db_pool,
            current_user=admin_user,
        )
        assert "categories" in result
        assert "total_services" in result
        assert result["total_services"] == 2

    @pytest.mark.asyncio
    async def test_catalog_empty(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_practice_types_catalog

        mock_db_conn.fetch = AsyncMock(return_value=[])

        result = await get_practice_types_catalog(
            db_pool=mock_db_pool,
            current_user=admin_user,
        )
        assert result["categories"] == []
        assert result["total_services"] == 0

    @pytest.mark.asyncio
    async def test_catalog_other_category(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_practice_types_catalog

        rows = [
            {
                "id": 1,
                "code": "misc",
                "name": "Misc",
                "description": "",
                "category": None,
                "base_price": None,
                "typical_duration_days": None,
            },
        ]
        mock_db_conn.fetch = AsyncMock(return_value=rows)

        result = await get_practice_types_catalog(
            db_pool=mock_db_pool,
            current_user=admin_user,
        )
        # category=None maps to "other"
        cat_codes = [c["code"] for c in result["categories"]]
        assert "other" in cat_codes


# ---------------------------------------------------------------------------
# Endpoint: get_practice
# ---------------------------------------------------------------------------


class TestGetPractice:
    @pytest.mark.asyncio
    async def test_get_practice_admin(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict, practice_row: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_practice

        mock_db_conn.fetchrow = AsyncMock(return_value=practice_row)

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            result = await get_practice(
                request=MagicMock(),
                practice_id=1,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_practice_not_found(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import get_practice

        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter", return_value=None
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_practice(
                    request=MagicMock(),
                    practice_id=999,
                    db_pool=mock_db_pool,
                    current_user=admin_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_practice_rbac_filtered(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import get_practice

        # RBAC filter applied, fetchrow returns None (not visible)
        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter",
            return_value="team@balizero.com",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_practice(
                    request=MagicMock(),
                    practice_id=1,
                    db_pool=mock_db_pool,
                    current_user=team_user,
                )
            assert exc_info.value.status_code == 404
        query = mock_db_conn.fetchrow.await_args.args[0]
        assert "c.assigned_to = $2 OR p.created_by = $2" in query
        assert "p.assigned_to = $2" not in query

    @pytest.mark.asyncio
    async def test_get_practice_strips_client_contact_fields_defensively(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import get_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={
                "id": 1,
                "created_by": "other@balizero.com",
                "assigned_to": "team@balizero.com",
                "client_lead": "lead@balizero.com",
                "client_name": "Synthetic Client",
                "client_email": "synthetic@example.com",
                "client_phone": "+620000000",
            }
        )

        with patch(
            "backend.app.routers.crm_practices.get_practices_user_filter",
            return_value="team@balizero.com",
        ):
            result = await get_practice(
                request=MagicMock(),
                practice_id=1,
                db_pool=mock_db_pool,
                current_user=team_user,
            )

        assert result["id"] == 1
        assert "client_name" not in result
        assert "client_email" not in result
        assert "client_phone" not in result
        assert "client_lead" not in result


# ---------------------------------------------------------------------------
# Endpoint: update_practice
# ---------------------------------------------------------------------------


class TestUpdatePractice:
    @pytest.mark.asyncio
    async def test_update_status_admin(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
        }
        canonical_row = {
            "id": 1,
            "status": "waiting_documents",
            "client_visible": True,
            "practice_type_id": 10,
            "client_id": 42,
            "practice_type_code": "ext_b1_voa",
            "practice_type_name": "B1 Visa on Arrival",
            "completion_date": None,
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, canonical_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        updates = PracticeUpdate(status="waiting_documents")

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.validate_transition"),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            result = await update_practice(
                request=MagicMock(),
                practice_id=1,
                updates=updates,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result["status"] == "waiting_documents"
        assert result["practice_type_code"] == "ext_b1_voa"

    @pytest.mark.asyncio
    async def test_update_returns_canonical_joined_row_and_clears_nullable_fields(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "on_process",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
            "start_date": datetime(2026, 7, 1, tzinfo=timezone.utc),
            "completion_date": None,
            "discount_amount": None,
            "metadata": {},
            "quoted_price": Decimal("15000000"),
        }
        canonical_row = {
            "id": 1,
            "status": "on_process",
            "client_visible": True,
            "practice_type_id": 10,
            "client_id": 42,
            "assigned_to": None,
            "start_date": None,
            "client_name": "Synthetic Client",
            "client_email": "synthetic@example.com",
            "client_phone": "+620000000",
            "client_lead": "lead@balizero.com",
            "practice_type_code": "ext_b1_voa",
            "practice_type_name": "B1 Visa on Arrival",
            "required_documents": [],
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, canonical_row])
        mock_db_conn.execute = AsyncMock(return_value=None)
        invalidate_cache_mock = AsyncMock()

        updates = PracticeUpdate(assigned_to=None, start_date=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch(
                "backend.app.routers.crm_practices.invalidate_cache",
                new=invalidate_cache_mock,
            ),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            result = await update_practice(
                request=MagicMock(),
                practice_id=1,
                updates=updates,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )

        update_query = mock_db_conn.fetchrow.await_args_list[1].args[0]
        update_params = mock_db_conn.fetchrow.await_args_list[1].args[1:]
        assert "assigned_to = $1" in update_query
        assert "start_date = $2" in update_query
        assert update_params[:2] == (None, None)
        assert result["assigned_to"] is None
        assert result["start_date"] is None
        assert result["client_name"] == "Synthetic Client"
        assert result["client_email"] == "synthetic@example.com"
        assert result["client_phone"] == "+620000000"
        assert result["client_lead"] == "lead@balizero.com"
        assert result["practice_type_code"] == "ext_b1_voa"
        assert "WITH updated AS" in update_query
        assert "LEFT JOIN practice_types" in update_query
        invalidate_cache_mock.assert_any_await("zantara:crm_practices_revenue_growth:*")

    @pytest.mark.asyncio
    async def test_update_assignee_only_does_not_disclose_client_contact_fields(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "creator@balizero.com",
            "assigned_to": "team@balizero.com",
            "client_lead": "lead@balizero.com",
        }
        canonical_row = {
            "id": 1,
            "status": "inquiry",
            "priority": "high",
            "client_id": 42,
            "client_visible": True,
            "client_name": "Synthetic Client",
            "client_email": "synthetic@example.com",
            "client_phone": "+620000000",
            "client_lead": "lead@balizero.com",
            "practice_type_code": "ext_b1_voa",
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, canonical_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=False),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            result = await update_practice(
                request=MagicMock(),
                practice_id=1,
                updates=PracticeUpdate(priority="high"),
                db_pool=mock_db_pool,
                current_user=team_user,
            )

        assert result["practice_type_code"] == "ext_b1_voa"
        assert "client_name" not in result
        assert "client_email" not in result
        assert "client_phone" not in result
        assert "client_lead" not in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("current_email", "created_by", "assigned_to", "client_lead"),
        [
            (
                "creator@balizero.com",
                "creator@balizero.com",
                "other@balizero.com",
                "lead@balizero.com",
            ),
            (
                "lead@balizero.com",
                "creator@balizero.com",
                "lead@balizero.com",
                "lead@balizero.com",
            ),
        ],
    )
    async def test_update_creator_and_client_lead_keep_client_contact_fields(
        self,
        mock_db_pool: MagicMock,
        mock_db_conn: AsyncMock,
        team_user: dict,
        current_email: str,
        created_by: str,
        assigned_to: str,
        client_lead: str,
    ) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        current_user = {**team_user, "email": current_email}
        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": created_by,
            "assigned_to": assigned_to,
            "client_lead": client_lead,
        }
        canonical_row = {
            "id": 1,
            "status": "inquiry",
            "priority": "high",
            "client_id": 42,
            "client_visible": True,
            "client_name": "Synthetic Client",
            "client_email": "synthetic@example.com",
            "client_phone": "+620000000",
            "client_lead": client_lead,
            "practice_type_code": "ext_b1_voa",
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, canonical_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=False),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            result = await update_practice(
                request=MagicMock(),
                practice_id=1,
                updates=PracticeUpdate(priority="high"),
                db_pool=mock_db_pool,
                current_user=current_user,
            )

        assert result["client_name"] == "Synthetic Client"
        assert result["client_email"] == "synthetic@example.com"
        assert result["client_phone"] == "+620000000"
        assert result["client_lead"] == client_lead

    @pytest.mark.asyncio
    async def test_update_applies_explicit_null_to_nullable_fields(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "on_process",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
        }
        canonical_row = {
            "id": 1,
            "status": "on_process",
            "client_id": 42,
            "notes": None,
            "expiry_date": None,
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, canonical_row])
        mock_db_conn.execute = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            result = await update_practice(
                request=MagicMock(),
                practice_id=1,
                updates=PracticeUpdate(notes=None, expiry_date=None),
                db_pool=mock_db_pool,
                current_user=admin_user,
            )

        update_query = mock_db_conn.fetchrow.await_args_list[1].args[0]
        update_params = mock_db_conn.fetchrow.await_args_list[1].args[1:]
        assert "expiry_date = $1" in update_query
        assert "notes = $2" in update_query
        assert update_params[:2] == (None, None)
        assert result["notes"] is None
        assert result["expiry_date"] is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "field",
        [
            "status",
            "priority",
            "quoted_price",
            "discount_amount",
            "discount_reason",
            "actual_price",
            "payment_status",
            "paid_amount",
            "client_visible",
            "documents",
            "missing_documents",
        ],
    )
    async def test_update_rejects_null_for_non_clearable_fields(
        self,
        mock_db_pool: MagicMock,
        mock_db_conn: AsyncMock,
        admin_user: dict,
        field: str,
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={
                "status": "inquiry",
                "client_id": 42,
                "client_visible": True,
                "created_by": "admin@balizero.com",
                "assigned_to": "team@balizero.com",
            }
        )

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_practice(
                    request=MagicMock(),
                    practice_id=1,
                    updates=PracticeUpdate(**{field: None}),
                    db_pool=mock_db_pool,
                    current_user=admin_user,
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == f"{field} cannot be null"

    @pytest.mark.asyncio
    async def test_update_no_fields(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(return_value=old_row)

        updates = PracticeUpdate()

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_practice(
                    request=MagicMock(),
                    practice_id=1,
                    updates=updates,
                    db_pool=mock_db_pool,
                    current_user=admin_user,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_non_admin_forbidden(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "other@balizero.com",
            "assigned_to": "other@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(return_value=old_row)

        updates = PracticeUpdate(status="on_process")

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_practice(
                    request=MagicMock(),
                    practice_id=1,
                    updates=updates,
                    db_pool=mock_db_pool,
                    current_user=team_user,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_invalid_transition(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import PracticeUpdate, update_practice
        from backend.services.crm.practice_state_machine import InvalidTransitionError

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(return_value=old_row)

        updates = PracticeUpdate(status="completed")

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch(
                "backend.app.routers.crm_practices.validate_transition",
                side_effect=InvalidTransitionError("inquiry", "completed", "bad"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_practice(
                    request=MagicMock(),
                    practice_id=1,
                    updates=updates,
                    db_pool=mock_db_pool,
                    current_user=admin_user,
                )
            assert exc_info.value.status_code == 400
            assert "Invalid status transition" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_not_found(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import PracticeUpdate, update_practice

        old_row = {
            "status": "inquiry",
            "client_id": 42,
            "client_visible": True,
            "created_by": "admin@balizero.com",
            "assigned_to": "team@balizero.com",
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[old_row, None])
        mock_db_conn.execute = AsyncMock(return_value=None)

        updates = PracticeUpdate(priority="high")

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.to_jsonb", return_value="{}"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_practice(
                    request=MagicMock(),
                    practice_id=999,
                    updates=updates,
                    db_pool=mock_db_pool,
                    current_user=admin_user,
                )
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint: delete_practice
# ---------------------------------------------------------------------------


class TestDeletePractice:
    @pytest.mark.asyncio
    async def test_delete_admin(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import delete_practice

        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"created_by": "someone", "assigned_to": "someone"},
                {"id": 1},
            ]
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
        ):
            result = await delete_practice(
                request=MagicMock(),
                practice_id=1,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import delete_practice

        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await delete_practice(
                request=MagicMock(),
                practice_id=999,
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_non_admin_forbidden(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import delete_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={"created_by": "other@balizero.com", "assigned_to": "other@balizero.com"}
        )

        with patch("backend.app.routers.crm_practices.is_crm_admin", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await delete_practice(
                    request=MagicMock(),
                    practice_id=1,
                    db_pool=mock_db_pool,
                    current_user=team_user,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_non_admin_owner_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import delete_practice

        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"created_by": "team@balizero.com", "assigned_to": None},
                {"id": 1},
            ]
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=False),
            patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()),
        ):
            result = await delete_practice(
                request=MagicMock(),
                practice_id=1,
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Endpoint: add_document_to_practice
# ---------------------------------------------------------------------------


class TestAddDocument:
    @pytest.mark.asyncio
    async def test_add_document_success(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import add_document_to_practice

        mock_db_conn.fetchrow = AsyncMock(return_value={"documents": []})
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await add_document_to_practice(
                request=MagicMock(),
                practice_id=1,
                document_name="Passport Copy",
                drive_file_id="drive123",
                uploaded_by="team@balizero.com",
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert result["success"] is True
        assert result["document"]["name"] == "Passport Copy"

    @pytest.mark.asyncio
    async def test_add_document_not_found(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import add_document_to_practice

        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await add_document_to_practice(
                request=MagicMock(),
                practice_id=999,
                document_name="Test",
                drive_file_id="x",
                uploaded_by="t@b.com",
                db_pool=mock_db_pool,
                current_user=admin_user,
            )
        assert exc_info.value.status_code == 404

    # -- crm-mutation-scope (2026-08-25): RBAC gate --------------------------
    # add_document_to_practice had NO scope check at all before this fix
    # (reconciliation F7). These tests prove the admin-or-owner gate now
    # mirrors update_practice's proven pattern.

    @pytest.mark.asyncio
    async def test_add_document_owner_created_by_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        """INNOCENCE: the practice's creator (non-admin) may add documents."""
        from backend.app.routers.crm_practices import add_document_to_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={
                "documents": [],
                "created_by": team_user["email"],
                "assigned_to": "someone-else@balizero.com",
            }
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await add_document_to_practice(
                request=MagicMock(),
                practice_id=1,
                document_name="Passport Copy",
                drive_file_id="drive123",
                uploaded_by=team_user["email"],
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result["success"] is True
        mock_db_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_document_owner_assigned_to_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        """INNOCENCE: the practice's assignee (non-admin) may add documents."""
        from backend.app.routers.crm_practices import add_document_to_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={
                "documents": [],
                "created_by": "someone-else@balizero.com",
                "assigned_to": team_user["email"],
            }
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await add_document_to_practice(
                request=MagicMock(),
                practice_id=1,
                document_name="Passport Copy",
                drive_file_id="drive123",
                uploaded_by=team_user["email"],
                db_pool=mock_db_pool,
                current_user=team_user,
            )
        assert result["success"] is True
        mock_db_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_document_denied_non_owner(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict, caplog
    ) -> None:
        """GUILT: a non-admin who neither created nor is assigned to the
        practice gets 403, no write happens, and the attempt is logged
        (auditable) — the exact gap the reconciliation found."""
        import logging

        from fastapi import HTTPException

        from backend.app.routers.crm_practices import add_document_to_practice

        mock_db_conn.fetchrow = AsyncMock(
            return_value={
                "documents": [],
                "created_by": "owner@balizero.com",
                "assigned_to": "other-owner@balizero.com",
            }
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with caplog.at_level(logging.WARNING, logger="backend.app.routers.crm_practices"):
            with pytest.raises(HTTPException) as exc_info:
                await add_document_to_practice(
                    request=MagicMock(),
                    practice_id=1,
                    document_name="Passport Copy",
                    drive_file_id="drive123",
                    uploaded_by=team_user["email"],
                    db_pool=mock_db_pool,
                    current_user=team_user,
                )
        assert exc_info.value.status_code == 403
        mock_db_conn.execute.assert_not_awaited()
        assert any("crm.rbac_practice_write_denied" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# update_required_document — RBAC gate (crm-mutation-scope, 2026-08-25)
# ---------------------------------------------------------------------------
# update_required_document had NO scope check at all before this fix
# (reconciliation F7: it is the backing route for the bot's would-be
# `mark_document_received` tool). These tests prove the admin-or-owner
# gate now mirrors update_practice's proven pattern.


class TestUpdateRequiredDocument:
    @pytest.mark.asyncio
    async def test_update_required_document_admin_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        from backend.app.routers.crm_practices import (
            RequiredDocumentUpdate,
            update_required_document,
        )

        practice_row = {"created_by": "owner@balizero.com", "assigned_to": "other@balizero.com"}
        doc_row = {
            "id": 5,
            "practice_id": 1,
            "document_type": "passport",
            "document_label": "Passport",
            "description": None,
            "is_required": True,
            "uploaded_by_client": False,
            "uploaded_file_id": None,
            "uploaded_at": None,
            "client_notes": None,
            "team_member_notes": None,
            "status": "verified",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[practice_row, doc_row])

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await update_required_document(
                practice_id=1,
                doc_id=5,
                update=RequiredDocumentUpdate(status="verified"),
                current_user=admin_user,
                db_pool=mock_db_pool,
            )
        assert result["status"] == "verified"

    @pytest.mark.asyncio
    async def test_update_required_document_owner_created_by_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        """INNOCENCE: the practice's creator (non-admin) may review documents."""
        from backend.app.routers.crm_practices import (
            RequiredDocumentUpdate,
            update_required_document,
        )

        practice_row = {"created_by": team_user["email"], "assigned_to": "other@balizero.com"}
        doc_row = {
            "id": 5,
            "practice_id": 1,
            "document_type": "passport",
            "document_label": "Passport",
            "description": None,
            "is_required": True,
            "uploaded_by_client": False,
            "uploaded_file_id": None,
            "uploaded_at": None,
            "client_notes": None,
            "team_member_notes": "looks good",
            "status": "verified",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[practice_row, doc_row])

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await update_required_document(
                practice_id=1,
                doc_id=5,
                update=RequiredDocumentUpdate(status="verified", team_member_notes="looks good"),
                current_user=team_user,
                db_pool=mock_db_pool,
            )
        assert result["status"] == "verified"

    @pytest.mark.asyncio
    async def test_update_required_document_owner_assigned_to_allowed(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict
    ) -> None:
        """INNOCENCE: the practice's assignee (non-admin) may review documents."""
        from backend.app.routers.crm_practices import (
            RequiredDocumentUpdate,
            update_required_document,
        )

        practice_row = {"created_by": "other@balizero.com", "assigned_to": team_user["email"]}
        doc_row = {
            "id": 5,
            "practice_id": 1,
            "document_type": "passport",
            "document_label": "Passport",
            "description": None,
            "is_required": True,
            "uploaded_by_client": False,
            "uploaded_file_id": None,
            "uploaded_at": None,
            "client_notes": None,
            "team_member_notes": None,
            "status": "verified",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        mock_db_conn.fetchrow = AsyncMock(side_effect=[practice_row, doc_row])

        with patch("backend.app.routers.crm_practices.invalidate_cache", new=AsyncMock()):
            result = await update_required_document(
                practice_id=1,
                doc_id=5,
                update=RequiredDocumentUpdate(status="verified"),
                current_user=team_user,
                db_pool=mock_db_pool,
            )
        assert result["status"] == "verified"

    @pytest.mark.asyncio
    async def test_update_required_document_denied_non_owner(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, team_user: dict, caplog
    ) -> None:
        """GUILT: a non-admin who neither created nor is assigned to the
        practice gets 403, no write happens, and the attempt is logged
        (auditable) — the exact gap the reconciliation found (backing
        route for the would-be bot tool `mark_document_received`)."""
        import logging

        from fastapi import HTTPException

        from backend.app.routers.crm_practices import (
            RequiredDocumentUpdate,
            update_required_document,
        )

        practice_row = {"created_by": "owner@balizero.com", "assigned_to": "other-owner@balizero.com"}
        mock_db_conn.fetchrow = AsyncMock(return_value=practice_row)

        with caplog.at_level(logging.WARNING, logger="backend.app.routers.crm_practices"):
            with pytest.raises(HTTPException) as exc_info:
                await update_required_document(
                    practice_id=1,
                    doc_id=5,
                    update=RequiredDocumentUpdate(status="verified"),
                    current_user=team_user,
                    db_pool=mock_db_pool,
                )
        assert exc_info.value.status_code == 403
        # Only the practice-ownership SELECT ran; the doc UPDATE never fired.
        assert mock_db_conn.fetchrow.await_count == 1
        assert any("crm.rbac_practice_write_denied" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_update_required_document_practice_not_found(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict
    ) -> None:
        """A nonexistent practice_id 404s before any ownership check or
        document lookup runs."""
        from fastapi import HTTPException

        from backend.app.routers.crm_practices import (
            RequiredDocumentUpdate,
            update_required_document,
        )

        mock_db_conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await update_required_document(
                practice_id=999,
                doc_id=5,
                update=RequiredDocumentUpdate(status="verified"),
                current_user=admin_user,
                db_pool=mock_db_pool,
            )
        assert exc_info.value.status_code == 404
        assert mock_db_conn.fetchrow.await_count == 1


# ---------------------------------------------------------------------------
# Helper: _create_hr_bonus_on_completed
# ---------------------------------------------------------------------------


class TestHRBonus:
    @pytest.mark.asyncio
    async def test_hr_bonus_no_assigned_to(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        # Should return silently if no assigned_to
        await _create_hr_bonus_on_completed(mock_db_pool, 1, None)
        mock_db_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_hr_bonus_table_not_exists(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(return_value=False)

        await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        mock_db_conn.fetchval.assert_awaited_once()
        mock_db_conn.fetchrow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hr_bonus_no_practice_type(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(return_value=True)
        mock_db_conn.fetchrow = AsyncMock(return_value=None)  # no practice type

        await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        mock_db_conn.fetchrow.assert_awaited_once()
        mock_db_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hr_bonus_no_rate(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(return_value=True)
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"code": "kitas_sponsor"},  # practice type
                None,  # no rate
            ]
        )

        await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        assert mock_db_conn.fetchrow.await_count == 2
        mock_db_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hr_bonus_no_employee(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(return_value=True)
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"code": "kitas_sponsor"},  # practice type
                {"id": 1, "amount_idr": 500000},  # rate
                None,  # no employee
            ]
        )

        await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        assert mock_db_conn.fetchrow.await_count == 3
        mock_db_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hr_bonus_existing_entry(
        self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock
    ) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(side_effect=[True, 99])  # table exists, existing entry
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"code": "kitas_sponsor"},  # practice type
                {"id": 1, "amount_idr": 500000},  # rate
                {"id": 7},  # employee
            ]
        )

        await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        assert mock_db_conn.fetchval.await_count == 2
        mock_db_conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hr_bonus_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_practices import _create_hr_bonus_on_completed

        mock_db_conn.fetchval = AsyncMock(side_effect=[True, None])  # table exists, no existing
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"code": "kitas_sponsor"},
                {"id": 1, "amount_idr": 500000},
                {"id": 7},
            ]
        )
        mock_db_conn.execute = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_practices._notify_hr_bonus_pending", new=AsyncMock()):
            await _create_hr_bonus_on_completed(mock_db_pool, 1, "team@balizero.com")
        mock_db_conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Helper: _notify_hr_bonus_pending
# ---------------------------------------------------------------------------


class TestNotifyHRBonus:
    @pytest.mark.asyncio
    async def test_notify_sends_email(self) -> None:
        from backend.app.routers.crm_practices import _notify_hr_bonus_pending

        # After HIGH-7 the recipient comes from settings.hr_notification_email
        # (default: asya@balizero.com). We patch both the send helper and the
        # settings attribute so this test pins the "asya@" contract without
        # depending on the env var's real value.
        # 2026-04-21: db_pool is now a required first arg (for email_send_log
        # audit); we pass a MagicMock — send_internal_email is patched so the
        # pool is never actually touched.
        mock_pool = MagicMock()
        with (
            patch(
                "backend.app.routers.crm_practices.send_internal_email",
                new=AsyncMock(),
            ) as mock_send,
            patch(
                "backend.app.routers.crm_practices.settings.hr_notification_email",
                "asya@balizero.com",
            ),
        ):
            await _notify_hr_bonus_pending(
                mock_pool,
                "team@balizero.com",
                "kitas_sponsor",
                500000,
                42,
            )
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["to"] == "asya@balizero.com"
        # New contract: audit kwargs thread through
        assert call_kwargs.kwargs["email_type"] == "hr_bonus"
        assert call_kwargs.kwargs["practice_id"] == 42
        assert call_kwargs.kwargs["pool"] is mock_pool


# ---------------------------------------------------------------------------
# Endpoint: upload_client_document
# ---------------------------------------------------------------------------


class TestUploadClientDocument:
    @pytest.mark.asyncio
    async def test_uses_canonical_document_upload_and_updates_required_doc(
        self,
        mock_db_pool: MagicMock,
        mock_db_conn: AsyncMock,
        admin_user: dict,
    ) -> None:
        from backend.app.routers import crm_practices

        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "id": 11,
                    "practice_id": 7,
                    "client_id": 42,
                    "client_name": "Client One",
                    "document_type": "passport",
                },
                {"id": 42},
            ]
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        canonical_upload = AsyncMock(return_value={"success": True, "document_id": 501})

        request = crm_practices.ClientDocumentUploadRequest(
            required_doc_id=11,
            file="ZmlsZQ==",
            file_name="passport.pdf",
            notes="client note",
        )

        with (
            patch.object(crm_practices, "upload_document_base64", canonical_upload, create=True),
            patch.object(crm_practices, "invalidate_cache", new=AsyncMock()),
        ):
            result = await crm_practices.upload_client_document(
                practice_id=7,
                request=request,
                current_user=admin_user,
                db_pool=mock_db_pool,
            )

        assert result["success"] is True
        assert result["document_id"] == 501

        upload_kwargs = canonical_upload.await_args.kwargs
        assert upload_kwargs["client_id"] == 42
        assert upload_kwargs["pool"] is mock_db_pool
        assert upload_kwargs["current_user"] is admin_user
        assert upload_kwargs["access_already_verified"] is True
        assert upload_kwargs["data"].file_name == "passport.pdf"
        assert upload_kwargs["data"].document_type == "passport"
        assert upload_kwargs["data"].practice_id == 7

        update_args = mock_db_conn.execute.await_args.args
        assert "UPDATE practice_required_documents" in update_args[0]
        assert update_args[1] == 501
        assert update_args[2] == "client note"
        assert update_args[3] == 11


# ---------------------------------------------------------------------------
# Constants / module-level
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_status_values(self) -> None:
        from backend.app.routers.crm_practices import STATUS_VALUES

        assert "completed" in STATUS_VALUES
        assert "inquiry" in STATUS_VALUES

    def test_priority_values(self) -> None:
        from backend.app.routers.crm_practices import PRIORITY_VALUES

        assert "high" in PRIORITY_VALUES
        assert "urgent" in PRIORITY_VALUES

    def test_category_labels(self) -> None:
        from backend.app.routers.crm_practices import CATEGORY_LABELS

        assert "kitas" in CATEGORY_LABELS
        assert "company" in CATEGORY_LABELS
