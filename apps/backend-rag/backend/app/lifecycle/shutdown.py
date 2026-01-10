"""
Shutdown Lifecycle Handlers

Handles application shutdown events.
"""

import asyncio
import inspect
import logging
from contextlib import suppress

from fastapi import FastAPI

from backend.services.misc.proactive_compliance_monitor import ProactiveComplianceMonitor
from backend.services.monitoring.health_monitor import HealthMonitor

logger = logging.getLogger("zantara.backend")


def register_shutdown_handlers(app: FastAPI) -> None:
    """
    Register shutdown event handlers for FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("🛑 Shutting down ZANTARA services...")

        # Shutdown WebSocket Redis Listener
        redis_task = getattr(app.state, "redis_listener_task", None)
        if redis_task:
            cancel = getattr(redis_task, "cancel", None)
            if callable(cancel):
                cancel()

            if inspect.isawaitable(redis_task):
                with suppress(asyncio.CancelledError):
                    await redis_task
            logger.info("✅ WebSocket Redis Listener stopped")

        # Shutdown Health Monitor
        health_monitor: HealthMonitor | None = getattr(app.state, "health_monitor", None)
        if health_monitor:
            await health_monitor.stop()
            logger.info("✅ Health Monitor stopped")

        # Shutdown Compliance Monitor
        compliance_monitor: ProactiveComplianceMonitor | None = getattr(
            app.state, "compliance_monitor", None
        )
        if compliance_monitor:
            await compliance_monitor.stop()
            logger.info("✅ Compliance Monitor stopped")

        # Shutdown Autonomous Scheduler (all agents)
        autonomous_scheduler = getattr(app.state, "autonomous_scheduler", None)
        if autonomous_scheduler:
            await autonomous_scheduler.stop()
            logger.info("✅ Autonomous Scheduler stopped (all agents terminated)")

        # Shutdown Metrics Pusher
        metrics_pusher_task = getattr(app.state, "metrics_pusher_task", None)
        if metrics_pusher_task:
            metrics_pusher_task.cancel()
            with suppress(asyncio.CancelledError):
                await metrics_pusher_task
            logger.info("✅ Metrics Pusher stopped")

        # Shutdown Daily Check-in Notifier
        daily_notifier = getattr(app.state, "daily_notifier", None)
        if daily_notifier:
            await daily_notifier.stop()
            logger.info("✅ Daily Check-in Notifier stopped")

        # Shutdown Weekly Email Reporter
        weekly_reporter = getattr(app.state, "weekly_reporter", None)
        if weekly_reporter:
            await weekly_reporter.stop()
            logger.info("✅ Weekly Email Reporter stopped")

        # Shutdown Team Timesheet Service (auto-logout monitor)
        ts_service = getattr(app.state, "ts_service", None)
        if ts_service:
            await ts_service.stop_auto_logout_monitor()
            logger.info("✅ Team Timesheet Service stopped")

        # Shutdown Database Health Check Loop
        db_health_check_task = getattr(app.state, "db_health_check_task", None)
        if db_health_check_task:
            db_health_check_task.cancel()
            with suppress(asyncio.CancelledError):
                await db_health_check_task
            logger.info("✅ Database Health Check Loop stopped")

        # Plugin System shutdown not needed

        # Close HTTP clients
        # HandlerProxyService removed - no cleanup needed
        logger.info("✅ HTTP clients closed")

        logger.info("✅ ZANTARA shutdown complete")
