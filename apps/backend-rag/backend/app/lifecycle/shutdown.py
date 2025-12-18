"""
Shutdown Lifecycle Handlers

Handles application shutdown events.
"""

import asyncio
import inspect
import logging
from contextlib import suppress

from fastapi import FastAPI

from services.health_monitor import HealthMonitor
from services.proactive_compliance_monitor import ProactiveComplianceMonitor

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

        # Plugin System shutdown not needed

        # Close HTTP clients
        # HandlerProxyService removed - no cleanup needed
        logger.info("✅ HTTP clients closed")

        logger.info("✅ ZANTARA shutdown complete")

