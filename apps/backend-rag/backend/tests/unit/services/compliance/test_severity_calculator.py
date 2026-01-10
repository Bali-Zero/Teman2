"""
Unit tests for SeverityCalculatorService
Target: >95% coverage
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.compliance.severity_calculator import AlertSeverity, SeverityCalculatorService


class TestSeverityCalculatorService:
    """Tests for SeverityCalculatorService"""

    def test_init(self):
        """Test initialization"""
        calculator = SeverityCalculatorService()
        assert calculator.ALERT_THRESHOLDS is not None
        assert AlertSeverity.CRITICAL in calculator.ALERT_THRESHOLDS

    def test_calculate_severity_critical_overdue(self):
        """Test calculating severity for overdue deadline"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() - timedelta(days=5)).isoformat()

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.CRITICAL
        assert days < 0

    def test_calculate_severity_critical_0_days(self):
        """Test calculating severity for deadline today"""
        calculator = SeverityCalculatorService()
        deadline = datetime.now().isoformat()

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.CRITICAL
        assert days <= 0

    def test_calculate_severity_urgent(self):
        """Test calculating severity for urgent deadline (1-7 days)"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() + timedelta(days=5)).isoformat()

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.URGENT
        assert 0 < days <= 7

    def test_calculate_severity_warning(self):
        """Test calculating severity for warning deadline (8-30 days)"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() + timedelta(days=20)).isoformat()

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.WARNING
        assert 7 < days <= 30

    def test_calculate_severity_info(self):
        """Test calculating severity for info deadline (>60 days)"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() + timedelta(days=90)).isoformat()

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.INFO
        assert days > 60

    def test_calculate_severity_with_z_suffix(self):
        """Test calculating severity with Z suffix in ISO format"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() + timedelta(days=5)).isoformat() + "Z"

        severity, days = calculator.calculate_severity(deadline)
        assert severity == AlertSeverity.URGENT

    def test_get_days_until_deadline_future(self):
        """Test getting days until future deadline"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() + timedelta(days=10)).isoformat()

        days = calculator.get_days_until_deadline(deadline)
        assert 9 <= days <= 10  # Allow small timing variance

    def test_get_days_until_deadline_past(self):
        """Test getting days until past deadline"""
        calculator = SeverityCalculatorService()
        deadline = (datetime.now() - timedelta(days=5)).isoformat()

        days = calculator.get_days_until_deadline(deadline)
        assert days < 0  # Should be negative (overdue)
        assert days <= -4  # Allow some tolerance

    def test_get_days_until_deadline_today(self):
        """Test getting days until deadline today"""
        calculator = SeverityCalculatorService()
        deadline = datetime.now().isoformat()

        days = calculator.get_days_until_deadline(deadline)
        assert days <= 0  # Today or slightly past due to timing
