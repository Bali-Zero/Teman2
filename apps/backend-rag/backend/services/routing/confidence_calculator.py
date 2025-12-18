"""
Confidence Calculator Service
Responsibility: Calculate confidence scores for routing decisions
"""

import logging

from app.core.constants import RoutingConstants

logger = logging.getLogger(__name__)


class ConfidenceCalculatorService:
    """
    Service for calculating routing confidence scores.

    Responsibility: Calculate confidence based on match strength, query length, and domain specificity.
    """

    CONFIDENCE_THRESHOLD_HIGH = RoutingConstants.CONFIDENCE_THRESHOLD_HIGH
    CONFIDENCE_THRESHOLD_LOW = RoutingConstants.CONFIDENCE_THRESHOLD_LOW

    def calculate_confidence(self, query: str, domain_scores: dict[str, int]) -> float:
        """
        Calculate confidence score for routing decision.

        Confidence factors:
        - Keyword match strength (primary factor)
        - Query length (longer = more context = higher confidence)
        - Domain specificity (clear winner vs. tie)

        Args:
            query: User query text
            domain_scores: Dictionary of domain scores from routing

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Get max score and total matches
        max_score = max(domain_scores.values())
        total_matches = sum(domain_scores.values())

        # Factor 1: Match strength (0.0 - 0.6)
        # 0 matches = 0.0, 1-2 matches = 0.3, 3-4 matches = 0.5, 5+ = 0.6
        if max_score == 0:
            match_confidence = 0.0
        elif max_score <= 2:
            match_confidence = 0.2 + (max_score * 0.1)
        elif max_score <= 4:
            match_confidence = 0.4 + ((max_score - 2) * 0.05)
        else:
            match_confidence = 0.6

        # Factor 2: Query length (0.0 - 0.2)
        # Short queries (<10 words) = lower confidence
        word_count = len(query.split())
        if word_count < 5:
            length_confidence = 0.0
        elif word_count < 10:
            length_confidence = 0.1
        else:
            length_confidence = 0.2

        # Factor 3: Domain specificity (0.0 - 0.2)
        # Clear winner (max >> others) = higher confidence
        if total_matches == 0:
            specificity_confidence = 0.0
        else:
            sorted_scores = sorted(domain_scores.values(), reverse=True)
            second_max = sorted_scores[1] if len(sorted_scores) > 1 else 0
            if max_score > second_max * 2:  # Clear winner
                specificity_confidence = 0.2
            elif max_score > second_max:
                specificity_confidence = 0.1
            else:
                specificity_confidence = 0.0  # Tie or close call

        total_confidence = match_confidence + length_confidence + specificity_confidence
        return min(total_confidence, 1.0)  # Cap at 1.0

    def get_confidence_level(self, confidence: float) -> str:
        """
        Get confidence level label.

        Args:
            confidence: Confidence score (0.0 - 1.0)

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if confidence >= self.CONFIDENCE_THRESHOLD_HIGH:
            return "high"
        elif confidence >= self.CONFIDENCE_THRESHOLD_LOW:
            return "medium"
        else:
            return "low"
