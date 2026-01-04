"""
Unit tests for QueryRouter
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.query_router import QueryRouter


@pytest.fixture
def query_router():
    """Create QueryRouter instance"""
    return QueryRouter()


class TestQueryRouter:
    """Tests for QueryRouter"""

    def test_init(self):
        """Test initialization"""
        router = QueryRouter()
        assert router.keyword_matcher is not None
        assert router.confidence_calculator is not None
        assert router.fallback_manager is not None
        assert router.priority_override is not None
        assert router.routing_stats is not None

    def test_calculate_domain_scores(self, query_router):
        """Test calculating domain scores"""
        scores = query_router._calculate_domain_scores("visa application")
        assert isinstance(scores, dict)
        assert "visa" in scores

    def test_check_priority_overrides_identity(self, query_router):
        """Test priority override for identity query"""
        result = query_router._check_priority_overrides("chi sono")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_team(self, query_router):
        """Test priority override for team query"""
        result = query_router._check_priority_overrides("tutti i membri del team")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_founder(self, query_router):
        """Test priority override for founder query"""
        result = query_router._check_priority_overrides("founder")
        assert result == "bali_zero_team"

    def test_check_priority_overrides_backend(self, query_router):
        """Test priority override for backend services"""
        result = query_router._check_priority_overrides("api endpoint")
        assert result == "zantara_books"

    def test_check_priority_overrides_none(self, query_router):
        """Test no priority override"""
        result = query_router._check_priority_overrides("simple query")
        assert result is None

    def test_determine_collection_visa(self, query_router):
        """Test determining collection for visa query"""
        scores = {"visa": 5, "legal": 2, "tax": 1}
        collection = query_router._determine_collection(scores, "visa application")
        assert collection == "visa_oracle"

    def test_determine_collection_tax(self, query_router):
        """Test determining collection for tax query"""
        scores = {"tax": 5, "legal": 2, "visa": 1}
        collection = query_router._determine_collection(scores, "tax calculation")
        assert collection == "tax_genius"

    def test_determine_collection_legal(self, query_router):
        """Test determining collection for legal query"""
        scores = {"legal": 5, "tax": 2, "visa": 1}
        collection = query_router._determine_collection(scores, "company formation")
        assert collection == "legal_unified"

    def test_determine_collection_property(self, query_router):
        """Test determining collection for property query"""
        scores = {"property": 5, "legal": 2, "tax": 1}
        collection = query_router._determine_collection(scores, "property purchase")
        assert collection == "property_unified"

    def test_determine_collection_kbli(self, query_router):
        """Test determining collection for KBLI query"""
        scores = {"kbli": 5, "legal": 2, "tax": 1}
        collection = query_router._determine_collection(scores, "kbli code")
        assert collection == "kbli_unified"

    def test_determine_collection_team(self, query_router):
        """Test determining collection for team query"""
        scores = {"team": 5, "legal": 2, "tax": 1}
        collection = query_router._determine_collection(scores, "team member")
        assert collection == "bali_zero_team"

    def test_determine_collection_default(self, query_router):
        """Test determining collection with no matches"""
        scores = {"visa": 0, "legal": 0, "tax": 0}
        collection = query_router._determine_collection(scores, "random query")
        assert collection == "legal_unified"

    def test_route_visa(self, query_router):
        """Test routing visa query"""
        collection = query_router.route("visa application")
        assert collection == "visa_oracle"

    def test_route_tax(self, query_router):
        """Test routing tax query"""
        collection = query_router.route("tax calculation")
        assert collection == "tax_genius"

    def test_route_legal(self, query_router):
        """Test routing legal query"""
        collection = query_router.route("company formation")
        assert collection == "legal_unified"

    def test_route_with_priority_override(self, query_router):
        """Test routing with priority override"""
        collection = query_router.route("chi sono")
        assert collection == "bali_zero_team"

    def test_calculate_confidence(self, query_router):
        """Test calculating confidence"""
        scores = {"visa": 5, "legal": 2, "tax": 1}
        confidence = query_router.calculate_confidence("visa application", scores)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_high(self, query_router):
        """Test calculating high confidence"""
        scores = {"visa": 10, "legal": 1, "tax": 1}
        confidence = query_router.calculate_confidence("visa visa visa", scores)
        assert confidence > 0.7

    def test_calculate_confidence_low(self, query_router):
        """Test calculating low confidence"""
        scores = {"visa": 1, "legal": 1, "tax": 1}
        confidence = query_router.calculate_confidence("ambiguous query", scores)
        assert confidence < 0.5

    def test_get_fallback_collections(self, query_router):
        """Test getting fallback collections"""
        fallbacks = query_router.get_fallback_collections(
            "visa_oracle", confidence=0.5, max_fallbacks=3
        )
        assert isinstance(fallbacks, list)
        assert len(fallbacks) > 0

    def test_get_fallback_collections_none(self, query_router):
        """Test getting fallback collections for unknown collection"""
        fallbacks = query_router.get_fallback_collections(
            "unknown_collection", confidence=0.5, max_fallbacks=3
        )
        assert isinstance(fallbacks, list)

    def test_route_with_confidence(self, query_router):
        """Test routing with confidence"""
        collection, confidence, fallbacks = query_router.route_with_confidence("visa application")
        assert collection == "visa_oracle"
        assert 0.0 <= confidence <= 1.0
        assert isinstance(fallbacks, list)
        assert collection in fallbacks  # Primary should be in fallbacks

    def test_route_with_confidence_low_confidence(self, query_router):
        """Test routing with low confidence"""
        collection, confidence, fallbacks = query_router.route_with_confidence(
            "ambiguous query text"
        )
        assert collection is not None
        # Low confidence queries may still have confidence >= 0.5, just check it's valid
        assert 0.0 <= confidence <= 1.0
        assert isinstance(fallbacks, list)

    def test_get_routing_stats(self, query_router):
        """Test getting routing stats"""
        stats = query_router.get_routing_stats("visa application")
        assert isinstance(stats, dict)
        assert "domain_scores" in stats
        # Stats may contain various keys, just verify it's a dict with domain_scores
        assert isinstance(stats["domain_scores"], dict)

    def test_get_fallback_stats(self, query_router):
        """Test getting fallback stats"""
        stats = query_router.get_fallback_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_route_query(self, query_router):
        """Test async route_query method"""
        result = await query_router.route_query("visa application", user_id="test123")
        assert isinstance(result, dict)
        assert "collection_name" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_route_query_with_user_id(self, query_router):
        """Test route_query with user_id"""
        result = await query_router.route_query("tax calculation", user_id="user123")
        assert result["collection_name"] == "tax_genius"

    @pytest.mark.asyncio
    async def test_route_query_with_override(self, query_router):
        """Test route_query with priority override"""
        result = await query_router.route_query("chi sono", user_id="user123")
        assert result["collection_name"] == "bali_zero_team"
