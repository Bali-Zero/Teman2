"""
Test ExpiryChecker logic.
"""

from datetime import datetime, timedelta

import pytest

from backend.app.modules.notifications.checker import ExpiryChecker
from backend.app.modules.notifications.models import AlertType, ClientInfo


class TestPassportAlerts:
    """Test passport expiry alert detection."""

    @pytest.fixture
    def checker(self) -> ExpiryChecker:
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self) -> ClientInfo:
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
        )

    def test_passport_expired(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Alert when passport is already expired."""
        client = base_client.model_copy()
        client.passport_expiry = datetime.now() - timedelta(days=30)

        alert = checker._check_passport(client)

        assert alert is not None
        assert alert.alert_type == AlertType.PASSPORT_EXPIRED

    def test_passport_critical_9_months(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Critical alert when passport expires within 9 months."""
        client = base_client.model_copy()
        client.passport_expiry = datetime.now() + timedelta(days=240)  # ~8 months

        alert = checker._check_passport(client)

        assert alert is not None
        assert alert.alert_type == AlertType.PASSPORT_CRITICAL

    def test_passport_warning_13_months(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Warning alert when passport expires within 13 months."""
        client = base_client.model_copy()
        client.passport_expiry = datetime.now() + timedelta(days=365)  # ~12 months

        alert = checker._check_passport(client)

        assert alert is not None
        assert alert.alert_type == AlertType.PASSPORT_WARNING

    def test_passport_no_alert_valid(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when passport is valid for more than 13 months."""
        client = base_client.model_copy()
        client.passport_expiry = datetime.now() + timedelta(days=500)  # ~16 months

        alert = checker._check_passport(client)

        assert alert is None

    def test_passport_no_date(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when passport expiry date is not set."""
        client = base_client.model_copy()
        client.passport_expiry = None

        alert = checker._check_passport(client)

        assert alert is None

    def test_passport_boundary_exactly_9_months(
        self, checker: ExpiryChecker, base_client: ClientInfo
    ):
        """Exactly 9 months: should be CRITICAL (boundary)."""
        client = base_client.model_copy()
        today = checker.today
        # Set expiry exactly 9 months from today
        target_month = today.month + 9
        target_year = today.year + (target_month - 1) // 12
        target_month = (target_month - 1) % 12 + 1
        client.passport_expiry = today.replace(year=target_year, month=target_month)

        alert = checker._check_passport(client)

        assert alert is not None
        assert alert.alert_type == AlertType.PASSPORT_CRITICAL

    def test_passport_boundary_exactly_13_months(
        self, checker: ExpiryChecker, base_client: ClientInfo
    ):
        """Exactly 13 months: should be WARNING (boundary)."""
        client = base_client.model_copy()
        today = checker.today
        target_month = today.month + 13
        target_year = today.year + (target_month - 1) // 12
        target_month = (target_month - 1) % 12 + 1
        client.passport_expiry = today.replace(year=target_year, month=target_month)

        alert = checker._check_passport(client)

        assert alert is not None
        assert alert.alert_type == AlertType.PASSPORT_WARNING


class TestVisaAlerts:
    """Test visa expiry alert detection."""

    @pytest.fixture
    def checker(self) -> ExpiryChecker:
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self) -> ClientInfo:
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
            visa_type="KITAS",
        )

    def test_visa_expired(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Alert when visa is already expired."""
        client = base_client.model_copy()
        client.visa_expiry = datetime.now() - timedelta(days=10)

        alert = checker._check_visa(client)

        assert alert is not None
        assert alert.alert_type == AlertType.VISA_EXPIRED

    def test_visa_critical_2_months(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Critical alert when visa expires within 60 days."""
        client = base_client.model_copy()
        client.visa_expiry = datetime.now() + timedelta(days=50)

        alert = checker._check_visa(client)

        assert alert is not None
        assert alert.alert_type == AlertType.VISA_CRITICAL

    def test_visa_warning_4_months(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Warning alert when visa expires within 120 days."""
        client = base_client.model_copy()
        client.visa_expiry = datetime.now() + timedelta(days=100)

        alert = checker._check_visa(client)

        assert alert is not None
        assert alert.alert_type == AlertType.VISA_WARNING

    def test_visa_no_alert_valid(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when visa is valid for more than 120 days."""
        client = base_client.model_copy()
        client.visa_expiry = datetime.now() + timedelta(days=150)

        alert = checker._check_visa(client)

        assert alert is None

    def test_visa_no_date(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when visa expiry date is not set."""
        client = base_client.model_copy()
        client.visa_expiry = None

        alert = checker._check_visa(client)

        assert alert is None

    def test_visa_boundary_exactly_60_days(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Exactly 60 days: should be CRITICAL (boundary)."""
        client = base_client.model_copy()
        client.visa_expiry = checker.today + timedelta(days=60)

        alert = checker._check_visa(client)

        assert alert is not None
        assert alert.alert_type == AlertType.VISA_CRITICAL

    def test_visa_boundary_exactly_120_days(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Exactly 120 days: should be WARNING (boundary)."""
        client = base_client.model_copy()
        client.visa_expiry = checker.today + timedelta(days=120)

        alert = checker._check_visa(client)

        assert alert is not None
        assert alert.alert_type == AlertType.VISA_WARNING

    def test_visa_default_visa_type(self, checker: ExpiryChecker, base_client: ClientInfo):
        """When visa_type is None, should use 'Current' as default."""
        client = base_client.model_copy()
        client.visa_type = None
        client.visa_expiry = datetime.now() + timedelta(days=50)

        alert = checker._check_visa(client)

        assert alert is not None
        assert "Current" in alert.email_body


class TestBirthdayAlerts:
    """Test birthday alert detection."""

    @pytest.fixture
    def checker(self) -> ExpiryChecker:
        return ExpiryChecker()

    @pytest.fixture
    def base_client(self) -> ClientInfo:
        return ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Test User",
            preferred_language="en",
        )

    def test_birthday_today(self, checker: ExpiryChecker, base_client: ClientInfo):
        """Alert when today is client's birthday."""
        client = base_client.model_copy()
        # Use the same today as checker (UTC-based) to avoid timezone mismatch
        today = checker.today
        client.date_of_birth = today.replace(year=today.year - 30)

        alert = checker._check_birthday(client)

        assert alert is not None
        assert alert.alert_type == AlertType.BIRTHDAY
        assert "Happy Birthday" in alert.email_subject or "Selamat" in alert.email_subject

    def test_birthday_not_today(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when today is not client's birthday."""
        client = base_client.model_copy()
        today = datetime.now()
        client.date_of_birth = today.replace(year=today.year - 30, month=today.month % 12 + 1)

        alert = checker._check_birthday(client)

        assert alert is None

    def test_birthday_no_date(self, checker: ExpiryChecker, base_client: ClientInfo):
        """No alert when date of birth is not set."""
        client = base_client.model_copy()
        client.date_of_birth = None

        alert = checker._check_birthday(client)

        assert alert is None


class TestExpiryCheckerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def checker(self) -> ExpiryChecker:
        return ExpiryChecker()

    def test_multiple_alerts_same_client(self, checker: ExpiryChecker):
        """Client can have multiple alerts (passport + visa + birthday)."""
        # Use checker.today (UTC-based) to avoid timezone mismatch
        today = checker.today
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

    def test_months_between_calculation(self, checker: ExpiryChecker):
        """Test months calculation is accurate."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 9, 15)

        months = checker._months_between(start, end)

        assert months == 8

    def test_months_between_partial_month(self, checker: ExpiryChecker):
        """Test partial months are handled correctly."""
        start = datetime(2024, 1, 15)
        end = datetime(2024, 9, 10)  # Less than full month

        months = checker._months_between(start, end)

        assert months == 7  # Should round down

    def test_months_between_negative_returns_zero(self, checker: ExpiryChecker):
        """Negative months (past date) should return 0."""
        start = datetime(2024, 9, 15)
        end = datetime(2024, 1, 15)  # Before start

        months = checker._months_between(start, end)

        assert months == 0

    def test_check_all_clients(self, checker: ExpiryChecker):
        """check_all_clients processes a list of clients."""
        today = datetime.now()
        clients = [
            ClientInfo(
                id=1,
                email="test1@example.com",
                full_name="User 1",
                passport_expiry=today + timedelta(days=240),
            ),
            ClientInfo(
                id=2,
                email="test2@example.com",
                full_name="User 2",
                passport_expiry=today + timedelta(days=500),  # No alert
            ),
        ]

        alerts = checker.check_all_clients(clients)

        assert len(alerts) == 1
        assert alerts[0].client_id == 1

    def test_language_routing_italian(self, checker: ExpiryChecker):
        """Italian client gets Italian template."""
        client = ClientInfo(
            id=1,
            email="test@example.com",
            full_name="Marco Rossi",
            preferred_language="it",
            passport_expiry=datetime.now() + timedelta(days=365),
        )

        alert = checker._check_passport(client)

        assert alert is not None
        assert "Passaporto" in alert.email_subject or "passaporto" in alert.email_body.lower()
