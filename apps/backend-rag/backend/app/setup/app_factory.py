"""
FastAPI Application Factory

Creates and configures FastAPI application instance with all middleware,
routers, and lifecycle handlers.
"""

import logging

from fastapi import FastAPI

from app.core.config import settings
from app.lifecycle.shutdown import register_shutdown_handlers
from app.lifecycle.startup import register_startup_handlers
from app.routers.audio import router as audio_router
from app.routers.root_endpoints import router as root_router
from app.setup.middleware_config import register_middleware
from app.setup.observability import setup_observability
from app.setup.router_registration import include_routers
from app.streaming import router as streaming_router

logger = logging.getLogger("zantara.backend")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application instance.

    This factory function:
    1. Creates FastAPI instance
    2. Configures observability (Prometheus, OpenTelemetry)
    3. Registers middleware (CORS, Auth, Tracing, Error Monitoring, Rate Limiting)
    4. Includes all routers
    5. Registers lifecycle handlers (startup, shutdown)

    Returns:
        Configured FastAPI application instance
    """
    # Setup FastAPI
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        debug=settings.log_level == "DEBUG",  # Environment-based debug mode
    )

    # Setup observability (Prometheus + OpenTelemetry)
    setup_observability(app)

    # Register middleware (CORS, Auth, Tracing, Error Monitoring, Rate Limiting)
    register_middleware(app)

    # Include routers
    include_routers(app)
    app.include_router(root_router)
    app.include_router(audio_router, prefix="/api")
    app.include_router(streaming_router)

    # Register lifecycle handlers (startup, shutdown)
    register_startup_handlers(app)
    register_shutdown_handlers(app)

    return app

