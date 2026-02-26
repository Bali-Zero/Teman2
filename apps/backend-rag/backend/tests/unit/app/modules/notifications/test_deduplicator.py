"""
Test AlertDeduplicator.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.modules.notifications.checker import AlertDeduplicator
from backend.app.modules.notifications.models import AlertType


class TestAlertDeduplicator:
    """Test alert deduplication logic."""

    @pytest.fixture
    def mock_db_pool(self) -> MagicMock:
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def deduplicator(self, mock_db_pool: MagicMock) -> AlertDeduplicator:
        return AlertDeduplicator(mock_db_pool)

    @pytest.mark.asyncio
    async def test_should_send_no_previous_alert(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """First alert for a client/type should always be sent."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchval.return_value = None  # No previous alert

        result = await deduplicator.should_send_alert(
            client_id=1,
            alert_type=AlertType.PASSPORT_WARNING,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_should_send_after_min_days(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """Alert should be sent if enough days have passed."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        # Last alert was 10 days ago (timezone-aware, as PostgreSQL returns)
        conn.fetchval.return_value = datetime.now(timezone.utc) - timedelta(days=10)

        result = await deduplicator.should_send_alert(
            client_id=1,
            alert_type=AlertType.PASSPORT_WARNING,
            min_days_between=7,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_send_too_recent(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """Alert should not be sent if too recent."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        # Last alert was 2 days ago
        conn.fetchval.return_value = datetime.now(timezone.utc) - timedelta(days=2)

        result = await deduplicator.should_send_alert(
            client_id=1,
            alert_type=AlertType.PASSPORT_WARNING,
            min_days_between=7,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_should_send_timezone_naive_last_alert(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """Handle timezone-naive datetime from database gracefully."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        # Timezone-naive (some DBs may return this)
        conn.fetchval.return_value = datetime.now() - timedelta(days=10)

        result = await deduplicator.should_send_alert(
            client_id=1,
            alert_type=AlertType.PASSPORT_WARNING,
            min_days_between=7,
        )

        assert result is True  # Should not raise TypeError

    @pytest.mark.asyncio
    async def test_mark_alert_sent(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """mark_alert_sent updates the database."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        await deduplicator.mark_alert_sent(alert_id=42)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "UPDATE notification_alerts" in call_args[0][0]
        assert call_args[0][1] == 42

    @pytest.mark.asyncio
    async def test_should_send_different_alert_types_independent(
        self, deduplicator: AlertDeduplicator, mock_db_pool: MagicMock
    ):
        """Different alert types are deduplicated independently."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        # Passport was sent recently, visa was never sent
        call_count = 0

        async def mock_fetchval(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Passport: sent 2 days ago
                return datetime.now(timezone.utc) - timedelta(days=2)
            else:
                # Visa: never sent
                return None

        conn.fetchval = mock_fetchval

        passport_result = await deduplicator.should_send_alert(
            client_id=1, alert_type=AlertType.PASSPORT_WARNING, min_days_between=7
        )
        visa_result = await deduplicator.should_send_alert(
            client_id=1, alert_type=AlertType.VISA_WARNING, min_days_between=7
        )

        assert passport_result is False
        assert visa_result is True
