"""
Notification Scheduler
======================
Scheduled task runner for automated notifications.

Runs daily at 9:00 AM Bali time (UTC+8).
Can be triggered manually via API.
"""

import asyncio
import logging

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.modules.notifications.checker import AlertDeduplicator, ExpiryChecker
from backend.app.modules.notifications.router import get_clients_from_db
from backend.app.modules.notifications.service import NotificationService

logger = logging.getLogger(__name__)

# Bali timezone (WITA = UTC+8)
BALI_TZ = "Asia/Makassar"


class NotificationScheduler:
    """Scheduler for automated notification tasks."""

    def __init__(self, db_pool: asyncpg.Pool | None = None) -> None:
        self.scheduler: AsyncIOScheduler | None = None
        self.is_running = False
        self.db_pool = db_pool
        self._daily_check_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler = AsyncIOScheduler(timezone=BALI_TZ)

        # Schedule daily check at 9:00 AM Bali time
        self.scheduler.add_job(
            self._daily_check,
            trigger=CronTrigger(hour=9, minute=0),
            id="daily_notification_check",
            name="Daily Expiry Check",
            replace_existing=True,
        )

        # Schedule hourly check for any missed alerts
        self.scheduler.add_job(
            self._send_pending_alerts,
            trigger=CronTrigger(minute=0),  # Every hour
            id="hourly_pending_send",
            name="Send Pending Alerts",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(
            "Notification scheduler started",
            extra={"timezone": BALI_TZ, "scheduled_jobs": len(self.scheduler.get_jobs())},
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Notification scheduler stopped")

    async def _daily_check(self) -> None:
        """Run daily expiry check. Uses lock to prevent concurrent execution."""
        if self._daily_check_lock.locked():
            logger.warning("Daily check already running, skipping")
            return

        async with self._daily_check_lock:
            logger.info("Starting daily expiry check")

            try:
                pool = self.db_pool
                if not pool:
                    logger.error("Database pool not available for scheduler")
                    return

                # Get all active clients
                clients = await get_clients_from_db(pool)

                if not clients:
                    logger.info("No clients to check")
                    return

                # Run expiry check
                checker = ExpiryChecker()
                alerts = checker.check_all_clients(clients)

                # Filter duplicates
                deduplicator = AlertDeduplicator(pool)
                new_alerts = []

                for alert in alerts:
                    should_send = await deduplicator.should_send_alert(
                        alert.client_id,
                        alert.alert_type,
                        min_days_between=1,  # Max 1 alert per day per type
                    )
                    if should_send:
                        new_alerts.append(alert)

                # Store alerts in database
                async with pool.acquire() as conn:
                    for alert in new_alerts:
                        await conn.execute(
                            """
                            INSERT INTO notification_alerts
                            (client_id, alert_type, status, message, email_subject, email_body, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (client_id, alert_type, created_date)
                            DO NOTHING
                            """,
                            alert.client_id,
                            alert.alert_type.value,
                            alert.status.value,
                            alert.message,
                            alert.email_subject,
                            alert.email_body,
                            alert.created_at,
                        )

                logger.info(
                    "Daily check completed",
                    extra={
                        "clients_checked": len(clients),
                        "alerts_generated": len(alerts),
                        "new_alerts": len(new_alerts),
                    },
                )

                # Immediately send alerts
                await self._send_pending_alerts()

            except Exception as e:
                logger.error("Daily check failed", exc_info=e)

    async def _send_pending_alerts(self) -> None:
        """Send all pending alerts. Uses lock to prevent concurrent execution."""
        if self._send_lock.locked():
            logger.debug("Send pending already running, skipping")
            return

        async with self._send_lock:
            try:
                pool = self.db_pool
                if not pool:
                    logger.error("Database pool not available for scheduler")
                    return
                service = NotificationService(pool)

                pending = await service.get_pending_alerts()

                if not pending:
                    return

                async def get_client_email(client_id: int) -> str | None:
                    async with pool.acquire() as conn:
                        return await conn.fetchval(
                            "SELECT email FROM clients WHERE id = $1",
                            client_id,
                        )

                results = await service.process_alerts_batch(pending, get_client_email)

                successful = sum(1 for r in results if r.success)

                logger.info(
                    "Pending alerts sent",
                    extra={
                        "total": len(results),
                        "successful": successful,
                        "failed": len(results) - successful,
                    },
                )

            except Exception as e:
                logger.error("Failed to send pending alerts", exc_info=e)


# Global scheduler instance
_scheduler: NotificationScheduler | None = None
_init_lock = asyncio.Lock()


async def init_scheduler(db_pool: asyncpg.Pool | None = None) -> NotificationScheduler:
    """Initialize and start the global scheduler. Thread-safe via lock."""
    global _scheduler
    async with _init_lock:
        if _scheduler and _scheduler.is_running:
            logger.warning("Scheduler already initialized, returning existing instance")
            return _scheduler
        _scheduler = NotificationScheduler(db_pool=db_pool)
        await _scheduler.start()
        return _scheduler


async def stop_scheduler() -> None:
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None


def get_scheduler() -> NotificationScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler
