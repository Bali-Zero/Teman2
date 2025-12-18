"""
Unit tests for SpecializedServiceRouter
Tests routing functionality for specialized services
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


class TestSpecializedServiceRouter:
    """Unit tests for SpecializedServiceRouter"""

    @pytest.fixture
    def mock_search_service(self):
        """Create mock search service"""
        mock = MagicMock()
        mock.search = AsyncMock(return_value={"results": []})
        return mock

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service"""
        mock = MagicMock()
        mock.get_user_memory = AsyncMock(return_value={})
        return mock

    def test_router_init(self, mock_search_service, mock_memory_service):
        """Test router initialization"""
        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        router = SpecializedServiceRouter()
        assert router is not None

    def test_detect_autonomous_research(self):
        """Test detect_autonomous_research method"""
        from unittest.mock import MagicMock

        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        mock_autonomous = MagicMock()
        router = SpecializedServiceRouter(autonomous_research_service=mock_autonomous)

        result = router.detect_autonomous_research(
            "crypto visa requirements", category="business_complex"
        )
        assert isinstance(result, bool)

    def test_detect_cross_oracle(self):
        """Test detect_cross_oracle method"""
        from unittest.mock import MagicMock

        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        mock_cross_oracle = MagicMock()
        router = SpecializedServiceRouter(cross_oracle_synthesis_service=mock_cross_oracle)

        result = router.detect_cross_oracle("open restaurant in bali", category="business_complex")
        assert isinstance(result, bool)

    def test_detect_client_journey(self):
        """Test detect_client_journey method"""
        from unittest.mock import MagicMock

        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        mock_journey = MagicMock()
        router = SpecializedServiceRouter(client_journey_orchestrator=mock_journey)

        result = router.detect_client_journey(
            "start process for pt pma", _category="business_complex"
        )
        assert isinstance(result, bool)

    def test_router_init_with_services(self):
        """Test router initialization with services"""
        from unittest.mock import MagicMock

        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        mock_autonomous = MagicMock()
        mock_cross_oracle = MagicMock()
        mock_journey = MagicMock()

        router = SpecializedServiceRouter(
            autonomous_research_service=mock_autonomous,
            cross_oracle_synthesis_service=mock_cross_oracle,
            client_journey_orchestrator=mock_journey,
        )

        assert router is not None
        assert router.autonomous_research == mock_autonomous
        assert router.cross_oracle == mock_cross_oracle
        assert router.client_journey == mock_journey
