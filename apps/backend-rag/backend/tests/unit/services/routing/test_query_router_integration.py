"""
Unit tests for QueryRouterIntegration
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.routing.query_router_integration import QueryRouterIntegration


@pytest.fixture
def query_router_integration():
    """Create QueryRouterIntegration instance"""
    return QueryRouterIntegration()


class TestQueryRouterIntegration:
    """Tests for QueryRouterIntegration"""

    def test_init(self):
        """Test initialization"""
        integration = QueryRouterIntegration()
        assert integration.router is not None
        assert len(integration.pricing_keywords) > 0

    def test_init_with_router(self):
        """Test initialization with custom router"""
        mock_router = MagicMock()
        integration = QueryRouterIntegration(query_router=mock_router)
        assert integration.router == mock_router

    def test_is_pricing_query_true(self, query_router_integration):
        """Test detecting pricing query"""
        assert query_router_integration.is_pricing_query("what is the price") is True
        assert query_router_integration.is_pricing_query("quanto costa") is True
        assert query_router_integration.is_pricing_query("berapa harga") is True

    def test_is_pricing_query_false(self, query_router_integration):
        """Test detecting non-pricing query"""
        assert query_router_integration.is_pricing_query("what is visa") is False
        assert query_router_integration.is_pricing_query("how to apply") is False

    def test_route_query(self, query_router_integration):
        """Test routing query"""
        result = query_router_integration.route_query("what is visa")
        assert isinstance(result, dict)
        assert "primary_collection" in result or "collections" in result

    def test_route_query_with_override(self, query_router_integration):
        """Test routing query with collection override"""
        result = query_router_integration.route_query(
            "test query", collection_override="visa_oracle"
        )
        assert isinstance(result, dict)

    def test_route_query_with_fallbacks(self, query_router_integration):
        """Test routing query with fallbacks enabled"""
        result = query_router_integration.route_query("test query", enable_fallbacks=True)
        assert isinstance(result, dict)
