"""
Unit tests for AlertGeneratorService
Target: >95% coverage
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.compliance.alert_generator import AlertGeneratorService, AlertStatus
from backend.services.compliance.compliance_tracker import ComplianceItem
from backend.services.compliance.severity_calculator import AlertSeverity


@pytest.fixture
def sample_compliance_item():
    """Sample compliance item for testing"""
    return ComplianceItem(
        item_id="item_123",
        client_id="client_456",
        compliance_type="visa_expiry",
        title="KITAS Renewal",
        description="KITAS renewal for client",
        deadline=(datetime.now() + timedelta(days=5)).isoformat(),
        requirement_details="Renew KITAS before expiry",
        required_documents=["passport", "sponsor_letter"],
        estimated_cost=15000000,
    )


class TestAlertGeneratorService:
    """Tests for AlertGeneratorService"""

    def test_init(self):
        """Test initialization"""
        generator = AlertGeneratorService()
        assert generator.alerts == {}
        assert generator.generator_stats["alerts_generated"] == 0

    def test_generate_alert_critical(self, sample_compliance_item):
        """Test generating critical alert"""
        generator = AlertGeneratorService()
        deadline = (datetime.now() - timedelta(days=1)).isoformat()
        sample_compliance_item.deadline = deadline

        alert = generator.generate_alert(sample_compliance_item, AlertSeverity.CRITICAL, -1)

        assert alert.severity == AlertSeverity.CRITICAL
        assert "OVERDUE" in alert.message
        assert alert.status == AlertStatus.PENDING
        assert alert.estimated_cost == 15000000

    def test_generate_alert_urgent(self, sample_compliance_item):
        """Test generating urgent alert"""
        generator = AlertGeneratorService()

        alert = generator.generate_alert(sample_compliance_item, AlertSeverity.URGENT, 5)

        assert alert.severity == AlertSeverity.URGENT
        assert "URGENT" in alert.message
        assert "5 days" in alert.message

    def test_generate_alert_warning(self, sample_compliance_item):
        """Test generating warning alert"""
        generator = AlertGeneratorService()

        alert = generator.generate_alert(sample_compliance_item, AlertSeverity.WARNING, 20)

        assert alert.severity == AlertSeverity.WARNING
        assert "REMINDER" in alert.message
        assert "20 days" in alert.message

    def test_generate_alert_info(self, sample_compliance_item):
        """Test generating info alert"""
        generator = AlertGeneratorService()

        alert = generator.generate_alert(sample_compliance_item, AlertSeverity.INFO, 90)

        assert alert.severity == AlertSeverity.INFO
        assert "UPCOMING" in alert.message
        assert "90 days" in alert.message

    def test_generate_alert_with_documents(self, sample_compliance_item):
        """Test generating alert with required documents"""
        generator = AlertGeneratorService()

        alert = generator.generate_alert(sample_compliance_item, AlertSeverity.URGENT, 5)

        assert "Required documents" in alert.message
        assert "passport" in alert.message

    def test_generate_alert_without_cost(self):
        """Test generating alert without estimated cost"""
        generator = AlertGeneratorService()
        item = ComplianceItem(
            item_id="item_123",
            client_id="client_456",
            compliance_type="visa_expiry",
            title="Test Item",
            description="Test description",
            deadline=(datetime.now() + timedelta(days=5)).isoformat(),
            requirement_details="Test requirement details",
        )

        alert = generator.generate_alert(item, AlertSeverity.URGENT, 5)

        assert alert.estimated_cost is None
        assert "Estimated cost" not in alert.message

    def test_generate_alert_creates_unique_id(self, sample_compliance_item):
        """Test that each alert gets unique ID"""
        import time

        generator = AlertGeneratorService()

        alert1 = generator.generate_alert(sample_compliance_item, AlertSeverity.URGENT, 5)

        time.sleep(1.1)  # Wait more than 1 second to ensure different timestamp

        alert2 = generator.generate_alert(sample_compliance_item, AlertSeverity.URGENT, 5)

        assert alert1.alert_id != alert2.alert_id
        assert len(generator.alerts) == 2
        assert alert1.alert_id in generator.alerts
        assert alert2.alert_id in generator.alerts
