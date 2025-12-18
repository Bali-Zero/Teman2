"""
Integration Tests for QueryRouter
Tests intelligent query routing to appropriate collections
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestQueryRouterIntegration:
    """Comprehensive integration tests for QueryRouter"""

    @pytest.fixture
    def router(self):
        """Create QueryRouter instance"""
        from services.query_router import QueryRouter

        return QueryRouter()

    def test_initialization(self, router):
        """Test router initialization"""
        assert router is not None

    def test_route_visa_query(self, router):
        """Test routing visa-related query"""
        result = router.route_query("How to get a visa for Indonesia?")

        assert result is not None
        assert "collection_name" in result
        assert (
            "visa" in result["collection_name"].lower()
            or "immigration" in result.get("reason", "").lower()
        )

    def test_route_kbli_query(self, router):
        """Test routing KBLI-related query"""
        result = router.route_query("What is KBLI code for software development?")

        assert result is not None
        assert "collection_name" in result
        assert (
            "kbli" in result["collection_name"].lower()
            or "kbli" in result.get("reason", "").lower()
        )

    def test_route_tax_query(self, router):
        """Test routing tax-related query"""
        result = router.route_query("How to calculate income tax in Indonesia?")

        assert result is not None
        assert "collection_name" in result
        assert (
            "tax" in result["collection_name"].lower() or "tax" in result.get("reason", "").lower()
        )

    def test_route_legal_query(self, router):
        """Test routing legal-related query"""
        result = router.route_query("How to set up a PT PMA company?")

        assert result is not None
        assert "collection_name" in result
        assert (
            "legal" in result["collection_name"].lower()
            or "legal" in result.get("reason", "").lower()
        )

    def test_route_property_query(self, router):
        """Test routing property-related query"""
        result = router.route_query("How to buy property in Bali?")

        assert result is not None
        assert "collection_name" in result

    def test_route_ambiguous_query(self, router):
        """Test routing ambiguous query"""
        result = router.route_query("What is the process?")

        assert result is not None
        assert "collection_name" in result
        # Should route to default or most common collection

    def test_route_multilingual_query(self, router):
        """Test routing query in different languages"""
        # Italian
        result_it = router.route_query("Come ottenere un visto per l'Indonesia?")
        assert result_it is not None

        # Indonesian
        result_id = router.route_query("Bagaimana cara mendapatkan visa untuk Indonesia?")
        assert result_id is not None

        # English
        result_en = router.route_query("How to get a visa for Indonesia?")
        assert result_en is not None

    def test_route_query_with_confidence(self, router):
        """Test routing with confidence scoring"""
        result = router.route_query("visa application process")

        assert result is not None
        # May include confidence score if implemented
        assert "collection_name" in result

    def test_route_query_fallback(self, router):
        """Test routing with fallback chain"""
        result = router.route_query("general information about Indonesia")

        assert result is not None
        assert "collection_name" in result

    def test_get_collection_for_domain(self, router):
        """Test getting collection for specific domain"""
        # Test visa domain
        collection = router.get_collection_for_domain("visa")
        assert collection is not None

        # Test tax domain
        collection = router.get_collection_for_domain("tax")
        assert collection is not None

    def test_get_fallback_chain(self, router):
        """Test getting fallback chain for domain"""
        chain = router.get_fallback_chain("visa")
        assert chain is not None
        assert isinstance(chain, list)

    def test_route_query_with_specific_codes(self, router):
        """Test routing queries with specific visa/business codes"""
        # E33G query
        result = router.route_query("What is E33G visa?")
        assert result is not None

        # B211 query (legacy)
        result = router.route_query("What is B211 visa?")
        assert result is not None

        # KBLI code query
        result = router.route_query("What is KBLI 62010?")
        assert result is not None
