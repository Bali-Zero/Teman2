"""
Unit tests for TaxService
Target: ≥80% coverage
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.schemas.portal import TaxObligation, TaxSummary
from backend.services.portal.tax_service import TaxService


class AsyncContextManagerMock:
    """Helper class for mocking async context managers."""

    def __init__(self, return_value) -> None:
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_conn():
    """Mock database connection."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    # Mock transaction context manager
    conn.transaction = MagicMock(return_value=AsyncContextManagerMock(None))
    return conn


@pytest.fixture
def mock_db_pool(mock_conn):
    """Mock database pool with proper async context manager."""
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
    return pool


@pytest.fixture
def tax_service(mock_db_pool):
    """Create tax service instance."""
    return TaxService(mock_db_pool)


def make_tax_row(
    id: int = 1,
    client_id: int = 123,
    tax_type: str = "pph_21",
    name: str = "PPh 21 - January 2026",
    status: str = "pending",
    due_date: date = None,
    amount_due: float = 5000000.0,
):
    """Helper to create mock tax obligation row."""
    if due_date is None:
        due_date = datetime.now(tz=timezone.utc).date() + timedelta(days=30)
    return {
        "id": id,
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "client_id": client_id,
        "tax_type": tax_type,
        "name": name,
        "frequency": "monthly",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "due_date": due_date,
        "status": status,
        "amount_due": amount_due,
        "amount_paid": None,
        "created_at": datetime.now(tz=timezone.utc),
    }


