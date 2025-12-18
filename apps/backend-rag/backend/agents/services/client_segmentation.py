"""
Client Segmentation Service

Responsibility: Segment clients and calculate risk levels based on LTV scores.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Constants for scoring thresholds
VIP_LTV_THRESHOLD = 80
HIGH_VALUE_LTV_THRESHOLD = 60
MEDIUM_VALUE_LTV_THRESHOLD = 40
HIGH_RISK_LTV_THRESHOLD = 70
HIGH_RISK_INACTIVE_DAYS = 30
VIP_INACTIVE_DAYS = 14
HIGH_VALUE_INACTIVE_DAYS = 60


class ClientSegmentationService:
    """Service for segmenting clients and calculating risk levels"""

    def calculate_risk(self, ltv_score: float, days_since_last: int) -> str:
        """
        Calculate churn risk level.

        Args:
            ltv_score: Lifetime value score (0-100)
            days_since_last: Days since last interaction

        Returns:
            Risk level: "HIGH_RISK", "MEDIUM_RISK", or "LOW_RISK"
        """
        if ltv_score >= HIGH_RISK_LTV_THRESHOLD and days_since_last > HIGH_RISK_INACTIVE_DAYS:
            return "HIGH_RISK"  # High-value but inactive
        elif ltv_score >= HIGH_RISK_LTV_THRESHOLD:
            return "LOW_RISK"  # High-value and active
        elif days_since_last > HIGH_VALUE_INACTIVE_DAYS:
            return "MEDIUM_RISK"  # Low-value and inactive
        else:
            return "LOW_RISK"

    def get_segment(self, ltv_score: float) -> str:
        """
        Segment client based on LTV score.

        Args:
            ltv_score: Lifetime value score (0-100)

        Returns:
            Segment: "VIP", "HIGH_VALUE", "MEDIUM_VALUE", or "LOW_VALUE"
        """
        if ltv_score >= VIP_LTV_THRESHOLD:
            return "VIP"
        elif ltv_score >= HIGH_VALUE_LTV_THRESHOLD:
            return "HIGH_VALUE"
        elif ltv_score >= MEDIUM_VALUE_LTV_THRESHOLD:
            return "MEDIUM_VALUE"
        else:
            return "LOW_VALUE"

    def enrich_client_data(self, client_data: dict[str, Any]) -> dict[str, Any]:
        """
        Add segmentation and risk data to client score data.

        Args:
            client_data: Client score data from ClientScoringService

        Returns:
            Enriched client data with segment and risk_level
        """
        ltv_score = client_data.get("ltv_score", 0.0)
        days_since_last = client_data.get("days_since_last_interaction", 999)

        client_data["segment"] = self.get_segment(ltv_score)
        client_data["risk_level"] = self.calculate_risk(ltv_score, days_since_last)

        return client_data

    def should_nurture(self, client_data: dict[str, Any]) -> tuple[bool, str]:
        """
        Determine if a client should be nurtured and why.

        Args:
            client_data: Enriched client data with segment and risk_level

        Returns:
            Tuple of (should_nurture: bool, reason: str)
        """
        segment = client_data.get("segment", "")
        risk_level = client_data.get("risk_level", "")
        days_since_last = client_data.get("days_since_last_interaction", 999)

        if segment == "VIP" and days_since_last > VIP_INACTIVE_DAYS:
            return True, "VIP inactive for 14+ days"
        elif risk_level == "HIGH_RISK":
            return True, "High-value client at risk of churn"
        elif segment in ["HIGH_VALUE", "VIP"] and days_since_last > HIGH_VALUE_INACTIVE_DAYS:
            return True, "High-value client inactive for 60+ days"

        return False, ""










