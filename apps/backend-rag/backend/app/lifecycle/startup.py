"""
Startup Lifecycle Handlers (DEPRECATED - 2026-02-11)

⚠️ DEPRECATION NOTICE:
This file uses the old @app.on_event("startup") API which is deprecated
in FastAPI 0.100+ and can cause lifespan conflicts.

DO NOT USE THIS FILE FOR NEW CODE.

Modern approach: Use the lifespan context manager in app_factory.py.
See: backend/app/setup/app_factory.py @asynccontextmanager lifespan()

This file is kept only for backward compatibility with existing tests.
It will be removed in a future version.

Handles application startup events.
"""

import logging

from fastapi import FastAPI

from backend.app.setup.plugin_initializer import initialize_plugins
from backend.app.setup.service_initializer import initialize_services
from backend.services.monitoring.alert_service import AlertService

logger = logging.getLogger("zantara.backend")


def register_startup_handlers(app: FastAPI) -> None:
    """
    Register startup event handlers for FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.on_event("startup")
    async def on_startup() -> None:
        # Initialize AlertService at startup (avoid import-time instantiation)
        try:
            app.state.alert_service = AlertService()
            app.state.alert_service.start_digest_loop()  # Hourly latency digest
        except Exception as e:
            logger.error(f"Failed to initialize AlertService: {e}")

        await initialize_services(app)
        await initialize_plugins(app)
