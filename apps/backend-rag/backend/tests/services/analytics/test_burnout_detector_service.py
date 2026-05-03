"""
Tests for BurnoutDetectorService
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.analytics.burnout_detector import BurnoutDetectorService


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def burnout_service(mock_pool):
    return BurnoutDetectorService(mock_pool)


@pytest.mark.asyncio
async def test_detect_burnout_signals_no_sessions(burnout_service, mock_pool):
    mock_pool.fetch.return_value = []
    results = await burnout_service.detect_burnout_signals()
    assert results == []


@pytest.mark.asyncio
async def test_detect_burnout_signals_with_warnings(burnout_service, mock_pool):
    # Mock some sessions that should trigger warnings
    # 3 sessions on weekends (DOW 0 or 6)
    sessions = [
        {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "session_start": datetime.now(tz=timezone.utc) - timedelta(days=7),
            "duration_minutes": 120,
            "conversations_count": 10,
            "activities_count": 5,
            "day_of_week": 0,  # Sunday
        },
        {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "session_start": datetime.now(tz=timezone.utc) - timedelta(days=6),
            "duration_minutes": 120,
            "conversations_count": 10,
            "activities_count": 5,
            "day_of_week": 6,  # Saturday
        },
        {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "session_start": datetime.now(tz=timezone.utc) - timedelta(days=1),
            "duration_minutes": 120,
            "conversations_count": 10,
            "activities_count": 5,
            "day_of_week": 0,  # Sunday
        },
    ]
    mock_pool.fetch.return_value = sessions

    results = await burnout_service.detect_burnout_signals()

    assert len(results) == 1
    assert results[0]["email"] == "test@example.com"
    assert "📅 Working 3 weekends" in results[0]["warning_signals"]
    assert results[0]["risk_level"] == "Low Risk"  # 15 points
