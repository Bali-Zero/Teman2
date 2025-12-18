"""
Unit tests for CulturalRAGService
Tests cultural RAG service functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestCulturalRAGService:
    """Unit tests for CulturalRAGService"""

    @pytest.fixture
    def mock_cultural_insights_service(self):
        """Create mock cultural insights service"""
        mock = MagicMock()
        mock.query_insights = AsyncMock(return_value=[])
        return mock

    def test_cultural_rag_service_init(self, mock_cultural_insights_service):
        """Test CulturalRAGService initialization"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        assert service is not None
        assert service.cultural_insights == mock_cultural_insights_service

    @pytest.mark.asyncio
    async def test_get_cultural_context(self, mock_cultural_insights_service):
        """Test getting cultural context"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        mock_cultural_insights_service.query_insights = AsyncMock(
            return_value=[{"content": "test", "metadata": {"topic": "greeting"}}]
        )

        context = await service.get_cultural_context(
            {"query": "ciao", "intent": "greeting"}, limit=5
        )

        assert isinstance(context, list)

    @pytest.mark.asyncio
    async def test_get_cultural_context_empty(self, mock_cultural_insights_service):
        """Test getting cultural context with empty results"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        mock_cultural_insights_service.query_insights = AsyncMock(return_value=[])

        context = await service.get_cultural_context(
            {"query": "test", "intent": "unknown"}, limit=5
        )

        assert isinstance(context, list)

    def test_build_cultural_prompt_injection(self, mock_cultural_insights_service):
        """Test building cultural prompt injection"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        chunks = [{"content": "test content", "metadata": {"topic": "greeting"}}]

        injection = service.build_cultural_prompt_injection(chunks)

        assert isinstance(injection, str)
        assert len(injection) > 0

    def test_build_cultural_prompt_injection_empty(self, mock_cultural_insights_service):
        """Test building cultural prompt injection with empty chunks"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        chunks = []

        injection = service.build_cultural_prompt_injection(chunks)

        assert isinstance(injection, str)

    @pytest.mark.asyncio
    async def test_get_cultural_topics_coverage(self, mock_cultural_insights_service):
        """Test getting cultural topics coverage"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)
        coverage = await service.get_cultural_topics_coverage()

        assert isinstance(coverage, dict)
