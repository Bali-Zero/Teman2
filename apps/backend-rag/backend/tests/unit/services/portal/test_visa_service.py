"""
Unit tests for VisaService
Target: ≥80% coverage
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.schemas.portal import VisaRecord, VisaSummary
from backend.services.portal.visa_service import VisaService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


@pytest.fixture
def visa_service(mock_db_pool):
    """Create visa service instance"""
    return VisaService(mock_db_pool)


class TestVisaService:
    """Tests for VisaService"""

    @pytest.mark.asyncio
    async def test_get_active_visa_none(self, visa_service, mock_db_pool):
        """Test when client has no active visa"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_active_visa(client_id=123)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_visa_exists(self, visa_service, mock_db_pool):
        """Test when client has active visa"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "active",
            "issue_date": date(2025, 12, 31),
            "expiry_date": date(2026, 12, 31),
            "visa_number": "C123456",
            "sponsor_name": "PT Example Indonesia",
            "sponsor_type": "company",
            "created_at": date(2025, 12, 31),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_active_visa(client_id=123)

        assert isinstance(result, VisaRecord)
        assert result.id == 1
        assert result.visa_type == "kitas_work"
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_visa_history(self, visa_service, mock_db_pool):
        """Test getting all visa records for a client"""
        mock_rows = [
            {
                "id": 1,
                "uuid": "550e8400-e29b-41d4-a716-446655440001",
                "client_id": 123,
                "visa_type": "kitas_work",
                "status": "active",
                "issue_date": date(2025, 12, 31),
                "expiry_date": date(2026, 12, 31),
                "visa_number": "C123456",
                "sponsor_name": "PT Example",
                "sponsor_type": "company",
                "created_at": date(2025, 12, 31),
            },
            {
                "id": 2,
                "uuid": "550e8400-e29b-41d4-a716-446655440002",
                "client_id": 123,
                "visa_type": "tourist",
                "status": "expired",
                "issue_date": date(2024, 1, 1),
                "expiry_date": date(2024, 2, 1),
                "visa_number": "T789012",
                "sponsor_name": None,
                "sponsor_type": None,
                "created_at": date(2024, 1, 1),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_visa_history(client_id=123)

        assert len(result) == 2
        assert isinstance(result[0], VisaRecord)
        assert result[0].visa_type == "kitas_work"
        assert result[1].visa_type == "tourist"

    @pytest.mark.asyncio
    async def test_get_visa_summary_no_visa(self, visa_service, mock_db_pool):
        """Test summary when no visa"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_visa_summary(client_id=123)

        assert isinstance(result, VisaSummary)
        assert result.has_active_visa is False
        assert result.status == "none"

    @pytest.mark.asyncio
    async def test_get_visa_summary_active(self, visa_service, mock_db_pool):
        """Test summary when visa active (>30 days)"""
        expiry_date = date.today() + timedelta(days=100)
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "active",
            "issue_date": date.today() - timedelta(days=100),
            "expiry_date": expiry_date,
            "visa_number": "C123456",
            "sponsor_name": "PT Example",
            "sponsor_type": "company",
            "created_at": date.today() - timedelta(days=100),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.has_active_visa is True
        assert result.visa_type == "kitas_work"
        assert result.days_until_expiry == 100
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_visa_summary_expiring_soon(self, visa_service, mock_db_pool):
        """Test summary when visa expiring in <30 days"""
        expiry_date = date.today() + timedelta(days=20)
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "active",
            "issue_date": date.today() - timedelta(days=100),
            "expiry_date": expiry_date,
            "visa_number": "C123456",
            "sponsor_name": "PT Example",
            "sponsor_type": "company",
            "created_at": date.today() - timedelta(days=100),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.status == "expiring_soon"
        assert result.days_until_expiry == 20

    @pytest.mark.asyncio
    async def test_get_visa_summary_expired(self, visa_service, mock_db_pool):
        """Test summary when visa expired"""
        expiry_date = date.today() - timedelta(days=10)
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "active",
            "issue_date": date.today() - timedelta(days=400),
            "expiry_date": expiry_date,
            "visa_number": "C123456",
            "sponsor_name": "PT Example",
            "sponsor_type": "company",
            "created_at": date.today() - timedelta(days=400),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.get_visa_summary(client_id=123)

        assert result.status == "expired"
        assert result.days_until_expiry == -10

    @pytest.mark.asyncio
    async def test_create_visa_record_creates_timeline_event(self, visa_service, mock_db_pool):
        """Test that creating visa record creates timeline event"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "active",
            "issue_date": date(2025, 12, 31),
            "expiry_date": date(2026, 12, 31),
            "visa_number": "C123456",
            "sponsor_name": "PT Example",
            "sponsor_type": "company",
            "practice_id": None,
            "created_at": date(2025, 12, 31),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.execute = AsyncMock()
        mock_transaction = AsyncMock()
        mock_conn.transaction.return_value = mock_transaction
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

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

    @pytest.mark.asyncio
    async def test_update_visa_status(self, visa_service, mock_db_pool):
        """Test updating visa status"""
        mock_row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440001",
            "client_id": 123,
            "visa_type": "kitas_work",
            "status": "expiring_soon",
            "issue_date": date(2025, 12, 31),
            "expiry_date": date(2026, 12, 31),
            "visa_number": "C123456",
            "sponsor_name": "PT Example",
            "sponsor_type": "company",
            "created_at": date(2025, 12, 31),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.update_visa_status(visa_id=1, new_status="expiring_soon")

        assert result.status == "expiring_soon"

    @pytest.mark.asyncio
    async def test_update_visa_status_not_found(self, visa_service, mock_db_pool):
        """Test updating status when visa not found"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await visa_service.update_visa_status(visa_id=999, new_status="expired")

        assert result is None
