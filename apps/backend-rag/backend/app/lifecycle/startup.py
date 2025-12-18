"""
Startup Lifecycle Handlers

Handles application startup events.
"""

import logging

from fastapi import FastAPI

from app.setup.plugin_initializer import initialize_plugins
from app.setup.service_initializer import initialize_services
from services.alert_service import AlertService

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
        app.state.alert_service = AlertService()
        await initialize_services(app)
        await initialize_plugins(app)

