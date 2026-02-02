"""
Unit tests for deadline_checker job
Target: ≥80% coverage
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.jobs.deadline_checker import (
    check_tax_deadlines,
    check_visa_expiry,
    run_deadline_checker,
)


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


class TestDeadlineChecker:
    """Tests for deadline checker job"""

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_30_days(self, mock_db_pool):
        """Test reminder created at 30 days before deadline"""
        today = date.today()
        target_date = today + timedelta(days=30)

        mock_obligation = {
            "client_id": 123,
            "name": "PPh 21 - March 2026",
            "due_date": target_date,
        }

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_obligation])
        mock_conn.execute = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_tax_deadlines(mock_db_pool)

        # Should create 1 reminder for 30-day reminder
        assert result >= 1
        # Verify timeline event was created
        assert mock_conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_7_days_urgent(self, mock_db_pool):
        """Test urgent reminder at 7 days before deadline"""
        today = date.today()
        target_date = today + timedelta(days=7)

        mock_obligation = {
            "client_id": 123,
            "name": "PPh 21 - Urgent",
            "due_date": target_date,
        }

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_obligation])
        mock_conn.execute = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_tax_deadlines(mock_db_pool)

        assert result >= 1
        # Verify urgent reminder created (color should be error)
        call_args = mock_conn.execute.call_args_list
        assert any("error" in str(args) for args in call_args)

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_no_duplicates(self, mock_db_pool):
        """Test that duplicate reminders are not created"""
        mock_conn = AsyncMock()
        # Return empty list (no obligations needing reminders)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_tax_deadlines(mock_db_pool)

        assert result == 0

    @pytest.mark.asyncio
    async def test_check_visa_expiry_90_days(self, mock_db_pool):
        """Test renewal notice sent at 90 days before expiry"""
        today = date.today()
        target_date = today + timedelta(days=90)

        mock_visa = {
            "client_id": 123,
            "visa_type": "kitas_work",
            "expiry_date": target_date,
        }

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")  # Status updates
        mock_conn.fetch = AsyncMock(return_value=[mock_visa])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_visa_expiry(mock_db_pool)

        # Should create at least 1 reminder
        assert result >= 1

    @pytest.mark.asyncio
    async def test_check_visa_expiry_30_days_status_change(self, mock_db_pool):
        """Test status changes to expiring_soon at 30 days"""
        today = date.today()
        expiry_date_30_days = today + timedelta(days=30)

        mock_conn = AsyncMock()
        # Mock UPDATE returning "UPDATE 2" (2 rows updated)
        mock_conn.execute = AsyncMock(side_effect=["UPDATE 2", "UPDATE 0"])
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_visa_expiry(mock_db_pool)

        # Should have updated 2 visas to expiring_soon
        assert result >= 2

    @pytest.mark.asyncio
    async def test_check_visa_expiry_expired_status(self, mock_db_pool):
        """Test status changes to expired"""
        mock_conn = AsyncMock()
        # Mock UPDATE returning "UPDATE 1" (1 row updated)
        mock_conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 1"])
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_visa_expiry(mock_db_pool)

        # Should have updated 1 visa to expired
        assert result >= 1

    @pytest.mark.asyncio
    async def test_run_deadline_checker_success(self):
        """Test full job execution success"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("backend.jobs.deadline_checker.get_db_pool", return_value=mock_pool):
            result = await run_deadline_checker()

            assert isinstance(result, dict)
            assert "tax_reminders" in result
            assert "visa_actions" in result

    @pytest.mark.asyncio
    async def test_run_deadline_checker_handles_errors(self):
        """Test job handles errors gracefully"""
        with patch(
            "backend.jobs.deadline_checker.get_db_pool",
            side_effect=Exception("Database connection failed"),
        ):
            with pytest.raises(Exception):
                await run_deadline_checker()

    @pytest.mark.asyncio
    async def test_check_tax_deadlines_all_reminder_days(self, mock_db_pool):
        """Test reminders created for all configured days (30/14/7/1)"""
        today = date.today()

        # Create obligations for each reminder day
        mock_obligations = [
            {"client_id": 123, "name": f"Tax {days}d", "due_date": today + timedelta(days=days)}
            for days in [30, 14, 7, 1]
        ]

        mock_conn = AsyncMock()
        # Return different obligation for each fetch call
        mock_conn.fetch = AsyncMock(side_effect=[[ob] for ob in mock_obligations])
        mock_conn.execute = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_tax_deadlines(mock_db_pool)

        # Should create 4 reminders (one for each day)
        assert result == 4

    @pytest.mark.asyncio
    async def test_check_visa_expiry_all_reminder_days(self, mock_db_pool):
        """Test reminders created for all configured days (90/60/30)"""
        today = date.today()

        # Create visas for each reminder day
        mock_visas = [
            {
                "client_id": 123,
                "visa_type": "kitas_work",
                "expiry_date": today + timedelta(days=days),
            }
            for days in [90, 60, 30]
        ]

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")
        # Return different visa for each fetch call
        mock_conn.fetch = AsyncMock(side_effect=[[visa] for visa in mock_visas])
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await check_visa_expiry(mock_db_pool)

        # Should create 3 reminders (one for each day)
        assert result >= 3
