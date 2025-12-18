"""
Integration tests for CrossOracleSynthesisService
Tests cross-oracle synthesis and knowledge combination
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
class TestCrossOracleSynthesisIntegration:
    """Integration tests for CrossOracleSynthesisService"""

    @pytest.mark.asyncio
    async def test_cross_oracle_synthesis_init(self):
        """Test CrossOracleSynthesisService initialization"""
        with patch("services.search_service.SearchService") as mock_search_service:
            from services.cross_oracle_synthesis_service import CrossOracleSynthesisService

            service = CrossOracleSynthesisService(mock_search_service.return_value)
            assert service is not None
            assert service.search_service is not None

    @pytest.mark.asyncio
    async def test_synthesize_knowledge(self):
        """Test synthesizing knowledge from multiple sources"""
        with patch("services.search_service.SearchService") as mock_search_service:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "content": "Test content",
                            "metadata": {"source": "legal"},
                            "score": 0.9,
                        }
                    ]
                }
            )
            mock_search_service.return_value = mock_service

            with patch("services.cross_oracle_synthesis_service.ZantaraAIClient") as mock_ai:
                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(return_value="Synthesized answer")
                mock_ai.return_value = mock_ai_instance

                from services.cross_oracle_synthesis_service import CrossOracleSynthesisService

                service = CrossOracleSynthesisService(mock_service)
                result = await service.synthesize_knowledge(
                    query="test query",
                    legal_results=[],
                    business_results=[],
                    cultural_results=[],
                )

                assert result is not None
                assert hasattr(result, "answer") or isinstance(result, dict)
