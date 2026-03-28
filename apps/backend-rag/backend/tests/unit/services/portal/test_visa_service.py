"""
Unit tests for VisaService
Target: ≥80% coverage
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.schemas.portal import VisaRecord, VisaSummary
from backend.services.portal.visa_service import VisaService


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
def visa_service(mock_db_pool):
    """Create visa service instance."""
    return VisaService(mock_db_pool)


def make_visa_row(
    id: int = 1,
    client_id: int = 123,
    visa_type: str = "kitas_work",
    status: str = "active",
    expiry_date: date = None,
    issue_date: date = None,
):
    """Helper to create mock visa record row."""
    if expiry_date is None:
        expiry_date = date.today() + timedelta(days=365)
    if issue_date is None:
        issue_date = date.today() - timedelta(days=30)
    return {
        "id": id,
        "uuid": "550e8400-e29b-41d4-a716-446655440001",
        "client_id": client_id,
        "visa_type": visa_type,
        "status": status,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "visa_number": "C123456",
        "sponsor_name": "PT Example Indonesia",
        "sponsor_type": "company",
        "created_at": datetime.now(),
    }


class TestVisaService:
    """Tests for VisaService."""

    @pytest.mark.asyncio
    async def test_get_active_visa_none(self, visa_service, mock_conn):
        """Test when client has no active visa."""
        mock_conn.fetchrow.return_value = None

        result = await visa_service.get_active_visa(client_id=123)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_visa_exists(self, visa_service, mock_conn):
        """Test when client has active visa."""
        mock_conn.fetchrow.return_value = make_visa_row()

        result = await visa_service.get_active_visa(client_id=123)

        assert isinstance(result, VisaRecord)
        assert result.id == 1
        assert result.visa_type == "kitas_work"
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_active_visa_expiring_soon(self, visa_service, mock_conn):
        """Test getting active visa with expiring_soon status."""
        mock_conn.fetchrow.return_value = make_visa_row(status="expiring_soon")

        result = await visa_service.get_active_visa(client_id=123)

        assert result.status == "expiring_soon"

    @pytest.mark.asyncio
    async def test_get_visa_history_empty(self, visa_service, mock_conn):
        """Test getting visa history when empty."""
        mock_conn.fetch.return_value = []

        result = await visa_service.get_visa_history(client_id=123)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_visa_history(self, visa_service, mock_conn):
        """Test getting all visa records for a client."""
        mock_conn.fetch.return_value = [
            make_visa_row(id=1, visa_type="kitas_work", status="active"),
            make_visa_row(id=2, visa_type="tourist", status="expired"),
        ]

        result = await visa_service.get_visa_history(client_id=123)

        assert len(result) == 2
        assert isinstance(result[0], VisaRecord)
        assert result[0].visa_type == "kitas_work"
        assert result[1].visa_type == "tourist"

    @pytest.mark.asyncio
    async def test_get_visa_summary_no_visa(self, visa_service, mock_conn):
        """Test summary when no visa."""
        mock_conn.fetchrow.return_value = None

        result = await visa_service.get_visa_summary(client_id=123)

        assert isinstance(result, VisaSummary)
        assert result.has_active_visa is False
        assert result.status == "none"

    @pytest.mark.asyncio
    async def test_get_visa_summary_active(self, visa_service, mock_conn):
        """Test summary when visa active (>30 days)."""
        expiry_date = date.today() + timedelta(days=100)
        mock_conn.fetchrow.return_value = make_visa_row(expiry_date=expiry_date)

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.has_active_visa is True
        assert result.visa_type == "kitas_work"
        assert result.days_until_expiry == 100
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_visa_summary_expiring_soon(self, visa_service, mock_conn):
        """Test summary when visa expiring in <30 days."""
        expiry_date = date.today() + timedelta(days=20)
        mock_conn.fetchrow.return_value = make_visa_row(expiry_date=expiry_date)

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.status == "expiring_soon"
        assert result.days_until_expiry == 20

    @pytest.mark.asyncio
    async def test_get_visa_summary_expired(self, visa_service, mock_conn):
        """Test summary when visa expired."""
        expiry_date = date.today() - timedelta(days=10)
        mock_conn.fetchrow.return_value = make_visa_row(expiry_date=expiry_date)

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.status == "expired"
        assert result.days_until_expiry == -10

    @pytest.mark.asyncio
    async def test_get_visa_summary_no_expiry_date(self, visa_service, mock_conn):
        """Test summary when visa has no expiry date."""
        row = make_visa_row()
        row["expiry_date"] = None
        mock_conn.fetchrow.return_value = row

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.has_active_visa is True
        assert result.days_until_expiry is None
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_create_visa_record_creates_timeline_event(self, visa_service, mock_conn):
        """Test that creating visa record creates timeline event."""
        mock_conn.fetchrow.return_value = make_visa_row()

        result = await visa_service.create_visa_record(
            client_id=123,
            visa_type="kitas_work",
            status="active",
            issue_date=date(2025, 12, 31),
            expiry_date=date(2026, 12, 31),
            visa_number="C123456",
            sponsor_name="PT Example",
            sponsor_type="company",
        )

        assert isinstance(result, VisaRecord)
        assert result.id == 1
        # Verify timeline event was created
        assert mock_conn.execute.call_count == 1
        execute_call = mock_conn.execute.call_args[0][0]
        assert "timeline_events" in execute_call

    @pytest.mark.asyncio
    async def test_create_visa_record_minimal(self, visa_service, mock_conn):
        """Test creating visa record with minimal fields."""
        mock_conn.fetchrow.return_value = make_visa_row()

        result = await visa_service.create_visa_record(
            client_id=123,
            visa_type="tourist",
        )

        assert isinstance(result, VisaRecord)

    @pytest.mark.asyncio
    async def test_create_visa_record_with_practice(self, visa_service, mock_conn):
        """Test creating visa record linked to practice."""
        mock_conn.fetchrow.return_value = make_visa_row()

        result = await visa_service.create_visa_record(
            client_id=123,
            visa_type="kitas_work",
            practice_id=456,
        )

        assert isinstance(result, VisaRecord)

    @pytest.mark.asyncio
    async def test_update_visa_status(self, visa_service, mock_conn):
        """Test updating visa status."""
        mock_conn.fetchrow.return_value = make_visa_row(status="expiring_soon")

        result = await visa_service.update_visa_status(visa_id=1, new_status="expiring_soon")

        assert result.status == "expiring_soon"

    @pytest.mark.asyncio
    async def test_update_visa_status_to_expired(self, visa_service, mock_conn):
        """Test updating visa status to expired."""
        mock_conn.fetchrow.return_value = make_visa_row(status="expired")

        result = await visa_service.update_visa_status(visa_id=1, new_status="expired")

        assert result.status == "expired"

    @pytest.mark.asyncio
    async def test_update_visa_status_not_found(self, visa_service, mock_conn):
        """Test updating status when visa not found."""
        mock_conn.fetchrow.return_value = None

        result = await visa_service.update_visa_status(visa_id=999, new_status="expired")

        assert result is None
