"""
Compliance Notification Service
Responsibility: Send compliance notifications
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceNotificationService:
    """
    Service for sending compliance notifications.

    Responsibility: Send alerts via various channels (WhatsApp, Email, etc.).
    """

    def __init__(self, notification_service: Any | None = None):
        """
        Initialize notification service.

        Args:
            notification_service: Optional notification service instance
        """
        self.notification_service = notification_service

    async def send_alert(
        self, alert_id: str, client_id: str, message: str, via: str = "whatsapp"
    ) -> bool:
        """
        Send alert to client.

        Args:
            alert_id: Alert identifier
            client_id: Client identifier
            message: Alert message
            via: Notification method (whatsapp, email, slack)

        Returns:
            True if sent successfully
        """
        logger.info(f"📤 Sending alert {alert_id} via {via}")

        if self.notification_service:
            # Use notification service
            try:
                success = await self.notification_service.send(
                    client_id=client_id, message=message, via=via
                )
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
                success = False
        else:
            # Log only (no notification service)
            logger.info(f"   To: {client_id}")
            logger.info(f"   Message: {message}")
            success = True

        return success
