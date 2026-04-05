"""
Tests for routing_stats.py - Routing statistics tracking.
"""

import pytest

from backend.services.routing.routing_stats import RoutingStatsService


@pytest.fixture
def stats_service():
    return RoutingStatsService()


class TestRecordRoute:
    """Tests for record_route method."""

    def test_high_confidence_recorded(self, stats_service):
        stats_service.record_route(confidence=0.8, fallbacks_used=False)
        stats = stats_service.fallback_stats
        assert stats["total_routes"] == 1
        assert stats["high_confidence"] == 1
        assert stats["fallbacks_used"] == 0

    def test_medium_confidence_recorded(self, stats_service):
        stats_service.record_route(confidence=0.5, fallbacks_used=True)
        stats = stats_service.fallback_stats
        assert stats["medium_confidence"] == 1
        assert stats["fallbacks_used"] == 1

    def test_low_confidence_recorded(self, stats_service):
        stats_service.record_route(confidence=0.1, fallbacks_used=True)
        stats = stats_service.fallback_stats
        assert stats["low_confidence"] == 1

    def test_multiple_routes_accumulated(self, stats_service):
        stats_service.record_route(confidence=0.8, fallbacks_used=False)
        stats_service.record_route(confidence=0.5, fallbacks_used=True)
        stats_service.record_route(confidence=0.1, fallbacks_used=True)
        stats = stats_service.fallback_stats
        assert stats["total_routes"] == 3
        assert stats["high_confidence"] == 1
        assert stats["medium_confidence"] == 1
        assert stats["low_confidence"] == 1
        assert stats["fallbacks_used"] == 2

    def test_boundary_values(self, stats_service):
        stats_service.record_route(confidence=0.7, fallbacks_used=False)
        assert stats_service.fallback_stats["high_confidence"] == 1

        stats_service.record_route(confidence=0.3, fallbacks_used=False)
        assert stats_service.fallback_stats["medium_confidence"] == 1

        stats_service.record_route(confidence=0.0, fallbacks_used=False)
        assert stats_service.fallback_stats["low_confidence"] == 1


class TestGetFallbackStats:
    """Tests for get_fallback_stats method."""

    def test_empty_stats(self, stats_service):
        stats = stats_service.get_fallback_stats()
        assert stats["total_routes"] == 0
        assert stats["fallback_rate"] == "0.0%"

    def test_stats_with_data(self, stats_service):
        stats_service.record_route(confidence=0.8, fallbacks_used=False)
        stats_service.record_route(confidence=0.5, fallbacks_used=True)
        stats = stats_service.get_fallback_stats()
        assert stats["total_routes"] == 2
        assert stats["fallback_rate"] == "50.0%"
        assert "confidence_distribution" in stats

    def test_confidence_distribution_percentages(self, stats_service):
        for _ in range(3):
            stats_service.record_route(confidence=0.8, fallbacks_used=False)
        for _ in range(7):
            stats_service.record_route(confidence=0.1, fallbacks_used=True)
        stats = stats_service.get_fallback_stats()
        assert stats["confidence_distribution"]["high"] == "30.0%"
        assert stats["confidence_distribution"]["low"] == "70.0%"


class TestResetStats:
    """Tests for reset_stats method."""

    def test_reset_clears_all(self, stats_service):
        stats_service.record_route(confidence=0.8, fallbacks_used=True)
        stats_service.record_route(confidence=0.1, fallbacks_used=True)
        stats_service.reset_stats()
        stats = stats_service.fallback_stats
        assert stats["total_routes"] == 0
        assert stats["high_confidence"] == 0
        assert stats["fallbacks_used"] == 0
