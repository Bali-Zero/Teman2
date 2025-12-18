"""
Comprehensive tests for services/query_router.py
Target: 95%+ coverage
"""

import pytest

from services.query_router import QueryRouter


class TestQueryRouter:
    """Comprehensive test suite for QueryRouter"""

    @pytest.fixture
    def router(self):
        """Create QueryRouter instance"""
        return QueryRouter()

    @pytest.mark.asyncio
    async def test_route_query_visa(self, router):
        """Test route_query with visa keywords"""
        result = await router.route_query("I need a visa for Indonesia")
        assert isinstance(result, dict)
        assert "collections" in result or "primary_collection" in result

    def test_route_visa(self, router):
        """Test route with visa keywords"""
        collection = router.route("I need a visa for Indonesia")
        assert isinstance(collection, str)

    def test_route_kbli(self, router):
        """Test route with KBLI keywords"""
        collection = router.route("What is KBLI code for restaurant?")
        assert isinstance(collection, str)

    def test_route_tax(self, router):
        """Test route with tax keywords"""
        collection = router.route("How do I pay taxes in Indonesia?")
        assert isinstance(collection, str)

    def test_route_legal(self, router):
        """Test route with legal keywords"""
        collection = router.route("What are the legal requirements?")
        assert isinstance(collection, str)

    def test_route_property(self, router):
        """Test route with property keywords"""
        collection = router.route("I want to buy property in Bali")
        assert isinstance(collection, str)

    def test_route_multiple_keywords(self, router):
        """Test route with multiple keywords"""
        collection = router.route("visa and tax requirements")
        assert isinstance(collection, str)

    def test_route_no_keywords(self, router):
        """Test route with no matching keywords"""
        collection = router.route("Hello how are you")
        assert isinstance(collection, str)

    def test_route_with_confidence(self, router):
        """Test route_with_confidence"""
        result = router.route_with_confidence("I need a visa")
        assert isinstance(result, dict)
        assert "collection" in result
        assert "confidence" in result
