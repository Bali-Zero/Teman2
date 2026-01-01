"""
Unit tests for RoutingStatsService
Target: >95% coverage
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.routing_stats import RoutingStatsService


@pytest.fixture
def routing_stats():
    """Create RoutingStatsService instance"""
    return RoutingStatsService()


class TestRoutingStatsService:
    """Tests for RoutingStatsService"""

    def test_init(self, routing_stats):
        """Test initialization"""
        assert routing_stats.fallback_stats["total_routes"] == 0
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 0
        assert routing_stats.fallback_stats["fallbacks_used"] == 0

    def test_record_route_high_confidence(self, routing_stats):
        """Test recording high confidence route"""
        routing_stats.record_route(confidence=0.8, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 1
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 0

    def test_record_route_medium_confidence(self, routing_stats):
        """Test recording medium confidence route"""
        routing_stats.record_route(confidence=0.5, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 1
        assert routing_stats.fallback_stats["low_confidence"] == 0

    def test_record_route_low_confidence(self, routing_stats):
        """Test recording low confidence route"""
        routing_stats.record_route(confidence=0.2, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 1
        assert routing_stats.fallback_stats["high_confidence"] == 0
        assert routing_stats.fallback_stats["medium_confidence"] == 0
        assert routing_stats.fallback_stats["low_confidence"] == 1

    def test_record_route_with_fallback(self, routing_stats):
        """Test recording route with fallback"""
        routing_stats.record_route(confidence=0.8, fallbacks_used=True)
        assert routing_stats.fallback_stats["fallbacks_used"] == 1

    def test_record_route_custom_thresholds(self, routing_stats):
        """Test recording route with custom thresholds"""
        routing_stats.record_route(
            confidence=0.6,
            fallbacks_used=False,
            confidence_threshold_high=0.8,
            confidence_threshold_low=0.4
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

    def test_record_route_multiple(self, routing_stats):
        """Test recording multiple routes"""
        routing_stats.record_route(confidence=0.8, fallbacks_used=False)
        routing_stats.record_route(confidence=0.5, fallbacks_used=True)
        routing_stats.record_route(confidence=0.2, fallbacks_used=False)
        assert routing_stats.fallback_stats["total_routes"] == 3
        assert routing_stats.fallback_stats["high_confidence"] == 1
        assert routing_stats.fallback_stats["medium_confidence"] == 1
        assert routing_stats.fallback_stats["low_confidence"] == 1
        assert routing_stats.fallback_stats["fallbacks_used"] == 1

    def test_get_fallback_stats(self, routing_stats):
        """Test getting fallback statistics"""
        routing_stats.record_route(confidence=0.8, fallbacks_used=False)
        stats = routing_stats.get_fallback_stats()
        assert stats["total_routes"] == 1
        assert stats["high_confidence"] == 1
        assert "fallback_rate" in stats
        assert "confidence_distribution" in stats
        assert isinstance(stats, dict)

    def test_reset_stats(self, routing_stats):
        """Test resetting statistics"""
        routing_stats.record_route(confidence=0.8, fallbacks_used=False)
        routing_stats.reset_stats()
        assert routing_stats.fallback_stats["total_routes"] == 0
        assert routing_stats.fallback_stats["high_confidence"] == 0
