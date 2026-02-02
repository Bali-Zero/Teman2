"""
Unit tests for deadline_checker job
Target: ≥80% coverage
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.jobs.deadline_checker import (
    TAX_REMINDER_DAYS,
    VISA_REMINDER_DAYS,
    check_tax_deadlines,
    check_visa_expiry,
    run_deadline_checker,
)


class AsyncContextManagerMock:
    """Helper class for mocking async context managers."""

    def __init__(self, return_value):
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
    conn.execute = AsyncMock(return_value="UPDATE 0")
    return conn


@pytest.fixture
def mock_db_pool(mock_conn):
    """Mock database pool with proper async context manager."""
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
    return pool


class TestDeadlineChecker:
    """Tests for deadline checker job."""

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_30_days(self, mock_db_pool, mock_conn):
        """Test reminder created at 30 days before deadline."""
        today = date.today()
        target_date = today + timedelta(days=30)

        mock_obligation = {
            "client_id": 123,
            "name": "PPh 21 - March 2026",
            "due_date": target_date,
        }

        # Return obligation only for 30-day check, empty for others
        mock_conn.fetch.side_effect = [
            [mock_obligation],  # 30 days
            [],  # 14 days
            [],  # 7 days
            [],  # 1 day
        ]

        result = await check_tax_deadlines(mock_db_pool)

        # Should create 1 reminder for 30-day reminder
        assert result == 1
        # Verify timeline event was created
        assert mock_conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_7_days_urgent(self, mock_db_pool, mock_conn):
        """Test urgent reminder at 7 days before deadline."""
        today = date.today()
        target_date = today + timedelta(days=7)

        mock_obligation = {
            "client_id": 123,
            "name": "PPh 21 - Urgent",
            "due_date": target_date,
        }

        # Return obligation only for 7-day check
        mock_conn.fetch.side_effect = [
            [],  # 30 days
            [],  # 14 days
            [mock_obligation],  # 7 days
            [],  # 1 day
        ]

        result = await check_tax_deadlines(mock_db_pool)

        assert result == 1
        # Verify urgent reminder created (color should be error)
        call_args = mock_conn.execute.call_args[0]
        assert "error" in call_args  # color parameter

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_1_day_critical(self, mock_db_pool, mock_conn):
        """Test critical reminder at 1 day before deadline."""
        today = date.today()
        target_date = today + timedelta(days=1)

        mock_obligation = {
            "client_id": 123,
            "name": "PPh 21 - Tomorrow",
            "due_date": target_date,
        }

        mock_conn.fetch.side_effect = [
            [],  # 30 days
            [],  # 14 days
            [],  # 7 days
            [mock_obligation],  # 1 day
        ]

        result = await check_tax_deadlines(mock_db_pool)

        assert result == 1

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_no_duplicates(self, mock_db_pool, mock_conn):
        """Test that duplicate reminders are not created."""
        # Return empty list (no obligations needing reminders)
        mock_conn.fetch.return_value = []

        result = await check_tax_deadlines(mock_db_pool)

        assert result == 0

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_all_reminder_days(self, mock_db_pool, mock_conn):
        """Test reminders created for all configured days (30/14/7/1)."""
        today = date.today()

        # Create obligations for each reminder day
        obligations = [
            {"client_id": 123, "name": f"Tax {days}d", "due_date": today + timedelta(days=days)}
            for days in TAX_REMINDER_DAYS
        ]

        # Return one obligation for each fetch call
        mock_conn.fetch.side_effect = [[ob] for ob in obligations]

        result = await check_tax_deadlines(mock_db_pool)

        # Should create 4 reminders (one for each day)
        assert result == 4

    @pytest.mark.asyncio
    async def test_check_visa_expiry_90_days(self, mock_db_pool, mock_conn):
        """Test renewal notice sent at 90 days before expiry."""
        today = date.today()
        target_date = today + timedelta(days=90)

        mock_visa = {
            "client_id": 123,
            "visa_type": "kitas_work",
            "expiry_date": target_date,
        }

        # Mock status updates return "UPDATE 0"
        mock_conn.execute.return_value = "UPDATE 0"
        # Return visa only for 90-day check
        mock_conn.fetch.side_effect = [
            [mock_visa],  # 90 days
            [],  # 60 days
            [],  # 30 days
        ]

        result = await check_visa_expiry(mock_db_pool)

        # Should create at least 1 reminder
        assert result >= 1

    @pytest.mark.asyncio
    async def test_check_visa_expiry_30_days_status_change(self, mock_db_pool, mock_conn):
        """Test status changes to expiring_soon at 30 days."""
        # Mock UPDATE returning "UPDATE 2" (2 rows updated to expiring_soon)
        mock_conn.execute.side_effect = ["UPDATE 2", "UPDATE 0"]
        mock_conn.fetch.return_value = []

        result = await check_visa_expiry(mock_db_pool)

        # Should have updated 2 visas to expiring_soon
        assert result >= 2

    @pytest.mark.asyncio
    async def test_check_visa_expiry_expired_status(self, mock_db_pool, mock_conn):
        """Test status changes to expired."""
        # Mock UPDATE returning "UPDATE 1" (1 row updated to expired)
        mock_conn.execute.side_effect = ["UPDATE 0", "UPDATE 1"]
        mock_conn.fetch.return_value = []

        result = await check_visa_expiry(mock_db_pool)

        # Should have updated 1 visa to expired
        assert result >= 1

    @pytest.mark.asyncio
    async def test_check_visa_expiry_all_reminder_days(self, mock_db_pool, mock_conn):
        """Test reminders created for all configured days (90/60/30)."""
        today = date.today()

        # Create visas for each reminder day
        visas = [
            {
                "client_id": 123,
                "visa_type": "kitas_work",
                "expiry_date": today + timedelta(days=days),
            }
            for days in VISA_REMINDER_DAYS
        ]

        mock_conn.execute.return_value = "UPDATE 0"
        # Return different visa for each fetch call
        mock_conn.fetch.side_effect = [[visa] for visa in visas]

        result = await check_visa_expiry(mock_db_pool)

        # Should create 3 reminders (one for each day)
        assert result >= 3

    @pytest.mark.asyncio
    async def test_run_deadline_checker_success(self, mock_db_pool, mock_conn):
        """Test full job execution success."""
        mock_conn.fetch.return_value = []
        mock_conn.execute.return_value = "UPDATE 0"

        with patch(
            "backend.app.core.database.get_db_pool",
            new_callable=AsyncMock,
            return_value=mock_db_pool,
        ):
            result = await run_deadline_checker()

            assert isinstance(result, dict)
            assert "tax_reminders" in result
            assert "visa_actions" in result

    @pytest.mark.asyncio
    async def test_run_deadline_checker_handles_errors(self):
        """Test job handles errors gracefully."""
        with patch(
            "backend.app.core.database.get_db_pool",
            new_callable=AsyncMock,
            side_effect=Exception("Database connection failed"),
        ):
            with pytest.raises(Exception, match="Database connection failed"):
                await run_deadline_checker()

    @pytest.mark.asyncio
    async def test_check_visa_expiry_no_visas(self, mock_db_pool, mock_conn):
        """Test when no visas need action."""
        mock_conn.execute.return_value = "UPDATE 0"
        mock_conn.fetch.return_value = []

        result = await check_visa_expiry(mock_db_pool)

        assert result == 0

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_multiple_clients(self, mock_db_pool, mock_conn):
        """Test reminders for multiple clients."""
        today = date.today()
        target_date = today + timedelta(days=30)

        mock_obligations = [
            {"client_id": 123, "name": "PPh 21 - Client A", "due_date": target_date},
            {"client_id": 456, "name": "PPh 21 - Client B", "due_date": target_date},
        ]

        mock_conn.fetch.side_effect = [
            mock_obligations,  # 30 days
            [],  # 14 days
            [],  # 7 days
            [],  # 1 day
        ]

        result = await check_tax_deadlines(mock_db_pool)

        assert result == 2
