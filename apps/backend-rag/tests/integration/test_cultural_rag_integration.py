"""
Integration tests for CulturalRAGService
Tests cultural context retrieval and prompt injection
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCulturalRAGIntegration:
    """Integration tests for CulturalRAGService"""

    @pytest.mark.asyncio
    async def test_cultural_rag_service_init(self):
        """Test CulturalRAGService initialization"""
        with patch("services.search_service.SearchService") as mock_search_service:
            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(mock_search_service.return_value)
            assert service is not None
            assert service.search_service is not None

    @pytest.mark.asyncio
    async def test_get_cultural_context(self):
        """Test getting cultural context for a query"""
        with patch("services.search_service.SearchService") as mock_search_service:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "content": "Indonesian greetings are important",
                            "metadata": {"topic": "indonesian_greetings"},
                            "score": 0.9,
                        }
                    ]
                }
            )
            mock_search_service.return_value = mock_service

            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(mock_service)
            result = await service.get_cultural_context(
                {"query": "ciao", "intent": "greeting"}, limit=1
            )

            assert len(result) > 0
            assert result[0]["metadata"]["topic"] == "indonesian_greetings"

    @pytest.mark.asyncio
    async def test_build_cultural_prompt_injection(self):
        """Test building cultural prompt injection"""
        with patch("services.search_service.SearchService"):
            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(MagicMock())
            chunks = [
                {
                    "content": "Indonesian greetings are important",
                    "metadata": {"topic": "indonesian_greetings"},
                }
            ]

            injection = service.build_cultural_prompt_injection(chunks)
            assert isinstance(injection, str)
            assert len(injection) > 0

    @pytest.mark.asyncio
    async def test_get_cultural_topics_coverage(self):
        """Test getting cultural topics coverage"""
        with patch("services.search_service.SearchService"):
            from services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService(MagicMock())
            coverage = await service.get_cultural_topics_coverage()

            assert isinstance(coverage, dict)
            assert "indonesian_greetings" in coverage
