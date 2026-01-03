"""
FastAPI Application Factory

Creates and configures FastAPI application instance with all middleware,
routers, and lifecycle handlers.
"""

import logging

from fastapi import FastAPI, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.lifecycle.shutdown import register_shutdown_handlers
from app.lifecycle.startup import register_startup_handlers
from app.routers.audio import router as audio_router
from app.routers.root_endpoints import router as root_router
from app.routers.system_observability import router as system_observability_router  # [NEW]
from app.setup.exception_handlers import (
    general_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
)
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

    # Register global exception handlers (MUST be before middleware to catch all exceptions)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Register middleware (CORS, Auth, Tracing, Error Monitoring, Rate Limiting)
    register_middleware(app)

    # Include routers
    include_routers(app)
    app.include_router(root_router)
    app.include_router(audio_router, prefix="/api")
    app.include_router(streaming_router)
    app.include_router(system_observability_router)  # [NEW]

    # Register lifecycle handlers (startup, shutdown) - MUST be before observability
    register_startup_handlers(app)
    register_shutdown_handlers(app)

    # Setup observability (Prometheus + OpenTelemetry) - MUST be after event handlers
    # FastAPIInstrumentor can conflict with @app.on_event if called before
    setup_observability(app)

    return app
