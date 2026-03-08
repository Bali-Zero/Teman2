"""
Unit tests for QueryRouterIntegration service

Tests query routing and collection selection logic in isolation.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).resolve().parents[2]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Aggressively mock problematic modules before any backend imports
def mock_problematic_modules():
    # Mock PIL only (numpy 1.26.4 is installed, use real numpy)
    sys.modules["numpy._typing"] = MagicMock()
    sys.modules["numpy._typing._char_codes"] = MagicMock()

    # Mock scipy
    scipy_mock = types.ModuleType("scipy")
    sys.modules["scipy"] = scipy_mock
    sys.modules["scipy.sparse"] = MagicMock()

    # Mock sklearn
    sklearn_mock = types.ModuleType("sklearn")
    sys.modules["sklearn"] = sklearn_mock
    sys.modules["sklearn.metrics"] = MagicMock()
    sys.modules["sklearn.metrics.pairwise"] = MagicMock()

    for m in ["PIL", "PIL.Image", "PIL.ImageMode"]:
        mock = types.ModuleType(m)
        if m == "PIL":
            mock.__version__ = "10.0.0"
            mock.Image = types.ModuleType("PIL.Image")
            mock.Image.Image = MagicMock
        sys.modules[m] = mock

    # Mock backend services to avoid cascade
    for m in [
        "backend.services.oracle",
        "backend.services.search",
        "backend.services.rag",
        "backend.services.rag.agentic",
        "backend.services.ingestion",
        "backend.services.analytics",
        "backend.services.llm_clients",
        "backend.services.pricing",
        "qdrant_client",
    ]:
        sys.modules[m] = MagicMock()

    # Special handling for monitoring to allow submodule imports
    monitoring_mock = types.ModuleType("backend.services.monitoring")
    monitoring_mock.__path__ = []
    sys.modules["backend.services.monitoring"] = monitoring_mock

    # Special handling for misc to allow submodule imports
    misc_mock = types.ModuleType("backend.services.misc")
    misc_mock.__path__ = []
    sys.modules["backend.services.misc"] = misc_mock
    sys.modules["backend.services.misc.clarification_service"] = MagicMock()
    sys.modules["backend.services.misc.context_suggestion_service"] = MagicMock()
    sys.modules["backend.services.misc.followup_service"] = MagicMock()

    # Special handling for routing to allow submodule imports
    routing_mock = types.ModuleType("backend.services.routing")
    routing_mock.__path__ = []
    sys.modules["backend.services.routing"] = routing_mock
    sys.modules["backend.services.routing.intelligent_router"] = MagicMock()


mock_problematic_modules()

from backend.services.routing.query_router_integration import QueryRouterIntegration  # noqa: E402


class TestQueryRouterIntegration:
    """Test QueryRouterIntegration service"""

    @pytest.fixture
    def mock_query_router(self):
        """Mock QueryRouter"""
        router = Mock()
        router.route.return_value = "visa_oracle"
        router.route_with_confidence.return_value = ("visa_oracle", 0.85, ["visa_oracle"])
        return router

    @pytest.fixture
    def integration(self, mock_query_router):
        """Create QueryRouterIntegration instance"""
        return QueryRouterIntegration(query_router=mock_query_router)

    def test_initialization(self, integration):
        """Test QueryRouterIntegration initialization"""
        assert integration is not None
        assert integration.router is not None
        assert len(integration.pricing_keywords) > 0

    def test_is_pricing_query_english(self, integration):
        """Test pricing query detection (English)"""
        assert integration.is_pricing_query("What is the price?") is True
        assert integration.is_pricing_query("How much does it cost?") is True
        assert integration.is_pricing_query("Tell me about visas") is False

    def test_is_pricing_query_indonesian(self, integration):
        """Test pricing query detection (Indonesian)"""
        assert integration.is_pricing_query("Berapa harganya?") is True
        assert integration.is_pricing_query("Apa biayanya?") is True

    def test_is_pricing_query_italian(self, integration):
        """Test pricing query detection (Italian)"""
        assert integration.is_pricing_query("Quanto costa?") is True
        assert integration.is_pricing_query("Qual è il prezzo?") is True

    def test_route_query_override(self, integration):
        """Test routing with collection override"""
        result = integration.route_query(
            query="test query", collection_override="tax_genius", enable_fallbacks=False
        )

        assert result["collection_name"] == "tax_genius"
        assert result["collections"] == ["tax_genius"]
        assert result["confidence"] == 1.0
        assert result["is_pricing"] is False

    def test_route_query_pricing(self, integration):
        """Test routing for pricing queries"""
        result = integration.route_query(
            query="What is the price?", collection_override=None, enable_fallbacks=False
        )

        assert result["collection_name"] == "bali_zero_pricing_hybrid"
        assert result["is_pricing"] is True
        assert result["confidence"] == 0.95  # Pricing queries return 0.95 confidence

    def test_route_query_normal(self, integration, mock_query_router):
        """Test routing for normal queries"""
        result = integration.route_query(
            query="Tell me about visas", collection_override=None, enable_fallbacks=False
        )

        assert result["collection_name"] == "visa_oracle"
        assert result["is_pricing"] is False
        mock_query_router.route.assert_called_once_with("Tell me about visas")

    def test_route_query_with_fallbacks(self, integration, mock_query_router):
        """Test routing with fallbacks enabled"""
        mock_query_router.route_with_confidence.return_value = (
            "visa_oracle",
            0.7,
            ["visa_oracle", "legal_architect"],
        )

        result = integration.route_query(
            query="Tell me about visas", collection_override=None, enable_fallbacks=True
        )

        assert result["collection_name"] == "visa_oracle"
        assert len(result["collections"]) == 2
        assert result["confidence"] == 0.7
        mock_query_router.route_with_confidence.assert_called_once()

    def test_route_query_case_insensitive(self, integration):
        """Test that pricing detection is case insensitive"""
        assert integration.is_pricing_query("PRICE") is True
        assert integration.is_pricing_query("Price") is True
        assert integration.is_pricing_query("price") is True
