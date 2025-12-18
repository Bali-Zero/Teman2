"""
Alert Notification Service
Sends alerts for critical errors via Slack, Discord, and logging
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertService:
    """Service for sending alerts to various channels"""

    def __init__(self):
        from app.core.config import settings

        self.slack_webhook = settings.slack_webhook_url
        self.discord_webhook = settings.discord_webhook_url
        self.enable_slack = bool(self.slack_webhook)
        self.enable_discord = bool(self.discord_webhook)
        self.enable_logging = True  # Always enabled

        logger.info("✅ AlertService initialized")
        logger.info(
            f"   Slack: {'✅ enabled' if self.enable_slack else '❌ disabled (no SLACK_WEBHOOK_URL)'}"
        )
        logger.info(
            f"   Discord: {'✅ enabled' if self.enable_discord else '❌ disabled (no DISCORD_WEBHOOK_URL)'}"
        )
        logger.info("   Logging: ✅ enabled")

    async def send_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.ERROR,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """
        Send alert to all configured channels

        Args:
            title: Alert title
            message: Alert message
            level: Alert severity level
            metadata: Additional metadata to include

        Returns:
            Dict with status for each channel
        """
        results = {"slack": False, "discord": False, "logging": False}

        # Always log
        try:
            self._log_alert(title, message, level, metadata)
            results["logging"] = True
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

        # Send to Slack if enabled
        if self.enable_slack:
            try:
                await self._send_slack_alert(title, message, level, metadata)
                results["slack"] = True
            except Exception as e:
                logger.error(f"Failed to send Slack alert: {e}")

        # Send to Discord if enabled
        if self.enable_discord:
            try:
                await self._send_discord_alert(title, message, level, metadata)
                results["discord"] = True
            except Exception as e:
                logger.error(f"Failed to send Discord alert: {e}")

        return results

    def _log_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ):
        """Log alert to application logs"""
        log_message = f"[{level.value.upper()}] {title}: {message}"
        if metadata:
            log_message += f" | Metadata: {metadata}"

        if level == AlertLevel.CRITICAL:
            logger.critical(log_message)
        elif level == AlertLevel.ERROR:
            logger.error(log_message)
        elif level == AlertLevel.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    async def _send_slack_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ):
        """Send alert to Slack"""
        if not self.slack_webhook:
            return

        # Choose color based on level
        color_map = {
            AlertLevel.INFO: "#36a64f",  # green
            AlertLevel.WARNING: "#ff9800",  # orange
            AlertLevel.ERROR: "#f44336",  # red
            AlertLevel.CRITICAL: "#9c27b0",  # purple
        }
        color = color_map.get(level, "#808080")

        # Build Slack message
        fields = [
            {"title": "Level", "value": level.value.upper(), "short": True},
            {
                "title": "Time",
                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True,
            },
        ]

        if metadata:
            for key, value in metadata.items():
                fields.append(
                    {
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": len(str(value)) < 50,
                    }
                )

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"🚨 {title}",
                    "text": message,
                    "fields": fields,
                    "footer": "ZANTARA RAG Backend",
                    "ts": int(datetime.utcnow().timestamp()),
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.slack_webhook, json=payload, timeout=5.0)
            response.raise_for_status()

    async def _send_discord_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ):
        """Send alert to Discord"""
        if not self.discord_webhook:
            return

        # Choose color based on level
        color_map = {
            AlertLevel.INFO: 0x36A64F,  # green
            AlertLevel.WARNING: 0xFF9800,  # orange
            AlertLevel.ERROR: 0xF44336,  # red
            AlertLevel.CRITICAL: 0x9C27B0,  # purple
        }
        color = color_map.get(level, 0x808080)

        # Build Discord embed
        embed = {
            "title": f"🚨 {title}",
            "description": message,
            "color": color,
            "fields": [
                {"name": "Level", "value": level.value.upper(), "inline": True},
                {
                    "name": "Time",
                    "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "inline": True,
                },
            ],
            "footer": {"text": "ZANTARA RAG Backend"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        if metadata:
            for key, value in metadata.items():
                embed["fields"].append(
                    {
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": len(str(value)) < 50,
                    }
                )

        payload = {"embeds": [embed]}

        async with httpx.AsyncClient() as client:
            response = await client.post(self.discord_webhook, json=payload, timeout=5.0)
            response.raise_for_status()

    async def send_http_error_alert(
        self,
        status_code: int,
        method: str,
        path: str,
        error_detail: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Send alert for HTTP errors (4xx/5xx)

        Args:
            status_code: HTTP status code
            method: HTTP method (GET, POST, etc.)
            path: Request path
            error_detail: Error detail message
            request_id: Request ID for tracking
            user_agent: User agent string
        """
        # Determine alert level
        if status_code >= 500:
            level = AlertLevel.CRITICAL if status_code >= 503 else AlertLevel.ERROR
        elif status_code >= 400:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO

        # Build title and message
        title = f"HTTP {status_code} Error"
        message = f"{method} {path} returned {status_code}"

        if error_detail:
            message += f"\nError: {error_detail}"

        # Build metadata
        metadata = {
            "status_code": status_code,
            "method": method,
            "path": path,
            "request_id": request_id or "N/A",
            "user_agent": user_agent[:100] if user_agent else "N/A",
        }

        if error_detail:
            metadata["error_detail"] = error_detail[:500]  # Limit error detail length

        # Send alert
        await self.send_alert(title=title, message=message, level=level, metadata=metadata)

    async def send_latency_alert(
        self,
        duration_ms: float,
        method: str,
        path: str,
        threshold_ms: float,
        request_id: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Send alert for high latency

        Args:
            duration_ms: Request duration in milliseconds
            method: HTTP method
            path: Request path
            threshold_ms: Threshold that was exceeded
            request_id: Request ID
            user_agent: User Agent
        """
        title = f"High Latency: {duration_ms:.0f}ms"
        message = f"{method} {path} took {duration_ms:.0f}ms (threshold: {threshold_ms:.0f}ms)"

        metadata = {
            "duration_ms": duration_ms,
            "threshold_ms": threshold_ms,
            "method": method,
            "path": path,
            "request_id": request_id or "N/A",
            "user_agent": user_agent[:100] if user_agent else "N/A",
        }

        # Latency alerts are usually warnings unless extremely high
        level = AlertLevel.WARNING

        await self.send_alert(title=title, message=message, level=level, metadata=metadata)


# Global singleton instance
_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Get or create global alert service instance"""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
