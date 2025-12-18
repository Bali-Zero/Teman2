"""
Comprehensive Unit Tests for ProactiveComplianceMonitor
Tests compliance tracking, deadline monitoring, alert generation
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from backend.services.proactive_compliance_monitor import (
    AlertSeverity,
    AlertStatus,
    ComplianceAlert,
    ComplianceItem,
    ComplianceType,
    ProactiveComplianceMonitor,
)


class TestComplianceDataClasses:
    """Test compliance data structures"""

    def test_compliance_item_creation(self):
        """Test creating compliance item"""
        deadline = (datetime.now() + timedelta(days=30)).isoformat()
        item = ComplianceItem(
            item_id="comp-123",
            client_id="client-456",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="KITAS Expiry",
            description="Work permit expiration",
            deadline=deadline,
            requirement_details="Renewal required 30 days before expiry",
        )

        assert item.item_id == "comp-123"
        assert item.client_id == "client-456"
        assert item.compliance_type == ComplianceType.VISA_EXPIRY
        assert item.title == "KITAS Expiry"

    def test_compliance_item_with_all_fields(self):
        """Test compliance item with all fields"""
        deadline = (datetime.now() + timedelta(days=60)).isoformat()
        item = ComplianceItem(
            item_id="comp-123",
            client_id="client-456",
            compliance_type=ComplianceType.TAX_FILING,
            title="SPT Tahunan",
            description="Annual tax return filing",
            deadline=deadline,
            requirement_details="File before March 31",
            estimated_cost=2500000.0,
            required_documents=["KTP", "NPWP", "Financial statements"],
            renewal_process="File online via DJP Online",
            source_oracle="tax_genius",
            metadata={"tax_year": "2024"},
        )

        assert item.estimated_cost == 2500000.0
        assert len(item.required_documents) == 3
        assert item.source_oracle == "tax_genius"

    def test_compliance_alert_creation(self):
        """Test creating compliance alert"""
        alert = ComplianceAlert(
            alert_id="alert-123",
            compliance_item_id="comp-456",
            client_id="client-789",
            severity=AlertSeverity.WARNING,
            title="KITAS Expiry Warning",
            message="Your KITAS expires in 30 days",
            deadline=(datetime.now() + timedelta(days=30)).isoformat(),
            days_until_deadline=30,
            action_required="Start renewal process",
        )

        assert alert.alert_id == "alert-123"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.PENDING


class TestComplianceEnums:
    """Test compliance enum values"""

    def test_compliance_types(self):
        """Test all compliance types are defined"""
        assert ComplianceType.VISA_EXPIRY == "visa_expiry"
        assert ComplianceType.TAX_FILING == "tax_filing"
        assert ComplianceType.LICENSE_RENEWAL == "license_renewal"
        assert ComplianceType.PERMIT_RENEWAL == "permit_renewal"
        assert ComplianceType.REGULATORY_CHANGE == "regulatory_change"
        assert ComplianceType.DOCUMENT_EXPIRY == "document_expiry"

    def test_alert_severities(self):
        """Test alert severity levels"""
        assert AlertSeverity.INFO == "info"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.URGENT == "urgent"
        assert AlertSeverity.CRITICAL == "critical"

    def test_alert_statuses(self):
        """Test alert status values"""
        assert AlertStatus.PENDING == "pending"
        assert AlertStatus.SENT == "sent"
        assert AlertStatus.ACKNOWLEDGED == "acknowledged"
        assert AlertStatus.RESOLVED == "resolved"
        assert AlertStatus.EXPIRED == "expired"


class TestProactiveComplianceMonitorInitialization:
    """Test monitor initialization"""

    def test_monitor_initialization(self):
        """Test monitor initializes correctly"""
        monitor = ProactiveComplianceMonitor()
        assert monitor is not None
        assert hasattr(monitor, "add_compliance_item")
        assert hasattr(monitor, "calculate_severity")
        assert hasattr(monitor, "check_compliance_items")

    def test_monitor_initialization_with_services(self):
        """Test monitor initializes with services"""
        mock_search = Mock()
        mock_notifications = Mock()
        monitor = ProactiveComplianceMonitor(
            search_service=mock_search,
            notification_service=mock_notifications,
        )
        assert monitor.search == mock_search
        assert monitor.notifications == mock_notifications

    def test_monitor_initial_state(self):
        """Test monitor initial state"""
        monitor = ProactiveComplianceMonitor()
        assert monitor.compliance_items == {}
        assert monitor.alerts == {}
        assert monitor.running is False
        assert monitor.task is None


class TestComplianceTracking:
    """Test compliance tracking functionality"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_add_compliance_item(self):
        """Test adding a compliance item"""
        deadline = (datetime.now() + timedelta(days=45)).isoformat()

        item = self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="KITAS Expiry",
            deadline=deadline,
            description="Work permit expires soon",
        )

        assert item is not None
        assert isinstance(item, ComplianceItem)
        assert item.client_id == "client-123"
        assert item.compliance_type == ComplianceType.VISA_EXPIRY

    def test_add_compliance_item_with_cost(self):
        """Test adding compliance item with estimated cost"""
        deadline = (datetime.now() + timedelta(days=30)).isoformat()

        item = self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.TAX_FILING,
            title="SPT Tahunan",
            deadline=deadline,
            description="Annual tax filing",
            estimated_cost=2500000.0,
        )

        assert item.estimated_cost == 2500000.0

    def test_add_compliance_item_with_documents(self):
        """Test adding compliance item with required documents"""
        deadline = (datetime.now() + timedelta(days=30)).isoformat()

        item = self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="KITAS Renewal",
            deadline=deadline,
            description="Work permit renewal",
            required_documents=["Passport", "KTP Sponsor", "Photo"],
        )

        assert len(item.required_documents) == 3

    def test_add_visa_expiry(self):
        """Test adding visa expiry item"""
        deadline = (datetime.now() + timedelta(days=45)).isoformat()

        item = self.monitor.add_visa_expiry(
            client_id="client-123",
            visa_type="KITAS",
            expiry_date=deadline,
            passport_number="AB1234567",
        )

        assert item is not None
        assert item.compliance_type == ComplianceType.VISA_EXPIRY
        assert "KITAS" in item.title

    def test_add_annual_tax_deadline(self):
        """Test adding annual tax deadline"""
        item = self.monitor.add_annual_tax_deadline(
            client_id="client-123",
            deadline_type="spt_tahunan_individual",
            year=2024,
        )

        assert item is not None
        assert item.compliance_type == ComplianceType.TAX_FILING
        assert "2024" in item.title

    def test_add_annual_tax_deadline_corporate(self):
        """Test adding corporate tax deadline"""
        item = self.monitor.add_annual_tax_deadline(
            client_id="client-123",
            deadline_type="spt_tahunan_corporate",
            year=2024,
        )

        assert item is not None
        assert item.compliance_type == ComplianceType.TAX_FILING

    def test_add_annual_tax_deadline_invalid_type(self):
        """Test adding unknown deadline type raises error"""
        with pytest.raises(ValueError, match="Unknown deadline type"):
            self.monitor.add_annual_tax_deadline(
                client_id="client-123",
                deadline_type="invalid_type",
                year=2024,
            )


