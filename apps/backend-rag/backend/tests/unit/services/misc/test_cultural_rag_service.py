"""
Unit tests for CulturalRAGService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.cultural_rag_service import CulturalRAGService


@pytest.fixture
def mock_cultural_insights_service():
    """Mock cultural insights service"""
    service = MagicMock()
    service.query_insights = AsyncMock(return_value=[])
    return service


@pytest.fixture
def cultural_rag_service(mock_cultural_insights_service):
    """Create CulturalRAGService instance"""
    return CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)


class TestCulturalRAGService:
    """Tests for CulturalRAGService"""

    def test_init_with_cultural_insights(self, mock_cultural_insights_service):
        """Test initialization with cultural insights service"""
        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        assert service.cultural_insights == mock_cultural_insights_service

    def test_init_without_services(self):
        """Test initialization without services"""
        with patch('services.misc.cultural_insights_service.CulturalInsightsService', return_value=mock_cultural_insights_service):
            service = CulturalRAGService()
            assert service.cultural_insights is not None

    @pytest.mark.asyncio
    async def test_get_cultural_context(self, cultural_rag_service, mock_cultural_insights_service):
        """Test getting cultural context"""
        context_params = {
            "query": "test query",
            "intent": "greeting",
            "conversation_stage": "first_contact"
        }
        result = await cultural_rag_service.get_cultural_context(context_params)
        assert isinstance(result, list)
        mock_cultural_insights_service.query_insights.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cultural_context_business_intent(self, cultural_rag_service, mock_cultural_insights_service):
        """Test getting cultural context for business intent"""
        context_params = {
            "query": "test query",
            "intent": "business_simple",
            "conversation_stage": "ongoing"
        }
        result = await cultural_rag_service.get_cultural_context(context_params)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_cultural_context_custom_limit(self, cultural_rag_service, mock_cultural_insights_service):
        """Test getting cultural context with custom limit"""
        context_params = {
            "query": "test query",
            "intent": "casual",
            "conversation_stage": "ongoing"
        }
        result = await cultural_rag_service.get_cultural_context(context_params, limit=5)
        assert isinstance(result, list)

