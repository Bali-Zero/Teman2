"""
Tests for severity_calculator.py - Alert severity calculation based on deadlines.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.compliance.severity_calculator import (
    AlertSeverity,
    SeverityCalculatorService,
)


@pytest.fixture
def calculator():
    return SeverityCalculatorService()


def _future_date(days: int) -> str:
    """Create ISO date string N days from now."""
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def _past_date(days: int) -> str:
    """Create ISO date string N days ago."""
    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


class TestCalculateSeverity:
    """Tests for calculate_severity method."""

    def test_overdue_returns_critical(self, calculator):
        severity, days = calculator.calculate_severity(_past_date(5))
        assert severity == AlertSeverity.CRITICAL
        assert days < 0

    def test_within_7_days_returns_urgent(self, calculator):
        severity, days = calculator.calculate_severity(_future_date(3))
        assert severity == AlertSeverity.URGENT
        assert 0 <= days <= 7

    def test_within_30_days_returns_warning(self, calculator):
        severity, days = calculator.calculate_severity(_future_date(15))
        assert severity == AlertSeverity.WARNING
        assert 7 < days <= 30

    def test_beyond_60_days_returns_info(self, calculator):
        severity, days = calculator.calculate_severity(_future_date(90))
        assert severity == AlertSeverity.INFO
        assert days > 60

    def test_exactly_7_days_is_urgent(self, calculator):
        severity, _ = calculator.calculate_severity(_future_date(7))
        assert severity == AlertSeverity.URGENT

    def test_exactly_30_days_is_warning(self, calculator):
        severity, _ = calculator.calculate_severity(_future_date(30))
        assert severity == AlertSeverity.WARNING

    def test_boundary_31_days(self, calculator):
        severity, _ = calculator.calculate_severity(_future_date(31))
        # 31 days is still within WARNING threshold (<=30), but due to time-of-day
        # could be 30 or 31. Check it's WARNING or INFO.
        assert severity in (AlertSeverity.WARNING, AlertSeverity.INFO)

    def test_today_deadline_is_urgent_or_critical(self, calculator):
        # Today could be 0 days (urgent) or -0 depending on time
        severity, days = calculator.calculate_severity(
            datetime.now(tz=timezone.utc).isoformat()
        )
        assert severity in (AlertSeverity.URGENT, AlertSeverity.CRITICAL)

    def test_handles_iso_format(self, calculator):
        # Use standard ISO format without Z suffix (which the source handles via .replace)
        date_str = (datetime.now(tz=timezone.utc) + timedelta(days=3)).isoformat()
        severity, _ = calculator.calculate_severity(date_str)
        assert severity == AlertSeverity.URGENT


class TestGetDaysUntilDeadline:
    """Tests for get_days_until_deadline method."""

    def test_future_deadline_positive(self, calculator):
        days = calculator.get_days_until_deadline(_future_date(10))
        assert days >= 9  # Could be 9 or 10 depending on time

    def test_past_deadline_negative(self, calculator):
        days = calculator.get_days_until_deadline(_past_date(5))
        assert days < 0

    def test_today_near_zero(self, calculator):
        days = calculator.get_days_until_deadline(
            datetime.now(tz=timezone.utc).isoformat()
        )
        assert -1 <= days <= 0


class TestAlertSeverityEnum:
    """Tests for AlertSeverity enum values."""

    def test_severity_values(self):
        assert AlertSeverity.INFO == "info"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.URGENT == "urgent"
        assert AlertSeverity.CRITICAL == "critical"

    def test_severity_ordering(self):
        """Verify severity levels make semantic sense."""
        thresholds = SeverityCalculatorService.ALERT_THRESHOLDS
        assert thresholds[AlertSeverity.INFO] > thresholds[AlertSeverity.WARNING]
        assert thresholds[AlertSeverity.WARNING] > thresholds[AlertSeverity.URGENT]
        assert thresholds[AlertSeverity.URGENT] > thresholds[AlertSeverity.CRITICAL]