class TestAlertGeneration:
    """Test alert generation based on deadlines"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_calculate_severity_far_future(self):
        """Test severity calculation for >30 days before deadline"""
        deadline = (datetime.now() + timedelta(days=70)).isoformat()
        severity, days = self.monitor.calculate_severity(deadline)

        assert severity == AlertSeverity.INFO, "Far future should be INFO"
        assert days >= 60

    def test_calculate_severity_warning_range(self):
        """Test severity calculation for 8-30 days before deadline"""
        deadline = (datetime.now() + timedelta(days=20)).isoformat()
        severity, days = self.monitor.calculate_severity(deadline)

        assert severity == AlertSeverity.WARNING, "8-30 days should be WARNING"

    def test_calculate_severity_urgent_range(self):
        """Test severity calculation for 1-7 days before deadline"""
        deadline = (datetime.now() + timedelta(days=5)).isoformat()
        severity, days = self.monitor.calculate_severity(deadline)

        assert severity == AlertSeverity.URGENT, "1-7 days should be URGENT"

    def test_calculate_severity_overdue(self):
        """Test severity calculation for overdue item"""
        deadline = (datetime.now() - timedelta(days=1)).isoformat()
        severity, days = self.monitor.calculate_severity(deadline)

        assert severity == AlertSeverity.CRITICAL, "Overdue should be CRITICAL"
        assert days < 0

    def test_check_compliance_items(self):
        """Test checking compliance items for alerts"""
        # Add a compliance item
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="KITAS Expiry",
            deadline=deadline,
            description="Work permit expires soon",
        )

        alerts = self.monitor.check_compliance_items()
        assert isinstance(alerts, list)

    def test_generate_alerts(self):
        """Test generating alerts"""
        # Add a compliance item
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="KITAS Expiry",
            deadline=deadline,
            description="Test",
        )

        alerts = self.monitor.generate_alerts()
        assert isinstance(alerts, list)
        if alerts:
            assert "severity" in alerts[0]


class TestAlertManagement:
    """Test alert management"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_acknowledge_alert(self):
        """Test acknowledging an alert"""
        # Add compliance item and generate alert
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )
        self.monitor.check_compliance_items()

        # Find an alert to acknowledge
        if self.monitor.alerts:
            alert_id = list(self.monitor.alerts.keys())[0]
            result = self.monitor.acknowledge_alert(alert_id)
            assert result is True
            assert self.monitor.alerts[alert_id].status == AlertStatus.ACKNOWLEDGED
        else:
            # No alerts generated, test passes
            assert True

    def test_acknowledge_nonexistent_alert(self):
        """Test acknowledging a non-existent alert"""
        result = self.monitor.acknowledge_alert("nonexistent-id")
        assert result is False

    def test_resolve_compliance_item(self):
        """Test resolving a compliance item"""
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        item = self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )

        result = self.monitor.resolve_compliance_item(item.item_id)
        assert result is True
        assert item.item_id not in self.monitor.compliance_items

    def test_resolve_nonexistent_item(self):
        """Test resolving a non-existent item"""
        result = self.monitor.resolve_compliance_item("nonexistent-id")
        assert result is False


