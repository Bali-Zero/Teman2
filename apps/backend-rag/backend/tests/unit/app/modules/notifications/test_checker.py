"""
Test ExpiryChecker logic.
"""

import pytest
from datetime import datetime, timedelta
from backend.app.modules.notifications.checker import ExpiryChecker
from backend.app.modules.notifications.models import AlertType, ClientInfo


class TestPassportAlerts:
    """Test passport expiry alert detection."""

    @pytest.fixture
    def checker(self):
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self):
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
        )

    def test_passport_expired(self, checker, base_client):
        """Alert when passport is already expired."""
        client = base_client.copy()
        client.passport_expiry = datetime.now() - timedelta(days=30)
        
        alerts = checker._check_passport(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.PASSPORT_EXPIRED

    def test_passport_critical_9_months(self, checker, base_client):
        """Critical alert when passport expires in 9 months."""
        client = base_client.copy()
        client.passport_expiry = datetime.now() + timedelta(days=240)  # ~8 months
        
        alerts = checker._check_passport(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.PASSPORT_CRITICAL

    def test_passport_warning_13_months(self, checker, base_client):
        """Warning alert when passport expires in 13 months."""
        client = base_client.copy()
        client.passport_expiry = datetime.now() + timedelta(days=365)  # ~12 months
        
        alerts = checker._check_passport(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.PASSPORT_WARNING

    def test_passport_no_alert_valid(self, checker, base_client):
        """No alert when passport is valid for more than 13 months."""
        client = base_client.copy()
        client.passport_expiry = datetime.now() + timedelta(days=500)  # ~16 months
        
        alerts = checker._check_passport(client)
        
        assert len(alerts) == 0

    def test_passport_no_date(self, checker, base_client):
        """No alert when passport expiry date is not set."""
        client = base_client.copy()
        client.passport_expiry = None
        
        alerts = checker._check_passport(client)
        
        assert len(alerts) == 0


class TestVisaAlerts:
    """Test visa expiry alert detection."""

    @pytest.fixture
    def checker(self):
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self):
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
            visa_type="KITAS",
        )

    def test_visa_expired(self, checker, base_client):
        """Alert when visa is already expired."""
        client = base_client.copy()
        client.visa_expiry = datetime.now() - timedelta(days=10)
        
        alerts = checker._check_visa(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.VISA_EXPIRED

    def test_visa_critical_2_months(self, checker, base_client):
        """Critical alert when visa expires in 2 months."""
        client = base_client.copy()
        client.visa_expiry = datetime.now() + timedelta(days=50)  # ~1.6 months
        
        alerts = checker._check_visa(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.VISA_CRITICAL

    def test_visa_warning_4_months(self, checker, base_client):
        """Warning alert when visa expires in 4 months."""
        client = base_client.copy()
        client.visa_expiry = datetime.now() + timedelta(days=100)  # ~3.3 months
        
        alerts = checker._check_visa(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.VISA_WARNING

    def test_visa_no_alert_valid(self, checker, base_client):
        """No alert when visa is valid for more than 4 months."""
        client = base_client.copy()
        client.visa_expiry = datetime.now() + timedelta(days=150)  # ~5 months
        
        alerts = checker._check_visa(client)
        
        assert len(alerts) == 0


class TestBirthdayAlerts:
    """Test birthday alert detection."""

    @pytest.fixture
    def checker(self):
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self):
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
        )

    def test_birthday_today(self, checker, base_client):
        """Alert when today is client's birthday."""
        client = base_client.copy()
        today = datetime.now()
        client.date_of_birth = today.replace(year=today.year - 30)
        
        alerts = checker._check_birthday(client)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.BIRTHDAY
        assert "Happy Birthday" in alerts[0].email_subject

    def test_birthday_not_today(self, checker, base_client):
        """No alert when today is not client's birthday."""
        client = base_client.copy()
        today = datetime.now()
        client.date_of_birth = today.replace(year=today.year - 30, month=today.month % 12 + 1)
        
        alerts = checker._check_birthday(client)
        
        assert len(alerts) == 0

    def test_birthday_no_date(self, checker, base_client):
        """No alert when date of birth is not set."""
        client = base_client.copy()
        client.date_of_birth = None
        
        alerts = checker._check_birthday(client)
        
        assert len(alerts) == 0


class TestExpiryCheckerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def checker(self):
        return ExpiryChecker()

    def test_multiple_alerts_same_client(self, checker):
        """Client can have multiple alerts (passport + visa + birthday)."""
        today = datetime.now()
        client = ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
            passport_expiry=today + timedelta(days=240),  # Critical
            visa_expiry=today + timedelta(days=50),  # Critical
            date_of_birth=today.replace(year=today.year - 30),  # Birthday
            visa_type="KITAS",
        )
        
        alerts = checker.check_client(client)
        
        assert len(alerts) == 3
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.PASSPORT_CRITICAL in alert_types
        assert AlertType.VISA_CRITICAL in alert_types
        assert AlertType.BIRTHDAY in alert_types

    def test_months_between_calculation(self, checker):
        """Test months calculation is accurate."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 9, 15)
        
        months = checker._months_between(start, end)
        
        assert months == 8

    def test_months_between_partial_month(self, checker):
        """Test partial months are handled correctly."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 9, 10)  # Less than full month
        
        months = checker._months_between(start, end)
        
        assert months == 7  # Should round down
