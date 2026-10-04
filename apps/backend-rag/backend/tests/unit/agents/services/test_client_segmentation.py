"""
Unit tests for ClientSegmentationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from typing import Any

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.services.client_segmentation import ClientSegmentationService


@pytest.fixture
def client_segmentation_service() -> ClientSegmentationService:
    """Create ClientSegmentationService instance"""
    return ClientSegmentationService()


class TestClientSegmentationService:
    """Tests for ClientSegmentationService"""

    def test_init(self):
        """Test initialization"""
        service = ClientSegmentationService()
        assert service is not None

    def test_calculate_risk_high_risk(self, client_segmentation_service):
        """Test calculating high risk"""
        risk = client_segmentation_service.calculate_risk(ltv_score=80.0, days_since_last=35)
        assert risk == "HIGH_RISK"

    def test_calculate_risk_low_risk_high_value(self, client_segmentation_service):
        """Test calculating low risk for high value active client"""
        risk = client_segmentation_service.calculate_risk(ltv_score=80.0, days_since_last=10)
        assert risk == "LOW_RISK"

    def test_calculate_risk_medium_risk(self, client_segmentation_service):
        """Test calculating medium risk"""
        risk = client_segmentation_service.calculate_risk(ltv_score=50.0, days_since_last=65)
        assert risk == "MEDIUM_RISK"

    def test_calculate_risk_low_risk_low_value(self, client_segmentation_service):
        """Test calculating low risk for low value active client"""
        risk = client_segmentation_service.calculate_risk(ltv_score=30.0, days_since_last=20)
        assert risk == "LOW_RISK"

    def test_get_segment_vip(self, client_segmentation_service):
        """Test getting VIP segment"""
        segment = client_segmentation_service.get_segment(ltv_score=85.0)
        assert segment == "VIP"

    def test_get_segment_high_value(self, client_segmentation_service):
        """Test getting HIGH_VALUE segment"""
        segment = client_segmentation_service.get_segment(ltv_score=70.0)
        assert segment == "HIGH_VALUE"

    def test_get_segment_medium_value(self, client_segmentation_service):
        """Test getting MEDIUM_VALUE segment"""
        segment = client_segmentation_service.get_segment(ltv_score=50.0)
        assert segment == "MEDIUM_VALUE"

    def test_get_segment_low_value(self, client_segmentation_service):
        """Test getting LOW_VALUE segment"""
        segment = client_segmentation_service.get_segment(ltv_score=30.0)
        assert segment == "LOW_VALUE"

    def test_enrich_client_data(self, client_segmentation_service):
        """Test enriching client data"""
        client_data = {"client_id": "123", "ltv_score": 75.0, "days_since_last_interaction": 20}

        enriched = client_segmentation_service.enrich_client_data(client_data)
        assert "segment" in enriched
        assert "risk_level" in enriched
        assert enriched["segment"] == "HIGH_VALUE"
        assert enriched["risk_level"] == "LOW_RISK"

    def test_should_nurture_vip_inactive(self, client_segmentation_service):
        """Test should nurture VIP inactive"""
        client_data = {
            "segment": "VIP",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 20,
        }

        should_nurture, reason = client_segmentation_service.should_nurture(client_data)
        assert should_nurture is True
        assert "VIP" in reason

    def test_should_nurture_high_risk(self, client_segmentation_service):
        """Test should nurture high risk"""
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "HIGH_RISK",
            "days_since_last_interaction": 35,
        }

        should_nurture, reason = client_segmentation_service.should_nurture(client_data)
        assert should_nurture is True
        assert "risk" in reason.lower()

    def test_should_nurture_high_value_inactive(self, client_segmentation_service):
        """Test should nurture high value inactive"""
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 65,
        }

        should_nurture, reason = client_segmentation_service.should_nurture(client_data)
        assert should_nurture is True

    def test_should_nurture_false(self, client_segmentation_service):
        """Test should not nurture"""
        client_data = {
            "segment": "LOW_VALUE",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 10,
        }

        should_nurture, reason = client_segmentation_service.should_nurture(client_data)
        assert should_nurture is False
        assert reason == ""

    @pytest.mark.parametrize(
        ("ltv_score", "expected_segment"),
        [
            (80.0, "VIP"),
            (79.99, "HIGH_VALUE"),
            (60.0, "HIGH_VALUE"),
            (59.99, "MEDIUM_VALUE"),
            (40.0, "MEDIUM_VALUE"),
            (39.99, "LOW_VALUE"),
        ],
    )
    def test_get_segment_uses_inclusive_lower_bounds(
        self,
        client_segmentation_service: ClientSegmentationService,
        ltv_score: float,
        expected_segment: str,
    ) -> None:
        """Catch off-by-one changes around segment thresholds."""
        assert client_segmentation_service.get_segment(ltv_score) == expected_segment

    @pytest.mark.parametrize(
        ("ltv_score", "days_since_last", "expected_risk"),
        [
            (70.0, 31, "HIGH_RISK"),
            (70.0, 30, "LOW_RISK"),
            (69.99, 61, "MEDIUM_RISK"),
            (69.99, 60, "LOW_RISK"),
            (70.0, 61, "HIGH_RISK"),
        ],
    )
    def test_calculate_risk_respects_threshold_precedence(
        self,
        client_segmentation_service: ClientSegmentationService,
        ltv_score: float,
        days_since_last: int,
        expected_risk: str,
    ) -> None:
        """Catch threshold strictness and high-LTV precedence regressions."""
        assert client_segmentation_service.calculate_risk(ltv_score, days_since_last) == expected_risk

    def test_enrich_client_data_defaults_missing_scores_and_mutates_input(
        self,
        client_segmentation_service: ClientSegmentationService,
    ) -> None:
        """Catch fallback changes for partial score payloads."""
        client_data: dict[str, Any] = {"client_id": "synthetic-client"}

        enriched = client_segmentation_service.enrich_client_data(client_data)

        assert enriched is client_data
        assert enriched["segment"] == "LOW_VALUE"
        assert enriched["risk_level"] == "MEDIUM_RISK"

    @pytest.mark.parametrize(
        ("client_data", "expected"),
        [
            ({"segment": "VIP", "risk_level": "HIGH_RISK", "days_since_last_interaction": 15}, (True, "VIP inactive for 14+ days")),
            ({"segment": "VIP", "risk_level": "LOW_RISK", "days_since_last_interaction": 14}, (False, "")),
            ({"segment": "HIGH_VALUE", "risk_level": "LOW_RISK", "days_since_last_interaction": 60}, (False, "")),
            ({"segment": "HIGH_VALUE", "risk_level": "LOW_RISK", "days_since_last_interaction": 61}, (True, "High-value client inactive for 60+ days")),
            ({}, (False, "")),
        ],
    )
    def test_should_nurture_handles_priority_boundaries_and_missing_data(
        self,
        client_segmentation_service: ClientSegmentationService,
        client_data: dict[str, Any],
        expected: tuple[bool, str],
    ) -> None:
        """Catch reason priority, strict day boundaries, and empty payload defaults."""
        assert client_segmentation_service.should_nurture(client_data) == expected
