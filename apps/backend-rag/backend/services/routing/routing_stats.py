"""
Routing Statistics Service
Responsibility: Track routing statistics and metrics
"""

import logging

logger = logging.getLogger(__name__)


class RoutingStatsService:
    """
    Service for tracking routing statistics.

    Responsibility: Record routing metrics and provide statistics.
    """

    def __init__(self):
        """Initialize routing statistics service."""
        self.fallback_stats = {
            "total_routes": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "fallbacks_used": 0,
        }

    def record_route(
        self,
        confidence: float,
        fallbacks_used: bool,
        confidence_threshold_high: float = 0.7,
        confidence_threshold_low: float = 0.3,
    ):
        """
        Record a routing decision.

        Args:
            confidence: Confidence score (0.0 - 1.0)
            fallbacks_used: Whether fallback collections were used
            confidence_threshold_high: High confidence threshold
            confidence_threshold_low: Low confidence threshold
        """
        self.fallback_stats["total_routes"] += 1

        if confidence >= confidence_threshold_high:
            self.fallback_stats["high_confidence"] += 1
        elif confidence >= confidence_threshold_low:
            self.fallback_stats["medium_confidence"] += 1
        else:
            self.fallback_stats["low_confidence"] += 1

        if fallbacks_used:
            self.fallback_stats["fallbacks_used"] += 1

    def get_fallback_stats(self) -> dict:
        """
        Get statistics about fallback chain usage.

        Returns:
            Dictionary with fallback metrics:
            - total_routes: Total routing calls
            - high_confidence: Routes with confidence > 0.7
            - medium_confidence: Routes with confidence 0.3-0.7
            - low_confidence: Routes with confidence < 0.3
            - fallbacks_used: Number of times fallback collections were suggested
            - fallback_rate: Percentage of routes using fallbacks
        """
        total = self.fallback_stats["total_routes"]
        fallback_rate = (self.fallback_stats["fallbacks_used"] / total * 100) if total > 0 else 0.0

        return {
            **self.fallback_stats,
            "fallback_rate": f"{fallback_rate:.1f}%",
            "confidence_distribution": {
                "high": f"{(self.fallback_stats['high_confidence'] / total * 100) if total > 0 else 0:.1f}%",
                "medium": f"{(self.fallback_stats['medium_confidence'] / total * 100) if total > 0 else 0:.1f}%",
                "low": f"{(self.fallback_stats['low_confidence'] / total * 100) if total > 0 else 0:.1f}%",
            },
        }

    def reset_stats(self):
        """Reset all statistics."""
        self.fallback_stats = {
            "total_routes": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "fallbacks_used": 0,
        }
