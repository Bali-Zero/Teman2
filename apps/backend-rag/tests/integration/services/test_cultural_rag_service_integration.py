"""
Integration Tests for CulturalRAGService
Tests cultural context retrieval and injection
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCulturalRAGServiceIntegration:
    """Comprehensive integration tests for CulturalRAGService"""

    @pytest_asyncio.fixture
    async def mock_cultural_insights_service(self):
        """Create mock cultural insights service"""
        mock_service = MagicMock()
        mock_service.query_insights = AsyncMock(
            return_value=[
                {
                    "content": "Test cultural insight",
                    "metadata": {"topic": "greeting", "when_to_use": "first_contact"},
                    "score": 0.8,
                }
            ]
        )
        return mock_service

    @pytest_asyncio.fixture
    async def service(self, mock_cultural_insights_service):
        """Create CulturalRAGService instance"""
        from services.cultural_rag_service import CulturalRAGService

        return CulturalRAGService(cultural_insights_service=mock_cultural_insights_service)

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.cultural_insights is not None

    @pytest.mark.asyncio
    async def test_get_cultural_context_greeting(self, service):
        """Test getting cultural context for greeting"""
        context_params = {
            "query": "Hello",
            "intent": "greeting",
            "conversation_stage": "first_contact",
        }

        insights = await service.get_cultural_context(context_params, limit=2)

        assert insights is not None
        assert isinstance(insights, list)

    @pytest.mark.asyncio
    async def test_get_cultural_context_business(self, service):
        """Test getting cultural context for business query"""
        context_params = {
            "query": "How to set up PT PMA?",
            "intent": "business_simple",
            "conversation_stage": "ongoing",
        }

        insights = await service.get_cultural_context(context_params)

        assert insights is not None

    @pytest.mark.asyncio
    async def test_get_cultural_context_error_handling(self, service):
        """Test error handling in get_cultural_context"""
        service.cultural_insights.query_insights = AsyncMock(side_effect=Exception("Test error"))

        insights = await service.get_cultural_context({"query": "test"})

        assert insights == []

    def test_build_cultural_prompt_injection(self, service):
        """Test building cultural prompt injection"""
        cultural_chunks = [
            {
                "content": "Test cultural insight content",
                "metadata": {"topic": "greeting"},
                "score": 0.8,
            }
        ]

        injection = service.build_cultural_prompt_injection(cultural_chunks)

        assert injection is not None
        assert isinstance(injection, str)
        assert "cultural" in injection.lower() or "indonesian" in injection.lower()

    def test_build_cultural_prompt_injection_empty(self, service):
        """Test building prompt injection with empty chunks"""
        injection = service.build_cultural_prompt_injection([])

        assert injection == ""

    def test_build_cultural_prompt_injection_low_score(self, service):
        """Test building prompt injection with low score chunks"""
        cultural_chunks = [
            {
                "content": "Low relevance content",
                "metadata": {"topic": "test"},
                "score": 0.2,  # Below threshold
            }
        ]

        injection = service.build_cultural_prompt_injection(cultural_chunks)

        # Low score chunks should be filtered out
        assert "Low relevance" not in injection or injection == ""
