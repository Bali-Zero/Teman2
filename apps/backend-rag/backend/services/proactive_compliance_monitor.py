"""
Proactive Compliance Monitor - Phase 3 (Orchestration Agent #2)

Monitors compliance deadlines and requirements for clients, sending
proactive alerts before deadlines.

Features:
- Tracks visa expiry dates (KITAS, KITAP, passport)
- Monitors tax filing deadlines (SPT Tahunan, PPh, PPn)
- Tracks license renewals (IMTA, NIB, business permits)
- Monitors regulatory changes from legal_updates/tax_updates
- Sends proactive notifications (60/30/7 days before)
- Auto-calculates renewal costs from bali_zero_pricing

REFACTORED: Uses sub-services following Single Responsibility Principle
- ComplianceTrackerService: Item tracking
- AlertGeneratorService: Alert generation
- SeverityCalculatorService: Severity calculation
- ComplianceTemplatesService: Template management
- ComplianceNotificationService: Notification sending

Example Monitored Items:
- KITAS expiry: Remind 60 days before
- SPT Tahunan deadline (March 31): Remind in February
- IMTA renewal: Remind 30 days before
- Regulation changes: Immediate alert if affects client
"""

import logging
from datetime import datetime

from services.compliance import (
    AlertGeneratorService,
    AlertSeverity,
    ComplianceNotificationService,
    ComplianceTemplatesService,
    ComplianceTrackerService,
    ComplianceType,
    SeverityCalculatorService,
)

logger = logging.getLogger(__name__)


# Import types from sub-services for backward compatibility
from services.compliance.alert_generator import AlertStatus, ComplianceAlert
from services.compliance.compliance_tracker import ComplianceItem