class TestTaxService:
    """Tests for TaxService."""

    @pytest.mark.asyncio
    async def test_get_client_taxes_empty(self, tax_service, mock_conn):
        """Test getting taxes for client with no obligations."""
        mock_conn.fetch.return_value = []

        result = await tax_service.get_client_taxes(client_id=123, include_completed=False)

        assert result == []
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_taxes_with_data(self, tax_service, mock_conn):
        """Test getting taxes with multiple obligations."""
        mock_conn.fetch.return_value = [make_tax_row()]

        result = await tax_service.get_client_taxes(client_id=123, include_completed=False)

        assert len(result) == 1
        assert isinstance(result[0], TaxObligation)
        assert result[0].id == 1
        assert result[0].tax_type == "pph_21"
        assert result[0].status == "pending"

    @pytest.mark.asyncio
    async def test_get_client_taxes_include_completed(self, tax_service, mock_conn):
        """Test getting taxes including completed obligations."""
        mock_conn.fetch.return_value = []

        await tax_service.get_client_taxes(client_id=123, include_completed=True)

        # Verify query doesn't filter by status
        call_args = mock_conn.fetch.call_args[0][0]
        assert "status NOT IN" not in call_args

    @pytest.mark.asyncio
    async def test_get_client_taxes_excludes_completed_by_default(self, tax_service, mock_conn):
        """Test that completed obligations are excluded by default."""
        mock_conn.fetch.return_value = []

        await tax_service.get_client_taxes(client_id=123, include_completed=False)

        # Verify query filters out paid/filed status
        call_args = mock_conn.fetch.call_args[0][0]
        assert "status NOT IN" in call_args

    @pytest.mark.asyncio
    async def test_get_tax_summary_no_deadlines(self, tax_service, mock_conn):
        """Test summary when no pending deadlines."""
        mock_conn.fetchrow.return_value = {
            "total_due": 0,
            "next_deadline": None,
            "pending_count": 0,
            "overdue_count": 0,
        }

        result = await tax_service.get_tax_summary(client_id=123)

        assert isinstance(result, TaxSummary)
        assert result.total_due == 0
        assert result.next_deadline is None
        assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_get_tax_summary_upcoming_deadline(self, tax_service, mock_conn):
        """Test summary with upcoming deadline shows correct days."""
        next_deadline = datetime.now(tz=timezone.utc).date() + timedelta(days=10)
        mock_conn.fetchrow.return_value = {
            "total_due": 5000000,
            "next_deadline": next_deadline,
            "pending_count": 2,
            "overdue_count": 0,
        }

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.days_until_deadline == 10
        assert result.status == "attention"  # 10 days <= 14 days

    @pytest.mark.asyncio
    async def test_get_tax_summary_critical_deadline(self, tax_service, mock_conn):
        """Test summary with critical deadline (≤7 days)."""
        next_deadline = datetime.now(tz=timezone.utc).date() + timedelta(days=5)
        mock_conn.fetchrow.return_value = {
            "total_due": 5000000,
            "next_deadline": next_deadline,
            "pending_count": 2,
            "overdue_count": 0,
        }

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.status == "critical"  # 5 days <= 7 days

    @pytest.mark.asyncio
    async def test_get_tax_summary_overdue(self, tax_service, mock_conn):
        """Test summary with overdue obligations."""
        mock_conn.fetchrow.return_value = {
            "total_due": 5000000,
            "next_deadline": datetime.now(tz=timezone.utc).date() + timedelta(days=30),
            "pending_count": 2,
            "overdue_count": 1,
        }

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.status == "critical"  # overdue_count > 0

    @pytest.mark.asyncio
    async def test_get_tax_summary_ok_status(self, tax_service, mock_conn):
        """Test summary with ok status (>14 days, no overdue)."""
        next_deadline = datetime.now(tz=timezone.utc).date() + timedelta(days=30)
        mock_conn.fetchrow.return_value = {
            "total_due": 5000000,
            "next_deadline": next_deadline,
            "pending_count": 2,
            "overdue_count": 0,
        }

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.status == "ok"  # 30 days > 14 days

    @pytest.mark.asyncio
    async def test_create_obligation_creates_timeline_event(self, tax_service, mock_conn):
        """Test that creating obligation also creates timeline event."""
        mock_conn.fetchrow.return_value = make_tax_row(status="upcoming")

        result = await tax_service.create_obligation(
            client_id=123,
            tax_type="pph_21",
            name="PPh 21 - January 2026",
            frequency="monthly",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 2, 15),
            amount_due=5000000.0,
        )

        assert isinstance(result, TaxObligation)
        assert result.id == 1
        # Verify timeline event was created
        assert mock_conn.execute.call_count == 1
        # Check timeline event SQL contains 'timeline_events'
        execute_call = mock_conn.execute.call_args[0][0]
        assert "timeline_events" in execute_call

    @pytest.mark.asyncio
    async def test_create_obligation_without_amount(self, tax_service, mock_conn):
        """Test creating obligation without amount_due."""
        mock_conn.fetchrow.return_value = make_tax_row(amount_due=None)

        result = await tax_service.create_obligation(
            client_id=123,
            tax_type="pph_21",
            name="PPh 21 - January 2026",
            frequency="monthly",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 2, 15),
            amount_due=None,
        )

        assert isinstance(result, TaxObligation)

    @pytest.mark.asyncio
    async def test_update_status_to_paid(self, tax_service, mock_conn):
        """Test updating status to paid creates completion event."""
        mock_conn.fetchrow.return_value = make_tax_row(status="paid")

        result = await tax_service.update_status(
            obligation_id=1, new_status="paid", amount_paid=5000000.0
        )

        assert result.status == "paid"
        # Verify completion timeline event was created
        assert mock_conn.execute.call_count == 1
        execute_call = mock_conn.execute.call_args[0][0]
        assert "timeline_events" in execute_call

    @pytest.mark.asyncio
    async def test_update_status_to_filed(self, tax_service, mock_conn):
        """Test updating status to filed (no timeline event)."""
        mock_conn.fetchrow.return_value = make_tax_row(status="filed")

        result = await tax_service.update_status(obligation_id=1, new_status="filed")

        assert result.status == "filed"
        # No timeline event for filed status (only for paid)
        assert mock_conn.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, tax_service, mock_conn):
        """Test updating status when obligation not found."""
        mock_conn.fetchrow.return_value = None

        result = await tax_service.update_status(obligation_id=999, new_status="paid")

        assert result is None
