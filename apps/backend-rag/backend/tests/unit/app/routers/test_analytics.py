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
    return {"email": "zero@balizero.com", "name": "Zero"}


@pytest.fixture
def mock_non_founder_user():
    """Mock non-founder user"""
    return {"email": "test@example.com", "name": "Test"}


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
        result = verify_founder_access(user=mock_founder_user)
        assert result == mock_founder_user

    def test_verify_founder_access_denied(self, mock_non_founder_user):
        """Test verifying founder access - denied"""
        with pytest.raises(HTTPException) as exc_info:
            verify_founder_access(user=mock_non_founder_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_overview(self, mock_request, mock_founder_user):
        """Test getting overview stats"""
        from backend.app.routers.analytics import get_overview

        with patch(
            "backend.services.analytics.analytics_aggregator.AnalyticsAggregator"
        ) as mock_aggregator:
            mock_agg_instance = MagicMock()
            mock_agg_instance.get_overview_stats = AsyncMock(return_value=MagicMock())
            mock_aggregator.return_value = mock_agg_instance

            result = await get_overview(request=mock_request, user=mock_founder_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_rag_stats(self, mock_request, mock_founder_user):
        """Test getting RAG stats"""
        from backend.app.routers.analytics import get_rag_stats

        with patch(
            "backend.services.analytics.analytics_aggregator.AnalyticsAggregator"
        ) as mock_aggregator:
            mock_agg_instance = MagicMock()
            mock_agg_instance.get_rag_stats = AsyncMock(return_value=MagicMock())
            mock_aggregator.return_value = mock_agg_instance

            result = await get_rag_stats(request=mock_request, user=mock_founder_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_crm_stats(self, mock_request, mock_founder_user):
        """Test getting CRM stats"""
        from backend.app.routers.analytics import get_crm_stats

        with patch(
            "backend.services.analytics.analytics_aggregator.AnalyticsAggregator"
        ) as mock_aggregator:
            mock_agg_instance = MagicMock()
            mock_agg_instance.get_crm_stats = AsyncMock(return_value=MagicMock())
            mock_aggregator.return_value = mock_agg_instance

            result = await get_crm_stats(request=mock_request, user=mock_founder_user)
            assert result is not None