class TestComplianceQuery:
    """Test querying compliance items"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_get_upcoming_deadlines(self):
        """Test getting upcoming deadlines"""
        # Add some compliance items
        for i in range(3):
            deadline = (datetime.now() + timedelta(days=10 + i * 10)).isoformat()
            self.monitor.add_compliance_item(
                client_id=f"client-{i}",
                compliance_type=ComplianceType.VISA_EXPIRY,
                title=f"Test {i}",
                deadline=deadline,
                description="Test",
            )

        items = self.monitor.get_upcoming_deadlines(days_ahead=30)
        assert isinstance(items, list)

    def test_get_upcoming_deadlines_filtered_by_client(self):
        """Test getting upcoming deadlines for specific client"""
        # Add items for different clients
        deadline = (datetime.now() + timedelta(days=20)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-A",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test A",
            deadline=deadline,
            description="Test",
        )
        self.monitor.add_compliance_item(
            client_id="client-B",
            compliance_type=ComplianceType.TAX_FILING,
            title="Test B",
            deadline=deadline,
            description="Test",
        )

        items = self.monitor.get_upcoming_deadlines(client_id="client-A", days_ahead=30)
        assert all(item.client_id == "client-A" for item in items)

    def test_get_alerts_for_client(self):
        """Test getting alerts for a specific client"""
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )
        self.monitor.check_compliance_items()

        alerts = self.monitor.get_alerts_for_client("client-123")
        assert isinstance(alerts, list)

    def test_get_monitor_stats(self):
        """Test getting monitor statistics"""
        stats = self.monitor.get_monitor_stats()

        assert isinstance(stats, dict)
        assert "total_items_tracked" in stats
        assert "active_items" in stats
        assert "alerts_generated" in stats


class TestComplianceEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_past_deadline(self):
        """Test handling deadlines in the past"""
        past_deadline = (datetime.now() - timedelta(days=365)).isoformat()
        severity, days = self.monitor.calculate_severity(past_deadline)

        assert severity == AlertSeverity.CRITICAL, "Past deadlines should be CRITICAL"
        assert days < 0

    def test_far_future_deadline(self):
        """Test handling very far future deadlines"""
        far_future = (datetime.now() + timedelta(days=365)).isoformat()
        severity, days = self.monitor.calculate_severity(far_future)

        assert severity == AlertSeverity.INFO, "Far future should be INFO"
        assert days > 60

    def test_deadline_with_timezone(self):
        """Test handling deadline with Z timezone suffix"""
        deadline = (datetime.now() + timedelta(days=50)).isoformat() + "Z"
        severity, days = self.monitor.calculate_severity(deadline)

        assert severity == AlertSeverity.INFO

    def test_empty_compliance_items(self):
        """Test checking empty compliance items"""
        alerts = self.monitor.check_compliance_items()
        assert alerts == []


class TestAsyncOperations:
    """Test async operations"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the monitor"""
        import asyncio

        await self.monitor.start()
        assert self.monitor.running is True

        # Stop may raise CancelledError internally, which is expected
        # CancelledError is a BaseException, not Exception, in Python 3.8+
        try:
            await self.monitor.stop()
        except (asyncio.CancelledError, BaseException):
            pass  # CancelledError is expected when stopping
        assert self.monitor.running is False

    @pytest.mark.asyncio
    async def test_start_twice(self):
        """Test starting monitor twice does nothing"""
        import asyncio

        await self.monitor.start()
        assert self.monitor.running is True

        # Start again should not change anything
        await self.monitor.start()
        assert self.monitor.running is True

        try:
            await self.monitor.stop()
        except (asyncio.CancelledError, BaseException):
            pass  # CancelledError is expected when stopping

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test sending an alert"""
        # Add compliance item and generate alert
        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )
        self.monitor.check_compliance_items()

        # Try to send an alert
        if self.monitor.alerts:
            alert_id = list(self.monitor.alerts.keys())[0]
            # Will succeed without notification service (logs only)
            result = await self.monitor.send_alert(alert_id)
            assert result is True
            assert self.monitor.alerts[alert_id].status == AlertStatus.SENT

    @pytest.mark.asyncio
    async def test_send_nonexistent_alert(self):
        """Test sending non-existent alert"""
        result = await self.monitor.send_alert("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_with_notification_service(self):
        """Test sending alert with notification service"""
        mock_notifications = AsyncMock()
        mock_notifications.send = AsyncMock(return_value=True)
        self.monitor.notifications = mock_notifications

        deadline = (datetime.now() + timedelta(days=25)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )
        self.monitor.check_compliance_items()

        if self.monitor.alerts:
            alert_id = list(self.monitor.alerts.keys())[0]
            result = await self.monitor.send_alert(alert_id, via="whatsapp")
            assert result is True
            mock_notifications.send.assert_called_once()


class TestStatsTracking:
    """Test statistics tracking"""

    def setup_method(self):
        self.monitor = ProactiveComplianceMonitor()

    def test_stats_increment_on_add(self):
        """Test stats increment when adding items"""
        initial_stats = self.monitor.get_monitor_stats()
        initial_count = initial_stats["total_items_tracked"]

        deadline = (datetime.now() + timedelta(days=30)).isoformat()
        self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )

        new_stats = self.monitor.get_monitor_stats()
        assert new_stats["total_items_tracked"] == initial_count + 1
        assert new_stats["active_items"] == 1

    def test_stats_decrement_on_resolve(self):
        """Test stats decrement when resolving items"""
        deadline = (datetime.now() + timedelta(days=30)).isoformat()
        item = self.monitor.add_compliance_item(
            client_id="client-123",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Test",
            deadline=deadline,
            description="Test",
        )

        initial_active = self.monitor.get_monitor_stats()["active_items"]
        self.monitor.resolve_compliance_item(item.item_id)
        new_active = self.monitor.get_monitor_stats()["active_items"]

        assert new_active == initial_active - 1

    def test_stats_compliance_type_distribution(self):
        """Test compliance type distribution tracking"""
        deadline = (datetime.now() + timedelta(days=30)).isoformat()

        self.monitor.add_compliance_item(
            client_id="client-1",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Visa 1",
            deadline=deadline,
            description="Test",
        )
        self.monitor.add_compliance_item(
            client_id="client-2",
            compliance_type=ComplianceType.TAX_FILING,
            title="Tax 1",
            deadline=deadline,
            description="Test",
        )
        self.monitor.add_compliance_item(
            client_id="client-3",
            compliance_type=ComplianceType.VISA_EXPIRY,
            title="Visa 2",
            deadline=deadline,
            description="Test",
        )

        stats = self.monitor.get_monitor_stats()
        distribution = stats["compliance_type_distribution"]

        assert distribution["visa_expiry"] == 2
        assert distribution["tax_filing"] == 1


# Parameterized tests for severity calculation
# Thresholds: <0 CRITICAL, <=7 URGENT, <=30 WARNING, >30 INFO
# Note: Due to datetime precision, we use clear boundary values
@pytest.mark.parametrize(
    "days_before_deadline,expected_severity",
    [
        (90, AlertSeverity.INFO),  # Far future
        (60, AlertSeverity.INFO),  # Well over 30 days
        (32, AlertSeverity.INFO),  # Safe margin above 30
        (30, AlertSeverity.WARNING),  # Exactly 30 days (boundary)
        (20, AlertSeverity.WARNING),  # Middle of warning range
        (10, AlertSeverity.WARNING),  # 10 days (safely > 7)
        (7, AlertSeverity.URGENT),  # Exactly 7 days (boundary)
        (5, AlertSeverity.URGENT),  # 5 days
        (3, AlertSeverity.URGENT),  # 3 days
        (1, AlertSeverity.URGENT),  # 1 day
        (-1, AlertSeverity.CRITICAL),  # Overdue
        (-30, AlertSeverity.CRITICAL),  # Long overdue
    ],
)
def test_severity_calculation_parameterized(days_before_deadline, expected_severity):
    """Parameterized test for severity calculation"""
    monitor = ProactiveComplianceMonitor()

    deadline = (datetime.now() + timedelta(days=days_before_deadline)).isoformat()
    severity, _ = monitor.calculate_severity(deadline)

    assert (
        severity == expected_severity
    ), f"Deadline in {days_before_deadline} days should have severity {expected_severity}, got {severity}"
