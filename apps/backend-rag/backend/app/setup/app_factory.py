"""
FastAPI Application Factory

Creates and configures FastAPI application instance with all middleware,
routers, and lifecycle handlers.

Modern Architecture (2026-02-11):
- Uses @asynccontextmanager lifespan API (FastAPI 0.100+)
- Consolidates startup/shutdown in single context manager
- Prevents lifespan conflicts and recursion bugs
"""

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.config import settings
from backend.app.setup.exception_handlers import (
    general_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
)
from backend.app.setup.logging_config import configure_logging
from backend.app.setup.middleware_config import register_middleware
from backend.app.setup.observability import setup_observability

# Configure structured logging FIRST (before any logger is used)
configure_logging()

logger = logging.getLogger("zantara.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifespan context manager.

    Handles application startup and shutdown in a single, clean context.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").

    Startup Phase:
    - Initialize AlertService
    - Initialize all backend services (RAG, CRM, Integrations, etc.)
    - Initialize plugin system

    Shutdown Phase:
    - Stop all background tasks (WebSocket listener, Health Monitor, etc.)
    - Stop autonomous agents (Compliance Monitor, Scheduler)
    - Close HTTP clients and connections

    Args:
        app: FastAPI application instance

    Yields:
        None (control back to FastAPI for request handling)
    """
    # ========== STARTUP PHASE ==========
    # CRITICAL: Yield quickly so uvicorn starts accepting connections.
    # Fly.io health checks require HTTP 200 on /health within 60s grace period.
    # The /health endpoint returns "initializing" when services aren't ready yet.
    logger.info("🚀 Starting ZANTARA backend - deferring heavy service init to background...")

    async def _background_init():
        """Initialize all services in background after server starts listening."""
        try:
            from backend.services.monitoring.alert_service import AlertService

            app.state.alert_service = AlertService()
            logger.info("✅ AlertService initialized")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize AlertService: {e}")

        from backend.app.setup.service_initializer import initialize_services

        await initialize_services(app)

        from backend.app.setup.plugin_initializer import initialize_plugins

        await initialize_plugins(app)

        # Initialize Notification Scheduler (automated email alerts)
        try:
            from backend.app.modules.notifications.scheduler import init_scheduler

            app.state.notification_scheduler = await init_scheduler(app.state.db_pool)
            logger.info("✅ Notification Scheduler initialized")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize Notification Scheduler: {e}")

        # Initialize X/Twitter Social Listening Monitor
        try:
            if settings.x_monitor_enabled:
                from backend.services.social.x_monitor_service import XMonitorService

                db_pool = getattr(app.state, "db_pool", None)
                x_monitor = XMonitorService(db_pool=db_pool)
                app.state.x_monitor_service = x_monitor
                await x_monitor.start()
                logger.info("✅ X Monitor Service initialized")
            else:
                logger.info("ℹ️ X Monitor disabled (X_MONITOR_ENABLED=false)")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize X Monitor: {e}")

        logger.info("✅ ZANTARA startup complete - all services ready")

    # Schedule background initialization
    init_task = asyncio.create_task(_background_init())
    app.state._init_task = init_task

    logger.info("✅ Server listening - background service init started")

    # ========== YIELD CONTROL TO FASTAPI ==========
    # Application runs and handles requests immediately.
    # /health returns "initializing" until services are ready.
    yield

    # Wait for background init to complete before shutdown
    if not init_task.done():
        logger.info("Waiting for background init to complete before shutdown...")
        init_task.cancel()
        with suppress(asyncio.CancelledError):
            await init_task

    # ========== SHUTDOWN PHASE ==========
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
    health_monitor = getattr(app.state, "health_monitor", None)
    if health_monitor:
        await health_monitor.stop()
        logger.info("✅ Health Monitor stopped")

    # Shutdown Compliance Monitor
    compliance_monitor = getattr(app.state, "compliance_monitor", None)
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

    # Shutdown Notification Scheduler
    notification_scheduler = getattr(app.state, "notification_scheduler", None)
    if notification_scheduler:
        await notification_scheduler.stop()
        logger.info("✅ Notification Scheduler stopped")

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

    # Shutdown X Monitor
    x_monitor = getattr(app.state, "x_monitor_service", None)
    if x_monitor:
        await x_monitor.stop()
        logger.info("✅ X Monitor stopped")

    # Shutdown Database Health Check Loop
    db_health_check_task = getattr(app.state, "db_health_check_task", None)
    if db_health_check_task:
        db_health_check_task.cancel()
        with suppress(asyncio.CancelledError):
            await db_health_check_task
        logger.info("✅ Database Health Check Loop stopped")

    # Close HTTP clients and Service Connections
    team_drive_service = getattr(app.state, "team_drive_service", None)
    if team_drive_service and hasattr(team_drive_service, "close"):
        await team_drive_service.close()
        logger.info("✅ Team Drive Service HTTP client closed")
        
    logger.info("✅ HTTP clients closed")

    logger.info("✅ ZANTARA shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application instance.

    Modern Architecture (2026-02-11):
    1. Creates FastAPI instance with lifespan context manager
    2. Configures observability (Prometheus, OpenTelemetry)
    3. Registers middleware (CORS, Auth, Tracing, Error Monitoring, Rate Limiting)
    4. Includes all routers
    5. Lifecycle managed via @asynccontextmanager (no @app.on_event)

    Returns:
        Configured FastAPI application instance with modern lifespan handling
    """
    # Setup FastAPI with modern lifespan context manager
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        debug=settings.log_level == "DEBUG",  # Environment-based debug mode
        lifespan=lifespan,  # Modern lifespan API (replaces @app.on_event)
    )

    # Register global exception handlers (MUST be before middleware to catch all exceptions)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Register middleware (CORS, Auth, Tracing, Error Monitoring, Rate Limiting)
    register_middleware(app)

    # Include routers (lazy imports to speed up module load)
    from backend.app.setup.router_registration import include_routers

    include_routers(app)

    from backend.app.routers.root_endpoints import router as root_router

    app.include_router(root_router)

    from backend.app.routers.audio import router as audio_router

    app.include_router(audio_router, prefix="/api")

    from backend.app.streaming import router as streaming_router

    app.include_router(streaming_router)

    from backend.app.routers.system_observability import router as system_observability_router

    app.include_router(system_observability_router)

    # Setup rate limiter for article composer (must be after router inclusion)
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from backend.app.routers import article_composer

    app.state.limiter = article_composer.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Lifecycle is handled by lifespan context manager (passed to FastAPI constructor)
    # No need for register_startup_handlers/register_shutdown_handlers

    # Setup observability (Prometheus + OpenTelemetry)
    setup_observability(app)

    return app
