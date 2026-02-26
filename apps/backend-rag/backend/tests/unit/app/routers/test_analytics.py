"""
Unit tests for analytics router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.analytics import verify_founder_access


@pytest.fixture
def mock_founder_user():
    """Mock founder user"""
    return {"email": "zero@balizero.com", "name": "Zero", "role": "Founder"}


@pytest.fixture
def mock_non_founder_user():
    """Mock non-founder user"""
    return {"email": "test@example.com", "name": "Test", "role": "user"}


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = MagicMock()
    return request


class TestAnalyticsRouter:
    """Tests for analytics router"""

    def test_verify_founder_access_success(self, mock_founder_user):
        """Test verifying founder access - success"""
        result = verify_founder_access(current_user=mock_founder_user)
        assert result == mock_founder_user

    def test_verify_founder_access_denied(self, mock_non_founder_user):
        """Test verifying founder access - denied"""
        with pytest.raises(HTTPException) as exc_info:
            verify_founder_access(current_user=mock_non_founder_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_completion_rates(self, mock_request, mock_founder_user):
        """Test getting completion rates"""
        from backend.app.routers.analytics import get_completion_rates

        with patch(
            "backend.app.routers.analytics.calculate_completion_rate",
            new_callable=AsyncMock,
            return_value={"completion_rate": 0.85},
        ):
            result = await get_completion_rates(
                db_pool=MagicMock(),
                current_user=mock_founder_user,
            )
            assert result["completion_rate"] == 0.85

    @pytest.mark.asyncio
    async def test_get_response_times(self, mock_founder_user):
        """Test getting response times"""
        from backend.app.routers.analytics import get_response_times

        with patch(
            "backend.app.routers.analytics.calculate_response_times",
            new_callable=AsyncMock,
            return_value={"avg_inquiry_to_start": 2.5},
        ):
            result = await get_response_times(
                db_pool=MagicMock(),
                current_user=mock_founder_user,
            )
            assert result["avg_inquiry_to_start"] == 2.5

    @pytest.mark.asyncio
    async def test_get_sla_compliance(self, mock_founder_user):
        """Test getting SLA compliance"""
        from backend.app.routers.analytics import get_sla_compliance

        with patch(
            "backend.app.routers.analytics.calculate_sla_compliance",
            new_callable=AsyncMock,
            return_value={"sla_compliance_rate": 0.92},
        ):
            result = await get_sla_compliance(
                db_pool=MagicMock(),
                current_user=mock_founder_user,
            )
            assert result["sla_compliance_rate"] == 0.92
