"""Unit tests for backend/services/compliance/lkpm_service.py"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _AsyncCM:
    """Reusable async context manager returning a fixed connection mock."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg pool with context manager.

    pool.acquire() must return a synchronous async-CM object,
    NOT a coroutine, because asyncpg uses ``async with pool.acquire()``.
    """
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock()

    pool.acquire.return_value = _AsyncCM(conn)

    return pool, conn


@pytest.fixture
def service(mock_db_pool):
    """Create LKPMService with mocked deps."""
    pool, _ = mock_db_pool
    with patch(
        "backend.services.compliance.lkpm_service.LKPMValidator"
    ) as mock_val_cls, patch(
        "backend.services.compliance.lkpm_service.LKPMDataCollector"
    ) as mock_dc_cls:
        mock_validator = AsyncMock()
        mock_val_cls.return_value = mock_validator
        mock_collector = MagicMock()
        mock_dc_cls.return_value = mock_collector

        from backend.services.compliance.lkpm_service import LKPMService

        svc = LKPMService(pool)
        svc._mock_conn = mock_db_pool[1]  # stash for assertions
        return svc


# ---------------------------------------------------------------------------
# Helper to build a mock DB row
# ---------------------------------------------------------------------------


def _make_config_row(**overrides):
    """Build a dict that looks like a DB row for lkpm_client_config."""
    defaults = {
        "client_id": 1,
        "company_id": 100,
        "company_name": "PT Test PMA",
        "npwp": "12.345.678.9-012.000",
        "nib": "1234567890",
        "kbli_codes": ["62011"],
        "planned_equipment_domestic": 100_000_000,
        "planned_equipment_import": 50_000_000,
        "planned_building_domestic": 200_000_000,
        "planned_building_import": 0,
        "planned_vehicle_domestic": 30_000_000,
        "planned_vehicle_import": 0,
        "planned_land": 500_000_000,
        "planned_working_capital": 100_000_000,
        "planned_other": 0,
        "planned_tki": 10,
        "planned_tka": 2,
        "jurnal_api_key": None,
        "jurnal_company_id": None,
    }
    defaults.update(overrides)
    return defaults


def _make_draft_row(**overrides):
    """Build a dict mimicking an lkpm_reports DB row."""
    defaults = {
        "id": 1,
        "client_id": 1,
        "company_id": 100,
        "quarter": "Q1",
        "year": 2026,
        "status": "draft",
        "realized_equipment_domestic": 10_000_000,
        "realized_equipment_import": 5_000_000,
        "realized_building_domestic": 20_000_000,
        "realized_building_import": 0,
        "realized_vehicle_domestic": 3_000_000,
        "realized_vehicle_import": 0,
        "realized_land": 50_000_000,
        "realized_working_capital": 10_000_000,
        "realized_other": 0,
        "cumulative_equipment_domestic": 10_000_000,
        "cumulative_equipment_import": 5_000_000,
        "cumulative_building_domestic": 20_000_000,
        "cumulative_building_import": 0,
        "cumulative_vehicle_domestic": 3_000_000,
        "cumulative_vehicle_import": 0,
        "cumulative_land": 50_000_000,
        "cumulative_working_capital": 10_000_000,
        "cumulative_other": 0,
        "current_tki": 8,
        "current_tka": 1,
        "quarterly_revenue": 50_000_000,
        "annual_revenue": 200_000_000,
        "narrative_obstacles": "None",
        "narrative_plans": "Continue operations",
        "validation_alerts": None,
        "validation_status": "pending",
        "client_approved": False,
        "client_approved_at": None,
        "oss_submitted": False,
        "oss_submitted_at": None,
        "oss_receipt_number": None,
        "data_source": "manual",
        "has_ai_categorized_items": False,
        "ai_categorized_count": 0,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# get_client_config
# ---------------------------------------------------------------------------


class TestGetClientConfig:
    @pytest.mark.asyncio
    async def test_returns_config_when_found(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = _make_config_row()

        result = await service.get_client_config(1)

        assert result is not None
        assert result.client_id == 1
        assert result.company_name == "PT Test PMA"
        assert result.planned.equipment_domestic == 100_000_000

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        result = await service.get_client_config(999)
        assert result is None


# ---------------------------------------------------------------------------
# save_client_config
# ---------------------------------------------------------------------------


class TestSaveClientConfig:
    @pytest.mark.asyncio
    async def test_save_returns_id(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = {"id": 42}

        from backend.app.models.lkpm import InvestmentRealization, LKPMClientConfig

        config = LKPMClientConfig(
            client_id=1,
            company_name="PT New",
            planned=InvestmentRealization(equipment_domestic=100),
        )
        result = await service.save_client_config(config)
        assert result == 42


# ---------------------------------------------------------------------------
# get_deadlines
# ---------------------------------------------------------------------------


class TestGetDeadlines:
    def test_returns_deadlines(self, service):
        deadlines = service.get_deadlines(days_ahead=365)
        assert isinstance(deadlines, list)
        # Should have at least one deadline within 365 days
        assert len(deadlines) > 0

    def test_deadlines_sorted_by_days_remaining(self, service):
        deadlines = service.get_deadlines(days_ahead=365)
        if len(deadlines) >= 2:
            assert deadlines[0].days_remaining <= deadlines[1].days_remaining

    def test_overdue_detection(self, service):
        """Past deadlines should be marked overdue."""
        deadlines = service.get_deadlines(days_ahead=365)
        for d in deadlines:
            if d.days_remaining < 0:
                assert d.is_overdue is True

    def test_narrow_window(self, service):
        """Very narrow window might return fewer deadlines."""
        deadlines = service.get_deadlines(days_ahead=1)
        # Could be 0 or 1 depending on date
        assert isinstance(deadlines, list)


# ---------------------------------------------------------------------------
# generate_draft
# ---------------------------------------------------------------------------


class TestGenerateDraft:
    @pytest.mark.asyncio
    async def test_returns_existing_draft(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = _make_draft_row()

        result = await service.generate_draft(1, "Q1", 2026)
        assert result.id == 1
        assert result.quarter == "Q1"

    @pytest.mark.asyncio
    async def test_creates_new_draft_when_none_exists(self, service, mock_db_pool):
        _, conn = mock_db_pool
        # First fetchrow: _load_draft returns None
        # Second fetchrow: get_client_config returns config
        # Third fetchrow: _calculate_cumulative returns sums
        # Fourth fetchrow: _save_draft returns id
        conn.fetchrow.side_effect = [
            None,  # no existing draft
            _make_config_row(),  # client config
            None,  # _calculate_cumulative (will use fetch)
        ]
        conn.fetch.return_value = [
            {
                "eq_d": 0, "eq_i": 0, "bd_d": 0, "bd_i": 0,
                "vh_d": 0, "vh_i": 0, "land": 0, "wc": 0, "other": 0,
            }
        ]

        # _save_draft returns id
        save_call = AsyncMock(return_value={"id": 99})
        conn.fetchrow.side_effect = [
            None,
            _make_config_row(),
        ]
        conn.fetch.return_value = [
            {
                "eq_d": 0, "eq_i": 0, "bd_d": 0, "bd_i": 0,
                "vh_d": 0, "vh_i": 0, "land": 0, "wc": 0, "other": 0,
            }
        ]

        # Make the final fetchrow (in _save_draft) return an id
        call_count = 0
        original_fetchrow = conn.fetchrow

        async def smart_fetchrow(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # _load_draft
            elif call_count == 2:
                return _make_config_row()  # get_client_config
            else:
                return {"id": 99}  # _save_draft

        conn.fetchrow = smart_fetchrow
        result = await service.generate_draft(1, "Q1", 2026)
        assert result.id == 99

    @pytest.mark.asyncio
    async def test_raises_when_no_config(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        with pytest.raises(ValueError, match="No LKPM config"):
            await service.generate_draft(999, "Q1", 2026)


# ---------------------------------------------------------------------------
# approve_draft / mark_submitted / upload_receipt
# ---------------------------------------------------------------------------


class TestSubmissionTracking:
    @pytest.mark.asyncio
    async def test_approve_draft(self, service, mock_db_pool):
        _, conn = mock_db_pool
        result = await service.approve_draft(1)
        assert result["success"] is True
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_mark_submitted(self, service, mock_db_pool):
        _, conn = mock_db_pool
        result = await service.mark_submitted(1, "admin@test.com")
        assert result["success"] is True
        assert result["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_upload_receipt(self, service, mock_db_pool):
        _, conn = mock_db_pool
        result = await service.upload_receipt(1, "RCPT-001", "https://example.com/rcpt")
        assert result["success"] is True
        assert result["receipt_number"] == "RCPT-001"


# ---------------------------------------------------------------------------
# get_history / get_batch / get_alerts
# ---------------------------------------------------------------------------


class TestQueries:
    @pytest.mark.asyncio
    async def test_get_history(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetch.return_value = []

        result = await service.get_history(1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_batch(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetch.return_value = []

        result = await service.get_batch("Q1", 2026)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_alerts(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetch.return_value = []

        result = await service.get_alerts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_alerts_with_data(self, service, mock_db_pool):
        import json

        _, conn = mock_db_pool
        conn.fetch.return_value = [
            {
                "id": 1,
                "client_id": 1,
                "company_id": 100,
                "company_name": "PT Test",
                "quarter": "Q1",
                "year": 2026,
                "validation_alerts": json.dumps([
                    {"severity": "red", "message": "Missing data"},
                    {"severity": "yellow", "message": "Low value"},
                ]),
                "status": "draft",
            }
        ]

        result = await service.get_alerts()
        assert len(result) == 1
        assert result[0]["red_alerts"] == 1
        assert result[0]["total_alerts"] == 2


# ---------------------------------------------------------------------------
# validate_draft
# ---------------------------------------------------------------------------


class TestValidateDraft:
    @pytest.mark.asyncio
    async def test_validates_existing_draft(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = _make_draft_row()

        # Second call: get_client_config
        call_count = 0

        async def smart_fetchrow(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_draft_row()  # _load_draft_by_id
            elif call_count == 2:
                return _make_config_row()  # get_client_config

        conn.fetchrow = smart_fetchrow

        from backend.app.models.lkpm import LKPMValidationResult

        mock_result = LKPMValidationResult(is_valid=True, alerts=[])
        service.validator.validate = AsyncMock(return_value=mock_result)

        result = await service.validate_draft(1)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_nonexistent_draft_raises(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.validate_draft(999)


# ---------------------------------------------------------------------------
# get_ready_pack
# ---------------------------------------------------------------------------


class TestGetReadyPack:
    @pytest.mark.asyncio
    async def test_ready_pack_success(self, service, mock_db_pool):
        _, conn = mock_db_pool

        call_count = 0

        async def smart_fetchrow(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_draft_row()  # _load_draft_by_id
            elif call_count == 2:
                return _make_config_row()  # get_client_config

        conn.fetchrow = smart_fetchrow

        result = await service.get_ready_pack(1)
        assert result.draft_id == 1
        assert result.company_name == "PT Test PMA"
        assert isinstance(result.realization_percentage, float)

    @pytest.mark.asyncio
    async def test_ready_pack_nonexistent_raises(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.get_ready_pack(999)


# ---------------------------------------------------------------------------
# _row_to_draft (static)
# ---------------------------------------------------------------------------


class TestRowToDraft:
    def test_basic_conversion(self, service):
        row = _make_draft_row()
        from backend.services.compliance.lkpm_service import LKPMService

        draft = LKPMService._row_to_draft(row)
        assert draft.client_id == 1
        assert draft.quarter == "Q1"
        assert draft.realized.equipment_domestic == 10_000_000

    def test_with_validation_alerts(self, service):
        import json

        row = _make_draft_row(
            validation_status="invalid",
            validation_alerts=json.dumps([
                {"field": "tki", "severity": "red", "message": "Too low"}
            ]),
        )
        from backend.services.compliance.lkpm_service import LKPMService

        draft = LKPMService._row_to_draft(row)
        assert draft.validation is not None
        assert draft.validation.is_valid is False


# ---------------------------------------------------------------------------
# _row_to_batch_item (static)
# ---------------------------------------------------------------------------


class TestRowToBatchItem:
    def test_basic_conversion(self, service):
        row = {
            **_make_draft_row(),
            "company_name": "PT Batch",
            "lkpm_assigned_to": None,
            "validation_alerts": "[]",
        }
        from backend.services.compliance.lkpm_service import LKPMService

        item = LKPMService._row_to_batch_item(row)
        assert item.company_name == "PT Batch"
        assert item.realized_total > 0

    def test_days_to_deadline_computed(self, service):
        row = {
            **_make_draft_row(quarter="Q1", year=2026),
            "company_name": "PT DL",
            "lkpm_assigned_to": None,
            "validation_alerts": "[]",
        }
        from backend.services.compliance.lkpm_service import LKPMService

        item = LKPMService._row_to_batch_item(row)
        assert item.days_to_deadline is not None


# ---------------------------------------------------------------------------
# sync_jurnal
# ---------------------------------------------------------------------------


class TestSyncJurnal:
    @pytest.mark.asyncio
    async def test_no_config_raises(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        with pytest.raises(ValueError, match="No LKPM config"):
            await service.sync_jurnal(1, "Q1", 2026)

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self, service, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = _make_config_row(jurnal_api_key=None)

        with pytest.raises(ValueError, match="No Jurnal API key"):
            await service.sync_jurnal(1, "Q1", 2026)
