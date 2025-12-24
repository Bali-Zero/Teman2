"""
Comprehensive unit tests for client_segmentation module.

Tests the ClientSegmentationService class which segments clients and calculates
risk levels based on LTV scores and activity patterns.

Target Coverage: 90%+
"""

import sys
from pathlib import Path

import pytest

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.client_segmentation import (
    HIGH_RISK_INACTIVE_DAYS,
    HIGH_RISK_LTV_THRESHOLD,
    HIGH_VALUE_INACTIVE_DAYS,
    HIGH_VALUE_LTV_THRESHOLD,
    MEDIUM_VALUE_LTV_THRESHOLD,
    VIP_INACTIVE_DAYS,
    VIP_LTV_THRESHOLD,
    ClientSegmentationService,
)


class TestClientSegmentationService:
    """Test suite for ClientSegmentationService"""

    @pytest.fixture
    def service(self):
        """Create a ClientSegmentationService instance for testing."""
        return ClientSegmentationService()

    # ========================================================================
    # calculate_risk() tests
    # ========================================================================

    def test_calculate_risk_high_value_inactive_returns_high_risk(self, service):
        """Test that high LTV score with high inactivity returns HIGH_RISK."""
        # Arrange: LTV >= 70, days > 30
        ltv_score = 75.0
        days_since_last = 35

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "HIGH_RISK"

    def test_calculate_risk_high_value_inactive_at_threshold(self, service):
        """Test HIGH_RISK at exact threshold boundary."""
        # Arrange: LTV = 70 (threshold), days = 31 (just over threshold)
        ltv_score = HIGH_RISK_LTV_THRESHOLD
        days_since_last = HIGH_RISK_INACTIVE_DAYS + 1

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "HIGH_RISK"

    def test_calculate_risk_high_value_active_returns_low_risk(self, service):
        """Test that high LTV score with recent activity returns LOW_RISK."""
        # Arrange: LTV >= 70, days <= 30
        ltv_score = 85.0
        days_since_last = 15

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "LOW_RISK"

    def test_calculate_risk_high_value_active_at_threshold(self, service):
        """Test LOW_RISK for high value at activity threshold."""
        # Arrange: LTV >= 70, days exactly at threshold (30)
        ltv_score = 90.0
        days_since_last = HIGH_RISK_INACTIVE_DAYS

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "LOW_RISK"

    def test_calculate_risk_low_value_very_inactive_returns_medium_risk(self, service):
        """Test that low LTV score with long inactivity returns MEDIUM_RISK."""
        # Arrange: LTV < 70, days > 60
        ltv_score = 50.0
        days_since_last = 65

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "MEDIUM_RISK"

    def test_calculate_risk_low_value_very_inactive_at_threshold(self, service):
        """Test MEDIUM_RISK at exact threshold boundary."""
        # Arrange: LTV < 70, days = 61 (just over threshold)
        ltv_score = 60.0
        days_since_last = HIGH_VALUE_INACTIVE_DAYS + 1

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "MEDIUM_RISK"

    def test_calculate_risk_low_value_active_returns_low_risk(self, service):
        """Test that low LTV score with recent activity returns LOW_RISK."""
        # Arrange: LTV < 70, days <= 60
        ltv_score = 30.0
        days_since_last = 20

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "LOW_RISK"

    def test_calculate_risk_zero_ltv_zero_days(self, service):
        """Test edge case with zero LTV and zero days since last interaction."""
        # Arrange
        ltv_score = 0.0
        days_since_last = 0

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "LOW_RISK"

    def test_calculate_risk_max_ltv_max_days(self, service):
        """Test edge case with maximum LTV and very high days."""
        # Arrange
        ltv_score = 100.0
        days_since_last = 365

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "HIGH_RISK"

    def test_calculate_risk_boundary_ltv_69(self, service):
        """Test boundary case just below high risk LTV threshold."""
        # Arrange: LTV = 69 (just below 70 threshold)
        ltv_score = 69.0
        days_since_last = 100

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "MEDIUM_RISK"

    def test_calculate_risk_negative_ltv(self, service):
        """Test edge case with negative LTV score."""
        # Arrange
        ltv_score = -10.0
        days_since_last = 50

        # Act
        result = service.calculate_risk(ltv_score, days_since_last)

        # Assert
        assert result == "LOW_RISK"

    # ========================================================================
    # get_segment() tests
    # ========================================================================

    def test_get_segment_vip_returns_vip(self, service):
        """Test that LTV >= 80 returns VIP segment."""
        # Arrange
        ltv_score = 85.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "VIP"

    def test_get_segment_vip_at_threshold(self, service):
        """Test VIP segment at exact threshold (80)."""
        # Arrange
        ltv_score = VIP_LTV_THRESHOLD

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "VIP"

    def test_get_segment_vip_max_score(self, service):
        """Test VIP segment with maximum score."""
        # Arrange
        ltv_score = 100.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "VIP"

    def test_get_segment_high_value_returns_high_value(self, service):
        """Test that LTV >= 60 and < 80 returns HIGH_VALUE segment."""
        # Arrange
        ltv_score = 70.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "HIGH_VALUE"

    def test_get_segment_high_value_at_lower_threshold(self, service):
        """Test HIGH_VALUE segment at lower threshold (60)."""
        # Arrange
        ltv_score = HIGH_VALUE_LTV_THRESHOLD

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "HIGH_VALUE"

    def test_get_segment_high_value_at_upper_boundary(self, service):
        """Test HIGH_VALUE segment just below VIP threshold."""
        # Arrange
        ltv_score = 79.9

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "HIGH_VALUE"

    def test_get_segment_medium_value_returns_medium_value(self, service):
        """Test that LTV >= 40 and < 60 returns MEDIUM_VALUE segment."""
        # Arrange
        ltv_score = 50.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "MEDIUM_VALUE"

    def test_get_segment_medium_value_at_lower_threshold(self, service):
        """Test MEDIUM_VALUE segment at lower threshold (40)."""
        # Arrange
        ltv_score = MEDIUM_VALUE_LTV_THRESHOLD

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "MEDIUM_VALUE"

    def test_get_segment_medium_value_at_upper_boundary(self, service):
        """Test MEDIUM_VALUE segment just below HIGH_VALUE threshold."""
        # Arrange
        ltv_score = 59.9

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "MEDIUM_VALUE"

    def test_get_segment_low_value_returns_low_value(self, service):
        """Test that LTV < 40 returns LOW_VALUE segment."""
        # Arrange
        ltv_score = 30.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "LOW_VALUE"

    def test_get_segment_low_value_at_boundary(self, service):
        """Test LOW_VALUE segment just below MEDIUM_VALUE threshold."""
        # Arrange
        ltv_score = 39.9

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "LOW_VALUE"

    def test_get_segment_zero_ltv(self, service):
        """Test edge case with zero LTV score."""
        # Arrange
        ltv_score = 0.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "LOW_VALUE"

    def test_get_segment_negative_ltv(self, service):
        """Test edge case with negative LTV score."""
        # Arrange
        ltv_score = -5.0

        # Act
        result = service.get_segment(ltv_score)

        # Assert
        assert result == "LOW_VALUE"

    # ========================================================================
    # enrich_client_data() tests
    # ========================================================================

    def test_enrich_client_data_adds_segment_and_risk(self, service):
        """Test that enrich_client_data adds segment and risk_level fields."""
        # Arrange
        client_data = {
            "client_id": "test_123",
            "ltv_score": 75.0,
            "days_since_last_interaction": 20,
        }

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert "segment" in result
        assert "risk_level" in result
        assert result["segment"] == "HIGH_VALUE"
        assert result["risk_level"] == "LOW_RISK"
        # Original data should still be present
        assert result["client_id"] == "test_123"
        assert result["ltv_score"] == 75.0
        assert result["days_since_last_interaction"] == 20

    def test_enrich_client_data_vip_high_risk(self, service):
        """Test enrichment for VIP client with high risk."""
        # Arrange
        client_data = {
            "ltv_score": 90.0,
            "days_since_last_interaction": 45,
        }

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert result["segment"] == "VIP"
        assert result["risk_level"] == "HIGH_RISK"

    def test_enrich_client_data_missing_ltv_score_defaults_to_zero(self, service):
        """Test that missing ltv_score defaults to 0.0."""
        # Arrange
        client_data = {
            "client_id": "test_456",
            "days_since_last_interaction": 30,
        }

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert result["segment"] == "LOW_VALUE"  # 0.0 < 40
        assert result["risk_level"] == "LOW_RISK"  # 0.0 < 70 and 30 <= 60

    def test_enrich_client_data_missing_days_defaults_to_999(self, service):
        """Test that missing days_since_last_interaction defaults to 999."""
        # Arrange
        client_data = {
            "client_id": "test_789",
            "ltv_score": 50.0,
        }

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert result["segment"] == "MEDIUM_VALUE"  # 40 <= 50 < 60
        assert result["risk_level"] == "MEDIUM_RISK"  # 50 < 70 and 999 > 60

    def test_enrich_client_data_empty_dict(self, service):
        """Test enrichment with completely empty client data."""
        # Arrange
        client_data = {}

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert result["segment"] == "LOW_VALUE"
        assert result["risk_level"] == "MEDIUM_RISK"  # Default 999 days > 60

    def test_enrich_client_data_preserves_existing_fields(self, service):
        """Test that existing fields in client_data are preserved."""
        # Arrange
        client_data = {
            "client_id": "client_999",
            "name": "John Doe",
            "email": "john@example.com",
            "ltv_score": 65.0,
            "days_since_last_interaction": 10,
            "other_field": "value",
        }

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert result["client_id"] == "client_999"
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["other_field"] == "value"
        assert result["segment"] == "HIGH_VALUE"
        assert result["risk_level"] == "LOW_RISK"

    def test_enrich_client_data_mutates_original_dict(self, service):
        """Test that enrich_client_data mutates the original dictionary."""
        # Arrange
        client_data = {
            "ltv_score": 80.0,
            "days_since_last_interaction": 5,
        }
        original_id = id(client_data)

        # Act
        result = service.enrich_client_data(client_data)

        # Assert
        assert id(result) == original_id  # Same object
        assert client_data["segment"] == "VIP"  # Original is mutated
        assert client_data["risk_level"] == "LOW_RISK"

    # ========================================================================
    # should_nurture() tests
    # ========================================================================

    def test_should_nurture_vip_inactive_14_days_returns_true(self, service):
        """Test that VIP inactive for 15+ days should be nurtured."""
        # Arrange
        client_data = {
            "segment": "VIP",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 15,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_should_nurture_vip_inactive_at_threshold(self, service):
        """Test VIP at exactly 15 days (threshold + 1)."""
        # Arrange: VIP_INACTIVE_DAYS is 14, so > 14 means >= 15
        client_data = {
            "segment": "VIP",
            "days_since_last_interaction": VIP_INACTIVE_DAYS + 1,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_should_nurture_vip_active_14_days_returns_false(self, service):
        """Test that VIP with 14 days inactivity (at threshold) should not be nurtured."""
        # Arrange
        client_data = {
            "segment": "VIP",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": VIP_INACTIVE_DAYS,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # First condition fails (not > 14), checks other conditions
        # No risk_level == "HIGH_RISK", and days not > 60
        assert should_nurture is False
        assert reason == ""

    def test_should_nurture_high_risk_returns_true(self, service):
        """Test that HIGH_RISK clients should be nurtured."""
        # Arrange
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "HIGH_RISK",
            "days_since_last_interaction": 35,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "High-value client at risk of churn"

    def test_should_nurture_high_risk_vip_returns_true(self, service):
        """Test that VIP with HIGH_RISK should be nurtured via risk check."""
        # Arrange: VIP inactive < 14 days but HIGH_RISK (should catch on second condition)
        client_data = {
            "segment": "VIP",
            "risk_level": "HIGH_RISK",
            "days_since_last_interaction": 10,  # Not > 14
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "High-value client at risk of churn"

    def test_should_nurture_high_value_inactive_60_days_returns_true(self, service):
        """Test that HIGH_VALUE client inactive for 60+ days should be nurtured."""
        # Arrange
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "MEDIUM_RISK",
            "days_since_last_interaction": 65,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "High-value client inactive for 60+ days"

    def test_should_nurture_vip_inactive_60_days_returns_true(self, service):
        """Test that VIP inactive for 60+ days should be nurtured."""
        # Arrange: VIP with > 60 days inactivity (catches third condition)
        client_data = {
            "segment": "VIP",
            "risk_level": "HIGH_RISK",  # Would catch on second, but testing third
            "days_since_last_interaction": 70,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # VIP with > 14 days triggers first condition, not the HIGH_RISK check
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_should_nurture_vip_inactive_60_days_no_high_risk(self, service):
        """Test VIP inactive 60+ days but not HIGH_RISK triggers third condition."""
        # Arrange: VIP, not > 14 days for first check, not HIGH_RISK, but > 60 days
        client_data = {
            "segment": "VIP",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 65,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # First condition: VIP and days > 14 -> True, triggers first
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_should_nurture_high_value_at_60_days_threshold(self, service):
        """Test HIGH_VALUE at exactly 61 days (threshold + 1)."""
        # Arrange
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "MEDIUM_RISK",
            "days_since_last_interaction": HIGH_VALUE_INACTIVE_DAYS + 1,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "High-value client inactive for 60+ days"

    def test_should_nurture_medium_value_returns_false(self, service):
        """Test that MEDIUM_VALUE clients are not nurtured."""
        # Arrange
        client_data = {
            "segment": "MEDIUM_VALUE",
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 70,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is False
        assert reason == ""

    def test_should_nurture_low_value_returns_false(self, service):
        """Test that LOW_VALUE clients are not nurtured."""
        # Arrange
        client_data = {
            "segment": "LOW_VALUE",
            "risk_level": "MEDIUM_RISK",
            "days_since_last_interaction": 100,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is False
        assert reason == ""

    def test_should_nurture_missing_segment_returns_false(self, service):
        """Test that missing segment field defaults to empty string and returns False."""
        # Arrange
        client_data = {
            "risk_level": "LOW_RISK",
            "days_since_last_interaction": 20,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is False
        assert reason == ""

    def test_should_nurture_missing_risk_level_returns_false_unless_vip(self, service):
        """Test that missing risk_level defaults to empty string."""
        # Arrange: VIP with > 14 days, but missing risk_level
        client_data = {
            "segment": "VIP",
            "days_since_last_interaction": 20,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # First condition: VIP and days > 14 -> True
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_should_nurture_missing_days_defaults_to_999(self, service):
        """Test that missing days_since_last_interaction defaults to 999."""
        # Arrange: HIGH_VALUE with no days_since_last_interaction
        client_data = {
            "segment": "HIGH_VALUE",
            "risk_level": "LOW_RISK",
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # 999 > 60, so third condition triggers
        assert should_nurture is True
        assert reason == "High-value client inactive for 60+ days"

    def test_should_nurture_empty_dict_returns_false(self, service):
        """Test that completely empty client_data returns False."""
        # Arrange
        client_data = {}

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # segment = "", risk_level = "", days = 999
        # None of the conditions match empty segment
        assert should_nurture is False
        assert reason == ""

    def test_should_nurture_medium_value_high_risk_returns_true(self, service):
        """Test that MEDIUM_VALUE with HIGH_RISK should be nurtured."""
        # Arrange: Testing that risk_level check works for non-VIP/HIGH_VALUE
        client_data = {
            "segment": "MEDIUM_VALUE",
            "risk_level": "HIGH_RISK",
            "days_since_last_interaction": 35,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        assert should_nurture is True
        assert reason == "High-value client at risk of churn"

    def test_should_nurture_priority_order_vip_14_days_over_risk(self, service):
        """Test that VIP 14+ days condition is checked before HIGH_RISK."""
        # Arrange: VIP with both conditions true
        client_data = {
            "segment": "VIP",
            "risk_level": "HIGH_RISK",
            "days_since_last_interaction": 20,
        }

        # Act
        should_nurture, reason = service.should_nurture(client_data)

        # Assert
        # First condition should match first
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"


class TestClientSegmentationConstants:
    """Test that module constants have expected values."""

    def test_vip_ltv_threshold(self):
        """Test VIP_LTV_THRESHOLD constant."""
        assert VIP_LTV_THRESHOLD == 80

    def test_high_value_ltv_threshold(self):
        """Test HIGH_VALUE_LTV_THRESHOLD constant."""
        assert HIGH_VALUE_LTV_THRESHOLD == 60

    def test_medium_value_ltv_threshold(self):
        """Test MEDIUM_VALUE_LTV_THRESHOLD constant."""
        assert MEDIUM_VALUE_LTV_THRESHOLD == 40

    def test_high_risk_ltv_threshold(self):
        """Test HIGH_RISK_LTV_THRESHOLD constant."""
        assert HIGH_RISK_LTV_THRESHOLD == 70

    def test_high_risk_inactive_days(self):
        """Test HIGH_RISK_INACTIVE_DAYS constant."""
        assert HIGH_RISK_INACTIVE_DAYS == 30

    def test_vip_inactive_days(self):
        """Test VIP_INACTIVE_DAYS constant."""
        assert VIP_INACTIVE_DAYS == 14

    def test_high_value_inactive_days(self):
        """Test HIGH_VALUE_INACTIVE_DAYS constant."""
        assert HIGH_VALUE_INACTIVE_DAYS == 60


class TestClientSegmentationIntegration:
    """Integration tests combining multiple methods."""

    @pytest.fixture
    def service(self):
        """Create a ClientSegmentationService instance for testing."""
        return ClientSegmentationService()

    def test_full_workflow_vip_nurture_pipeline(self, service):
        """Test complete workflow: score -> enrich -> nurture decision."""
        # Arrange: Simulate raw client data from scoring service
        raw_client_data = {
            "client_id": "vip_001",
            "name": "Alice Johnson",
            "ltv_score": 95.0,
            "days_since_last_interaction": 20,
        }

        # Act: Enrich the data
        enriched_data = service.enrich_client_data(raw_client_data)

        # Assert: Check enrichment
        assert enriched_data["segment"] == "VIP"
        # HIGH_RISK requires LTV >= 70 AND days > 30, so 20 days = LOW_RISK
        assert enriched_data["risk_level"] == "LOW_RISK"

        # Act: Check nurture decision
        should_nurture, reason = service.should_nurture(enriched_data)

        # Assert: VIP with 20 days inactivity should be nurtured
        assert should_nurture is True
        assert reason == "VIP inactive for 14+ days"

    def test_full_workflow_high_value_no_nurture(self, service):
        """Test complete workflow for HIGH_VALUE client that doesn't need nurturing."""
        # Arrange
        raw_client_data = {
            "client_id": "hv_002",
            "ltv_score": 70.0,
            "days_since_last_interaction": 25,
        }

        # Act
        enriched_data = service.enrich_client_data(raw_client_data)
        should_nurture, reason = service.should_nurture(enriched_data)

        # Assert
        assert enriched_data["segment"] == "HIGH_VALUE"
        assert enriched_data["risk_level"] == "LOW_RISK"
        assert should_nurture is False
        assert reason == ""

    def test_full_workflow_low_value_no_nurture(self, service):
        """Test that LOW_VALUE clients are never nurtured."""
        # Arrange
        raw_client_data = {
            "client_id": "lv_003",
            "ltv_score": 20.0,
            "days_since_last_interaction": 200,
        }

        # Act
        enriched_data = service.enrich_client_data(raw_client_data)
        should_nurture, reason = service.should_nurture(enriched_data)

        # Assert
        assert enriched_data["segment"] == "LOW_VALUE"
        assert enriched_data["risk_level"] == "MEDIUM_RISK"
        assert should_nurture is False
        assert reason == ""

    def test_multiple_clients_batch_processing(self, service):
        """Test processing multiple clients in batch."""
        # Arrange
        clients = [
            {"client_id": "c1", "ltv_score": 90.0, "days_since_last_interaction": 5},
            {"client_id": "c2", "ltv_score": 75.0, "days_since_last_interaction": 40},
            {"client_id": "c3", "ltv_score": 50.0, "days_since_last_interaction": 70},
            {"client_id": "c4", "ltv_score": 30.0, "days_since_last_interaction": 10},
        ]

        # Act
        enriched_clients = [service.enrich_client_data(c) for c in clients]
        nurture_decisions = [service.should_nurture(c) for c in enriched_clients]

        # Assert
        assert enriched_clients[0]["segment"] == "VIP"
        assert enriched_clients[0]["risk_level"] == "LOW_RISK"
        assert nurture_decisions[0] == (False, "")

        assert enriched_clients[1]["segment"] == "HIGH_VALUE"
        assert enriched_clients[1]["risk_level"] == "HIGH_RISK"
        assert nurture_decisions[1] == (True, "High-value client at risk of churn")

        assert enriched_clients[2]["segment"] == "MEDIUM_VALUE"
        assert enriched_clients[2]["risk_level"] == "MEDIUM_RISK"
        assert nurture_decisions[2] == (False, "")

        assert enriched_clients[3]["segment"] == "LOW_VALUE"
        assert enriched_clients[3]["risk_level"] == "LOW_RISK"
        assert nurture_decisions[3] == (False, "")
