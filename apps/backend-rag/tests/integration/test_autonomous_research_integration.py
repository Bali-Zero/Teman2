"""
Integration tests for AutonomousResearchService
Tests autonomous research and knowledge gathering
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAutonomousResearchIntegration:
    """Integration tests for AutonomousResearchService"""

    def test_autonomous_research_init(self):
        """Test AutonomousResearchService initialization"""
        with (
            patch("services.search_service.SearchService") as mock_search,
            patch("services.query_router.QueryRouter") as mock_query_router,
            patch("llm.zantara_ai_client.ZantaraAIClient") as mock_zantara,
        ):
            mock_search_instance = mock_search.return_value
            mock_query_router_instance = mock_query_router.return_value
            mock_zantara_instance = mock_zantara.return_value

            from services.autonomous_research_service import AutonomousResearchService

            service = AutonomousResearchService(
                search_service=mock_search_instance,
                query_router=mock_query_router_instance,
                zantara_ai_service=mock_zantara_instance,
            )
            assert service is not None
            assert hasattr(service, "search")

    def test_autonomous_research_service_constants(self):
        """Test that AutonomousResearchService has expected constants"""
        with (
            patch("services.search_service.SearchService") as mock_search,
            patch("services.query_router.QueryRouter") as mock_query_router,
            patch("llm.zantara_ai_client.ZantaraAIClient") as mock_zantara,
        ):
            from services.autonomous_research_service import AutonomousResearchService

            service = AutonomousResearchService(
                search_service=mock_search.return_value,
                query_router=mock_query_router.return_value,
                zantara_ai_service=mock_zantara.return_value,
            )
            # Test that service has expected attributes
            assert hasattr(service, "MAX_ITERATIONS")
            assert hasattr(service, "CONFIDENCE_THRESHOLD")
            assert hasattr(service, "MIN_RESULTS_THRESHOLD")
