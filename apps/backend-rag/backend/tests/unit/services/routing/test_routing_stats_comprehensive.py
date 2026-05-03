"""
Comprehensive tests for RoutingStatsService
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.routing.routing_stats import RoutingStatsService  # noqa: E402


@pytest.fixture
def routing_stats():
    """Create RoutingStatsService instance"""
    return RoutingStatsService()


class TestRoutingStatsService:
    """Tests for RoutingStatsService"""

    def test_init(self):
        """Test initialization"""
        stats = RoutingStatsService()
        assert stats.fallback_stats["total_routes"] == 0
        assert stats.fallback_stats["high_confidence"] == 0
        assert stats.fallback_stats["medium_confidence"] == 0
        assert stats.fallback_stats["low_confidence"] == 0
        assert stats.fallback_stats["fallbacks_used"] == 0

    def test_record_route_high_confidence(self, routing_stats):
        """Test recording route with high confidence"""
        routing_stats.record_route(confidence=0.85, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 1
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 0

    def test_record_route_medium_confidence(self, routing_stats):
        """Test recording route with medium confidence"""
        routing_stats.record_route(confidence=0.5, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 1
        assert routing_stats.fallback_stats["low_confidence"] == 0

    def test_record_route_low_confidence(self, routing_stats):
        """Test recording route with low confidence"""
        routing_stats.record_route(confidence=0.2, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 1

    def test_record_route_with_fallback(self, routing_stats):
        """Test recording route with fallback used"""
        routing_stats.record_route(confidence=0.5, fallbacks_used=True)
        assert routing_stats.fallback_stats["fallbacks_used"] == 1

    def test_record_route_custom_thresholds(self, routing_stats):
        """Test recording route with custom thresholds"""
        routing_stats.record_route(
            confidence=0.6,
            fallbacks_used=False,
            confidence_threshold_high=0.8,
            confidence_threshold_low=0.4,
        )
        assert routing_stats.fallback_stats["medium_confidence"] == 1

    def test_record_route_boundary_high(self, routing_stats):
        """Test recording route at high confidence boundary"""
        routing_stats.record_route(confidence=0.7, fallbacks_used=False)
        assert routing_stats.fallback_stats["high_confidence"] == 1

    def test_record_route_boundary_low(self, routing_stats):
        """Test recording route at low confidence boundary"""
        routing_stats.record_route(confidence=0.3, fallbacks_used=False)
        assert routing_stats.fallback_stats["medium_confidence"] == 1

    def test_get_fallback_stats_empty(self, routing_stats):
        """Test getting stats when no routes recorded"""
        stats = routing_stats.get_fallback_stats()
        assert stats["total_routes"] == 0
        assert stats["fallback_rate"] == "0.0%"
        assert stats["confidence_distribution"]["high"] == "0.0%"
        assert stats["confidence_distribution"]["medium"] == "0.0%"
        assert stats["confidence_distribution"]["low"] == "0.0%"

    def test_get_fallback_stats_with_routes(self, routing_stats):
        """Test getting stats with recorded routes"""
        routing_stats.record_route(confidence=0.85, fallbacks_used=True)
        routing_stats.record_route(confidence=0.5, fallbacks_used=False)
        routing_stats.record_route(confidence=0.2, fallbacks_used=True)

        stats = routing_stats.get_fallback_stats()
        assert stats["total_routes"] == 3
        assert stats["high_confidence"] == 1
        assert stats["medium_confidence"] == 1
        assert stats["low_confidence"] == 1
        assert stats["fallbacks_used"] == 2
        assert stats["fallback_rate"] == "66.7%"
        assert "confidence_distribution" in stats

    def test_get_fallback_stats_percentages(self, routing_stats):
        """Test getting stats with correct percentages"""
        # Record 10 routes: 5 high, 3 medium, 2 low
        for _ in range(5):
            routing_stats.record_route(confidence=0.85, fallbacks_used=False)
        for _ in range(3):
            routing_stats.record_route(confidence=0.5, fallbacks_used=False)
        for _ in range(2):
            routing_stats.record_route(confidence=0.2, fallbacks_used=False)

        stats = routing_stats.get_fallback_stats()
        assert stats["confidence_distribution"]["high"] == "50.0%"
        assert stats["confidence_distribution"]["medium"] == "30.0%"
        assert stats["confidence_distribution"]["low"] == "20.0%"

    def test_reset_stats(self, routing_stats):
        """Test resetting statistics"""
        routing_stats.record_route(confidence=0.85, fallbacks_used=True)
        routing_stats.record_route(confidence=0.5, fallbacks_used=False)

        routing_stats.reset_stats()

        assert routing_stats.fallback_stats["total_routes"] == 0
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 0
        assert routing_stats.fallback_stats["fallbacks_used"] == 0

    def test_multiple_routes_accumulation(self, routing_stats):
        """Test that multiple routes accumulate correctly"""
        routing_stats.record_route(confidence=0.85, fallbacks_used=True)
        routing_stats.record_route(confidence=0.9, fallbacks_used=False)
        routing_stats.record_route(confidence=0.4, fallbacks_used=True)

        assert routing_stats.fallback_stats["total_routes"] == 3
        assert routing_stats.fallback_stats["high_confidence"] == 2
        assert routing_stats.fallback_stats["medium_confidence"] == 1
        assert routing_stats.fallback_stats["fallbacks_used"] == 2