class ProactiveComplianceMonitor:
    """
    Monitors compliance deadlines and sends proactive alerts.

    Alert Schedule:
    - 60 days before: INFO alert
    - 30 days before: WARNING alert
    - 7 days before: URGENT alert
    - Overdue: CRITICAL alert

    REFACTORED: Delegates to specialized sub-services.
    """

    def __init__(
        self,
        search_service=None,
        notification_service=None,  # For WhatsApp/email alerts
    ):
        """
        Initialize Proactive Compliance Monitor.

        Args:
            search_service: SearchService for querying Oracle collections
            notification_service: Optional service for sending alerts
        """
        self.search = search_service

        # Initialize sub-services
        self.compliance_tracker = ComplianceTrackerService()
        self.alert_generator = AlertGeneratorService()
        self.severity_calculator = SeverityCalculatorService()
        self.templates = ComplianceTemplatesService()
        self.notifications = ComplianceNotificationService(notification_service)

        # Backward compatibility: expose notification_service directly
        self.notification_service = notification_service

        # Backward compatibility: expose constants
        self.ANNUAL_DEADLINES = self.templates.ANNUAL_DEADLINES
        self.ALERT_THRESHOLDS = self.severity_calculator.ALERT_THRESHOLDS

        # Backward compatibility: expose storage
        self.compliance_items = self.compliance_tracker.compliance_items
        self.alerts = self.alert_generator.alerts

        self.monitor_stats = {
            "total_items_tracked": 0,
            "active_items": 0,
            "alerts_generated": 0,
            "alerts_sent": 0,
            "overdue_items": 0,
            "compliance_type_distribution": {},
        }

        logger.info("✅ ProactiveComplianceMonitor initialized")
        logger.info(f"   Annual deadlines: {len(self.ANNUAL_DEADLINES)}")

        # Background task control
        self.running = False
        self.task = None
        self.check_interval = 86400  # 24 hours (daily check)

    async def start(self):
        """Start the compliance monitoring loop"""
        if self.running:
            logger.warning("⚠️ ProactiveComplianceMonitor already running")
            return

        self.running = True
        import asyncio

        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info("🚀 ProactiveComplianceMonitor started (Daily checks)")

    async def stop(self):
        """Stop the compliance monitoring loop"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except Exception:
                pass
        logger.info("🛑 ProactiveComplianceMonitor stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        import asyncio

        while self.running:
            try:
                logger.info("🔍 Running daily compliance check...")
                self.check_compliance_items()
                # Also generate alerts for dashboard
                self.generate_alerts()
            except Exception as e:
                logger.error(f"❌ Error in compliance monitoring loop: {e}")

            # Wait for next interval
            await asyncio.sleep(self.check_interval)

    def add_compliance_item(
        self,
        client_id: str,
        compliance_type: ComplianceType | str,
        title: str,
        deadline: str,
        description: str = "",
        estimated_cost: float | None = None,
        required_documents: list[str] | None = None,
        metadata: dict | None = None,
    ) -> ComplianceItem:
        """
        Add a new compliance item to track.

        REFACTORED: Delegates to ComplianceTrackerService.

        Args:
            client_id: Client identifier
            compliance_type: Type of compliance (enum or string)
            title: Item title
            deadline: Deadline (ISO date)
            description: Item description
            estimated_cost: Estimated cost in IDR
            required_documents: List of required documents
            metadata: Additional metadata

        Returns:
            ComplianceItem instance
        """
        # Convert enum to string if needed
        compliance_type_str = (
            compliance_type.value
            if isinstance(compliance_type, ComplianceType)
            else compliance_type
        )

        item = self.compliance_tracker.add_compliance_item(
            client_id=client_id,
            compliance_type=compliance_type_str,
            title=title,
            deadline=deadline,
            description=description,
            estimated_cost=estimated_cost,
            required_documents=required_documents,
            metadata=metadata,
        )

        # Update monitor stats
        self.monitor_stats["total_items_tracked"] += 1
        self.monitor_stats["active_items"] += 1
        self.monitor_stats["compliance_type_distribution"][compliance_type_str] = (
            self.monitor_stats["compliance_type_distribution"].get(compliance_type_str, 0) + 1
        )

        return item

    def add_visa_expiry(
        self, client_id: str, visa_type: str, expiry_date: str, passport_number: str
    ) -> ComplianceItem:
        """
        Add KITAS/KITAP expiry tracking.

        REFACTORED: Uses ComplianceTrackerService.

        Args:
            client_id: Client identifier
            visa_type: Type of visa (KITAS, KITAP, etc.)
            expiry_date: Expiry date (ISO)
            passport_number: Passport number

        Returns:
            ComplianceItem instance
        """
        return self.add_compliance_item(
            client_id=client_id,
            compliance_type=ComplianceType.VISA_EXPIRY,
            title=f"{visa_type} Expiry",
            deadline=expiry_date,
            description=f"{visa_type} for passport {passport_number} expires on {expiry_date}",
            estimated_cost=None,  # Retrieved from database (pricing service)
            required_documents=[],  # Retrieved from database (document checklist)
            metadata={"visa_type": visa_type, "passport_number": passport_number},
        )

    def add_annual_tax_deadline(
        self, client_id: str, deadline_type: str, year: int
    ) -> ComplianceItem:
        """
        Add annual tax deadline (SPT Tahunan, etc.).

        REFACTORED: Uses ComplianceTemplatesService.

        Args:
            client_id: Client identifier
            deadline_type: Type of deadline (spt_tahunan_individual, etc.)
            year: Tax year

        Returns:
            ComplianceItem instance
        """
        template = self.templates.get_template(deadline_type)
        if not template:
            raise ValueError(f"Unknown deadline type: {deadline_type}")

        # Calculate deadline date
        deadline_date = datetime(year, template["deadline_month"], template["deadline_day"])

        compliance_type = template["compliance_type"]
        if isinstance(compliance_type, ComplianceType):
            compliance_type = compliance_type.value

        return self.add_compliance_item(
            client_id=client_id,
            compliance_type=compliance_type,
            title=f"{template['title']} - {year}",
            deadline=deadline_date.isoformat(),
            description=template["description"],
            estimated_cost=template.get("estimated_cost"),
            metadata={"deadline_type": deadline_type, "tax_year": year},
        )

    def calculate_severity(self, deadline: str) -> tuple[AlertSeverity, int]:
        """
        Calculate alert severity based on days until deadline.

        REFACTORED: Delegates to SeverityCalculatorService.

        Args:
            deadline: Deadline date (ISO)

        Returns:
            Tuple of (severity, days_until_deadline)
        """
        return self.severity_calculator.calculate_severity(deadline)

    def check_compliance_items(self) -> list[ComplianceAlert]:
        """
        Check all compliance items and generate alerts.

        REFACTORED: Delegates to AlertGeneratorService.

        Returns:
            List of new alerts generated
        """
        new_alerts = []

        for item_id, item in self.compliance_items.items():
            severity, days_until = self.calculate_severity(item.deadline)

            # Check if alert already exists for this threshold
            existing_alert = self.alert_generator.find_existing_alert(item_id, severity)
            if existing_alert:
                continue  # Already alerted at this severity level

            # Generate alert (delegated to AlertGeneratorService)
            alert = self.alert_generator.generate_alert(item, severity, days_until)
            new_alerts.append(alert)

            # Update stats
            self.monitor_stats["alerts_generated"] += 1

            if severity == AlertSeverity.CRITICAL:
                self.monitor_stats["overdue_items"] += 1

        logger.info(f"🔔 Generated {len(new_alerts)} new compliance alerts")

        return new_alerts

    async def send_alert(self, alert_id: str, via: str = "whatsapp") -> bool:
        """
        Send alert to client.

        REFACTORED: Delegates to ComplianceNotificationService.

        Args:
            alert_id: Alert identifier
            via: Notification method (whatsapp, email, slack)

        Returns:
            True if sent successfully
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False

        # Send alert (delegated to ComplianceNotificationService)
        success = await self.notifications.send_alert(
            alert_id=alert_id,
            client_id=alert.client_id,
            message=alert.message,
            via=via,
        )

        if success:
            self.alert_generator.mark_alert_sent(alert_id)
            self.monitor_stats["alerts_sent"] += 1

        return success

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark alert as acknowledged by client.

        REFACTORED: Delegates to AlertGeneratorService.

        Args:
            alert_id: Alert identifier

        Returns:
            True if acknowledged
        """
        return self.alert_generator.acknowledge_alert(alert_id)

    def resolve_compliance_item(self, item_id: str) -> bool:
        """
        Mark compliance item as resolved.

        REFACTORED: Delegates to ComplianceTrackerService.

        Args:
            item_id: Compliance item identifier

        Returns:
            True if resolved
        """
        success = self.compliance_tracker.resolve_compliance_item(item_id)

        if success:
            # Mark related alerts as resolved
            for _alert_id, alert in self.alerts.items():
                if alert.compliance_item_id == item_id:
                    alert.status = AlertStatus.RESOLVED

            # Update stats
            self.monitor_stats["active_items"] -= 1

        return success

    def get_upcoming_deadlines(
        self, client_id: str | None = None, days_ahead: int = 90
    ) -> list[ComplianceItem]:
        """
        Get upcoming compliance deadlines.

        REFACTORED: Delegates to ComplianceTrackerService.

        Args:
            client_id: Optional filter by client
            days_ahead: Look ahead window in days

        Returns:
            List of upcoming compliance items
        """
        return self.compliance_tracker.get_upcoming_deadlines(client_id, days_ahead)

    def get_alerts_for_client(
        self, client_id: str, status_filter: AlertStatus | None = None
    ) -> list[ComplianceAlert]:
        """
        Get alerts for a specific client.

        REFACTORED: Delegates to AlertGeneratorService.

        Args:
            client_id: Client identifier
            status_filter: Optional status filter

        Returns:
            List of alerts
        """
        return self.alert_generator.get_alerts_for_client(client_id, status_filter)

    def get_monitor_stats(self) -> dict:
        """
        Get monitoring statistics.

        REFACTORED: Combines stats from sub-services.
        """
        tracker_stats = self.compliance_tracker.get_stats()
        generator_stats = self.alert_generator.get_stats()

        return {
            **self.monitor_stats,
            **tracker_stats,
            **generator_stats,
            "alert_severity_distribution": {
                severity.value: sum(
                    1
                    for a in self.alerts.values()
                    if a.severity == severity and a.status != AlertStatus.EXPIRED
                )
                for severity in AlertSeverity
            },
        }

    def generate_alerts(self) -> list[dict]:
        """
        Generate compliance alerts for all monitored items.

        REFACTORED: Delegates to AlertGeneratorService and SeverityCalculatorService.
        """
        try:
            alerts = []

            # Get all compliance items
            for item_id, item in self.compliance_items.items():
                # Calculate severity (delegated to SeverityCalculatorService)
                severity, days_until = self.calculate_severity(item.deadline)

                # Create alert dict
                deadline_str = (
                    datetime.fromisoformat(item.deadline.replace("Z", "")).isoformat()
                    if isinstance(item.deadline, str)
                    else item.deadline.isoformat()
                    if hasattr(item.deadline, "isoformat")
                    else str(item.deadline)
                )

                compliance_type_value = (
                    item.compliance_type.value
                    if isinstance(item.compliance_type, ComplianceType)
                    else item.compliance_type
                )

                alert = {
                    "alert_id": f"alert_{item_id}",
                    "client_id": item.client_id,
                    "compliance_type": compliance_type_value,
                    "title": item.title,
                    "description": item.description,
                    "deadline": deadline_str,
                    "days_until": days_until,
                    "severity": severity.value,
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                }
                alerts.append(alert)

            logger.info(f"Generated {len(alerts)} compliance alerts")
            return alerts

        except Exception as e:
            logger.error(f"Error generating alerts: {e}")
            return []
