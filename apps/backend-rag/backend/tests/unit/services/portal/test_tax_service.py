"""
Unit tests for TaxService
Target: ≥80% coverage
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.schemas.portal import TaxObligation, TaxSummary
from backend.services.portal.tax_service import TaxService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


@pytest.fixture
def tax_service(mock_db_pool):
    """Create tax service instance"""
    return TaxService(mock_db_pool)


class TestTaxService:
    """Tests for TaxService"""

    @pytest.mark.asyncio
    async def test_get_client_taxes_empty(self, tax_service, mock_db_pool):
        """Test getting taxes for client with no obligations"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_client_taxes(client_id=123, include_completed=False)

        assert result == []
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_taxes_with_data(self, tax_service, mock_db_pool):
        """Test getting taxes with multiple obligations"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "client_id": 123,
            "tax_type": "pph_21",
            "name": "PPh 21 - January 2026",
            "frequency": "monthly",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "due_date": date(2026, 2, 15),
            "status": "pending",
            "amount_due": 5000000.0,
            "amount_paid": None,
            "created_at": date(2026, 1, 15),
        }

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_client_taxes(client_id=123, include_completed=False)

        assert len(result) == 1
        assert isinstance(result[0], TaxObligation)
        assert result[0].id == 1
        assert result[0].tax_type == "pph_21"
        assert result[0].status == "pending"

    @pytest.mark.asyncio
    async def test_get_client_taxes_include_completed(self, tax_service, mock_db_pool):
        """Test getting taxes including completed obligations"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        await tax_service.get_client_taxes(client_id=123, include_completed=True)

        # Verify query doesn't filter by status
        call_args = mock_conn.fetch.call_args[0][0]
        assert "status NOT IN" not in call_args

    @pytest.mark.asyncio
    async def test_get_tax_summary_no_deadlines(self, tax_service, mock_db_pool):
        """Test summary when no pending deadlines"""
        mock_row = {
            "total_due": 0,
            "next_deadline": None,
            "pending_count": 0,
            "overdue_count": 0,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_tax_summary(client_id=123)

        assert isinstance(result, TaxSummary)
        assert result.total_due == 0
        assert result.next_deadline is None
        assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_get_tax_summary_upcoming_deadline(self, tax_service, mock_db_pool):
        """Test summary with upcoming deadline shows correct days"""
        next_deadline = date.today() + timedelta(days=10)
        mock_row = {
            "total_due": 5000000,
            "next_deadline": next_deadline,
            "pending_count": 2,
            "overdue_count": 0,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.days_until_deadline == 10
        assert result.status == "attention"  # 10 days <= 14 days

    @pytest.mark.asyncio
    async def test_get_tax_summary_critical_deadline(self, tax_service, mock_db_pool):
        """Test summary with critical deadline (≤7 days)"""
        next_deadline = date.today() + timedelta(days=5)
        mock_row = {
            "total_due": 5000000,
            "next_deadline": next_deadline,
            "pending_count": 2,
            "overdue_count": 0,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.status == "critical"  # 5 days <= 7 days

    @pytest.mark.asyncio
    async def test_get_tax_summary_overdue(self, tax_service, mock_db_pool):
        """Test summary with overdue obligations"""
        mock_row = {
            "total_due": 5000000,
            "next_deadline": date.today() + timedelta(days=30),
            "pending_count": 2,
            "overdue_count": 1,
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.get_tax_summary(client_id=123)

        assert result.status == "critical"  # overdue_count > 0

    @pytest.mark.asyncio
    async def test_create_obligation_creates_timeline_event(self, tax_service, mock_db_pool):
        """Test that creating obligation also creates timeline event"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "client_id": 123,
            "tax_type": "pph_21",
            "name": "PPh 21 - January 2026",
            "frequency": "monthly",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "due_date": date(2026, 2, 15),
            "status": "upcoming",
            "amount_due": 5000000.0,
            "amount_paid": None,
            "created_at": date(2026, 1, 15),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.execute = AsyncMock()
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

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

    @pytest.mark.asyncio
    async def test_update_status_to_paid(self, tax_service, mock_db_pool):
        """Test updating status to paid creates completion event"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "client_id": 123,
            "tax_type": "pph_21",
            "name": "PPh 21 - January 2026",
            "frequency": "monthly",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "due_date": date(2026, 2, 15),
            "status": "paid",
            "amount_due": 5000000.0,
            "amount_paid": 5000000.0,
            "created_at": date(2026, 1, 15),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.execute = AsyncMock()
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.update_status(
            obligation_id=1, new_status="paid", amount_paid=5000000.0
        )

        assert result.status == "paid"
        # Verify completion timeline event was created
        assert mock_conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, tax_service, mock_db_pool):
        """Test updating status when obligation not found"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tax_service.update_status(obligation_id=999, new_status="paid")

        assert result is None
