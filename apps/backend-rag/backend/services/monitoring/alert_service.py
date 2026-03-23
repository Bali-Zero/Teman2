"""
Alert Notification Service
Sends alerts for critical errors via Telegram, Slack, Discord, and logging.

Telegram is the PRIMARY alert channel (already configured for the project).
Slack/Discord are secondary channels, enabled via webhook URLs.
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class AlertLevel(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Emoji mapping for Telegram alert formatting
_LEVEL_EMOJI = {
    AlertLevel.INFO: "ℹ️",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.ERROR: "🔴",
    AlertLevel.CRITICAL: "🚨",
}


class AlertService:
    """Service for sending alerts to Telegram, Slack, Discord, and logs"""

    def __init__(self) -> None:
        from backend.app.core.config import settings

        # Telegram (primary channel)
        self.telegram_bot_token = settings.telegram_bot_token
        self.telegram_admin_chat_id = settings.admin_telegram_chat_id
        self.enable_telegram = bool(self.telegram_bot_token and self.telegram_admin_chat_id)

        # Slack (secondary)
        self.slack_webhook = settings.slack_webhook_url
        self.enable_slack = bool(self.slack_webhook)

        # Discord (secondary)
        self.discord_webhook = settings.discord_webhook_url
        self.enable_discord = bool(self.discord_webhook)

        # Logging (always on)
        self.enable_logging = True

        # Hourly digest buffer: list of latency event dicts
        self._latency_buffer: list[dict[str, Any]] = []
        self._digest_task: asyncio.Task | None = None

        # Rate limiting: track last send time per (title, path) key
        # Prevents same error from spamming Telegram on repeated failures
        self._last_alert_time: dict[str, float] = {}
        self._alert_cooldown_seconds: float = 300.0  # 5 min per error type

        # Global rate limiter: max N Telegram messages per minute across ALL paths
        self._global_send_times: list[float] = []
        self._global_max_per_minute: int = 3  # max 3 Telegram messages per minute total
        self._global_cooldown_seconds: float = 60.0

        # Persistent HTTP client
        self._client: httpx.AsyncClient | None = None

        logger.info("✅ AlertService initialized")
        logger.info(
            f"   Telegram: {'✅ enabled' if self.enable_telegram else '❌ disabled (need TELEGRAM_BOT_TOKEN + ADMIN_TELEGRAM_CHAT_ID)'}"
        )
        logger.info(
            f"   Slack: {'✅ enabled' if self.enable_slack else '❌ disabled (no SLACK_WEBHOOK_URL)'}"
        )
        logger.info(
            f"   Discord: {'✅ enabled' if self.enable_discord else '❌ disabled (no DISCORD_WEBHOOK_URL)'}"
        )
        logger.info("   Logging: ✅ enabled")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("AlertService HTTP client closed.")

    async def send_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.ERROR,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """
        Send alert to all configured channels.

        Args:
            title: Alert title
            message: Alert message
            level: Alert severity level
            metadata: Additional metadata to include

        Returns:
            Dict with status for each channel
        """
        results = {"telegram": False, "slack": False, "discord": False, "logging": False}

        # Always log
        try:
            self._log_alert(title, message, level, metadata)
            results["logging"] = True
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

        # Rate limiting: deduplicate same alert within cooldown window
        rate_key = f"{title}:{metadata.get('path', '') if metadata else ''}"
        now = time.monotonic()
        last_sent = self._last_alert_time.get(rate_key, 0.0)
        if now - last_sent < self._alert_cooldown_seconds:
            logger.debug(
                f"[alert] Rate limited '{title}' — {int(self._alert_cooldown_seconds - (now - last_sent))}s remaining"
            )
            return results

        # Global rate limiter: prevent Telegram spam across ALL error paths
        self._global_send_times = [
            t for t in self._global_send_times
            if now - t < self._global_cooldown_seconds
        ]
        if len(self._global_send_times) >= self._global_max_per_minute:
            logger.debug(
                f"[alert] Global rate limited — {len(self._global_send_times)} alerts in last {int(self._global_cooldown_seconds)}s"
            )
            return results
        self._global_send_times.append(now)

        self._last_alert_time[rate_key] = now

        # Send to Telegram (primary channel)
        if self.enable_telegram:
            try:
                await self._send_telegram_alert(title, message, level, metadata)
                results["telegram"] = True
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")

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
    ) -> None:
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

    async def _send_telegram_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ) -> None:
        """Send alert to admin Telegram chat"""
        if not self.telegram_bot_token or not self.telegram_admin_chat_id:
            return

        emoji = _LEVEL_EMOJI.get(level, "ℹ️")

        # Build compact Telegram message (HTML — more robust than Markdown)
        # Escape HTML special chars in dynamic content
        def _esc(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = [
            f"{emoji} <b>{_esc(title)}</b>",
            "",
            _esc(message),
        ]

        if metadata:
            lines.append("")
            for key, value in metadata.items():
                val_str = _esc(str(value)[:200])
                lines.append(f"• <code>{_esc(key)}</code>: {val_str}")

        lines.append(f"\n<i>Zantara RAG — {datetime.utcnow().strftime('%H:%M:%S UTC')}</i>")

        text = "\n".join(lines)

        url = f"{TELEGRAM_API_BASE}{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_admin_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        client = self._get_client()
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()

    async def _send_slack_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ) -> None:
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

        client = self._get_client()
        response = await client.post(self.slack_webhook, json=payload, timeout=5.0)
        response.raise_for_status()

    async def _send_discord_alert(
        self, title: str, message: str, level: AlertLevel, metadata: dict[str, Any] | None = None
    ) -> None:
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

        client = self._get_client()
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
    ) -> dict[str, bool]:
        """Send alert for HTTP errors (4xx/5xx). Returns send_alert results."""
        # Determine alert level
        if status_code >= 500:
            level = AlertLevel.CRITICAL if status_code >= 503 else AlertLevel.ERROR
        elif status_code >= 400:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO

        title = f"HTTP {status_code} Error"
        message = f"{method} {path} returned {status_code}"

        if error_detail:
            message += f"\nError: {error_detail}"

        metadata = {
            "status_code": status_code,
            "method": method,
            "path": path,
            "request_id": request_id or "N/A",
            "user_agent": user_agent[:100] if user_agent else "N/A",
        }

        if error_detail:
            metadata["error_detail"] = error_detail[:500]

        return await self.send_alert(title=title, message=message, level=level, metadata=metadata)

    async def send_latency_alert(
        self,
        duration_ms: float,
        method: str,
        path: str,
        threshold_ms: float,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, bool]:
        """Buffer latency alert — verrà inviato nell'hourly digest. Returns stub result."""
        self._latency_buffer.append(
            {
                "ts": datetime.utcnow().strftime("%H:%M"),
                "duration_ms": round(duration_ms),
                "method": method,
                "path": path,
                "threshold_ms": round(threshold_ms),
                "request_id": request_id or "",
                "user_agent": (user_agent or "")[:60],
            }
        )
        logger.warning(
            f"[WARNING] High Latency: {duration_ms:.0f}ms: "
            f"{method} {path} took {duration_ms:.0f}ms (buffered for hourly digest)"
        )
        return {"telegram": False, "slack": False, "discord": False, "logging": True}

    async def send_hourly_digest(self) -> None:
        """Invia un messaggio Telegram con tutti gli alert latency dell'ultima ora."""
        if not self._latency_buffer:
            logger.info("[digest] Nessun alert latency nell'ultima ora — digest saltato")
            return

        events = self._latency_buffer[:]
        self._latency_buffer.clear()

        # Raggruppa per path
        by_path: dict[str, list[dict]] = defaultdict(list)
        for e in events:
            by_path[e["path"]].append(e)

        lines = [
            "⚠️ <b>Hourly Latency Digest</b>",
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:00 UTC')} — {len(events)} eventi</i>",
            "",
        ]

        for path, evts in sorted(
            by_path.items(), key=lambda x: -max(e["duration_ms"] for e in x[1])
        ):
            worst = max(e["duration_ms"] for e in evts)
            avg = round(sum(e["duration_ms"] for e in evts) / len(evts))
            times = ", ".join(e["ts"] for e in evts[:5])
            lines.append(
                f"• <code>{evts[0]['method']} {path}</code>\n"
                f"  {len(evts)}x — max <b>{worst}ms</b> avg {avg}ms — [{times}]"
            )

        lines.append(f"\n<i>Zantara RAG — {datetime.utcnow().strftime('%H:%M:%S UTC')}</i>")
        text = "\n".join(lines)

        if self.enable_telegram:
            url = f"{TELEGRAM_API_BASE}{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_admin_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            client = self._get_client()
            await client.post(url, json=payload, timeout=10.0)
            logger.info(
                f"[digest] Hourly digest inviato: {len(events)} eventi, {len(by_path)} path"
            )
    async def _digest_loop(self) -> None:
        """Background loop: flush digest ogni ora esatta (minuto 0)."""
        while True:
            now = datetime.utcnow()
            # Aspetta fino al prossimo minuto :00
            secs_to_next_hour = (60 - now.minute) * 60 - now.second
            if secs_to_next_hour <= 0:
                secs_to_next_hour = 3600
            await asyncio.sleep(secs_to_next_hour)
            try:
                await self.send_hourly_digest()
            except Exception as e:
                logger.error(f"[digest] Errore nel digest loop: {e}")

    def start_digest_loop(self) -> None:
        """Avvia il background task digest (chiamare all'avvio dell'app)."""
        if self._digest_task is None or self._digest_task.done():
            self._digest_task = asyncio.create_task(self._digest_loop())
            logger.info("[digest] Hourly digest loop avviato")

    async def send_resource_alert(
        self,
        resource: str,
        current_value: float,
        threshold: float,
        unit: str = "%",
    ) -> None:
        """Send alert for resource exhaustion (memory, CPU, disk).

        Args:
            resource: Resource name (memory, cpu, disk)
            current_value: Current usage value
            threshold: Threshold that was exceeded
            unit: Unit of measurement
        """
        title = f"High {resource.title()} Usage: {current_value:.1f}{unit}"
        message = (
            f"{resource.title()} usage at {current_value:.1f}{unit} "
            f"(threshold: {threshold:.1f}{unit})"
        )

        level = AlertLevel.CRITICAL if current_value > threshold * 1.1 else AlertLevel.WARNING

        metadata = {
            "resource": resource,
            "current_value": f"{current_value:.1f}{unit}",
            "threshold": f"{threshold:.1f}{unit}",
        }

        await self.send_alert(title=title, message=message, level=level, metadata=metadata)


# Global singleton instance
_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Get or create global alert service instance"""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
