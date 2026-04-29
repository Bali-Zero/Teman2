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
import logging
import os
import time
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
if not getattr(configure_logging, "_done", False):
    configure_logging()
    configure_logging._done = True

logger = logging.getLogger("zantara.backend")

SHUTDOWN_TIMEOUT = 2.0  # seconds per service stop()


async def _safe_stop(name: str, coro) -> None:
    """Stop a service with timeout. Logs warning if it hangs."""
    try:
        await asyncio.wait_for(coro, timeout=SHUTDOWN_TIMEOUT)
        logger.info(f"✅ {name} stopped")
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ {name} stop() timed out after {SHUTDOWN_TIMEOUT}s — skipping")
    except Exception as e:
        logger.warning(f"⚠️ {name} stop() error: {e}")


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
    # Mark this as the heavy RAG process so health.py resource thresholds work correctly.
    # main_api.py sets "light"; without this the memory check silently never fires on the rag VM.
    app.state.process_mode = "rag"

    # P0-0: track startup timing so /health can surface a warmup deadline.
    # Without this, an init that hangs (deadlocked DB pool, slow embedding load,
    # silent Qdrant retry loop) stays "initializing" forever and Fly.io never
    # auto-restarts. See cicatrix STRUCTURAL 2026-04-29.
    app.state.startup_started_at = time.time()
    app.state.startup_complete = False
    app.state.startup_failed = False

    async def _background_init():
        """Initialize all services in background after server starts listening."""
        # Langfuse POC observability (feat/observability-langfuse-poc).
        # Init here, not in create_app(), because:
        # 1. We're past the uvicorn "accept connections" point — safe to
        #    spend ms on setup without tripping Fly's 60s health grace.
        # 2. Langfuse SDK does its own OTEL tracer_provider registration.
        #    Running in a background task keeps that off the main loop.
        # Heavy pip imports (langfuse, openinference) live inside
        # init_observability(); the no-op path costs ~1ms.
        try:
            from backend.core.observability import init_observability

            await asyncio.to_thread(init_observability, "nuzantara-rag")
        except Exception as e:
            logger.warning(f"⚠️ Langfuse init skipped: {e}")

        try:
            from backend.services.monitoring.alert_service import AlertService

            app.state.alert_service = AlertService()
            logger.info("✅ AlertService initialized")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize AlertService: {e}")

        from backend.app.setup.service_initializer import initialize_services

        try:
            await initialize_services(app)
        except RuntimeError as e:
            logger.critical(f"❌ CRITICAL: Service initialization failed: {e}")
            app.state.startup_failed = True
            app.state.startup_error = str(e)
            return  # Stop background init, health check will report 503

        from backend.app.setup.plugin_initializer import initialize_plugins

        await initialize_plugins(app)

        # Initialize Notification Scheduler (automated email alerts)
        try:
            from backend.app.modules.notifications.scheduler import init_scheduler

            app.state.notification_scheduler = await init_scheduler(app.state.db_pool)
            logger.info("✅ Notification Scheduler initialized")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize Notification Scheduler: {e}")

        # P0-0: mark startup complete so /health stops returning warmup status.
        app.state.startup_complete = True
        logger.info("✅ ZANTARA startup complete - all services ready")

        # Warm-up CrossEncoder model in background thread (prevents 10-30s first-request spike)
        try:
            from backend.services.rag.reranker import CrossEncoderReranker

            reranker = CrossEncoderReranker()
            await asyncio.to_thread(lambda: reranker.model)  # triggers _load_model() off event loop
            logger.info("✅ CrossEncoder model warm-up complete")
        except Exception as e:
            logger.warning(f"⚠️ CrossEncoder warm-up failed (non-critical): {e}")

        # Background workers kill switch (2026-04-12 incident).
        # When DISABLE_BACKGROUND_WORKERS=1 we skip every long-running async
        # worker that holds DB connections and retries on failure. These are
        # the ones that poisoned the asyncpg pool during the disk-full cascade:
        # Workflow Queue, Legal Full Ingestion, Practice Status Listener, EventBus.
        # Keep as a safety switch; unset the env var when you want to re-enable.
        if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
            logger.warning(
                "⚠️ DISABLE_BACKGROUND_WORKERS=1 — skipping Workflow Queue + "
                "Legal Ingestion + Practice Status Listener + EventBus",
            )
            app.state._workflow_worker_task = None
            app.state.workflow_checkpointer = None
            app.state._legal_worker_task = None
            app.state.practice_status_listener = None
            app.state.event_bus = None
        else:
            # Initialize Workflow Queue (PG SKIP LOCKED + LangGraph checkpointer)
            try:
                from backend.services.workflow.checkpointer import get_checkpointer
                from backend.services.workflow.queue import run_worker

                db_url = settings.database_url
                app.state.workflow_checkpointer = await get_checkpointer(db_url)

                worker_task = asyncio.create_task(run_worker(app.state.db_pool, app.state))
                app.state._workflow_worker_task = worker_task
                logger.info("✅ Workflow queue worker started (PG SKIP LOCKED)")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize Workflow Queue: {e}")

            # Initialize Legal Full Ingestion Worker
            try:
                from backend.services.ingestion.legal_full_ingestion_worker import (
                    run_worker as legal_run_worker,
                )

                legal_worker_task = asyncio.create_task(legal_run_worker(app.state.db_pool, app.state))
                app.state._legal_worker_task = legal_worker_task
                logger.info("✅ Legal ingestion worker started (PG SKIP LOCKED)")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize Legal Ingestion Worker: {e}")

            # Initialize Practice Status Listener (M4 + M5)
            # Listens on pg_notify 'practice_changed' channel for real-time email dispatch:
            # - M4: payment_status → 'paid' → payment confirmation to client + team member
            # - M5: status milestone (on_process / submitted / approved / completed) → client email
            try:
                from backend.services.crm.practice_status_listener import PracticeStatusListener

                db_dsn = settings.database_url
                practice_listener = PracticeStatusListener(
                    db_dsn=db_dsn,
                    db_pool=app.state.db_pool,
                )
                await practice_listener.start()
                app.state.practice_status_listener = practice_listener
                logger.info("✅ Practice Status Listener started (M4 + M5 notifications)")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize Practice Status Listener: {e}")

            # Initialize EventBus (PG LISTEN/NOTIFY + in-process pub/sub)
            # Extends PracticeStatusListener pattern to client_changed, compliance_alert
            try:
                from backend.services.events.event_bus import EventBus
                from backend.services.events.handlers import register_handlers

                event_bus = EventBus(
                    db_dsn=settings.database_url,
                    db_pool=app.state.db_pool,
                )
                await event_bus.start()
                register_handlers(event_bus, app.state.db_pool)
                app.state.event_bus = event_bus
                logger.info("✅ EventBus started (client_changed, compliance_alert)")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize EventBus: {e}")

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

    # Flush Langfuse FIRST — before httpx clients close, so the SDK can
    # still POST its span buffer to cloud.langfuse.com. Fly kill_timeout
    # is 30s; Langfuse flush is bounded by LANGFUSE_FLUSH_INTERVAL (1s
    # default). Runs off-loop to avoid blocking the event loop on HTTP.
    try:
        from backend.core.observability import shutdown_observability

        await asyncio.to_thread(shutdown_observability)
        logger.info("✅ Langfuse flushed")
    except Exception as e:
        logger.warning(f"⚠️ Langfuse shutdown skipped: {e}")

    # Shutdown Workflow Queue Worker
    workflow_worker_task = getattr(app.state, "_workflow_worker_task", None)
    if workflow_worker_task and not workflow_worker_task.done():
        workflow_worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await workflow_worker_task
        logger.info("✅ Workflow queue worker stopped")

    # Shutdown Legal Ingestion Worker
    legal_worker_task = getattr(app.state, "_legal_worker_task", None)
    if legal_worker_task and not legal_worker_task.done():
        legal_worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await legal_worker_task
        logger.info("✅ Legal ingestion worker stopped")

    # Close LangGraph checkpointer psycopg3 pool
    try:
        from backend.services.workflow.checkpointer import close_checkpointer

        await close_checkpointer()
    except Exception as e:
        logger.debug(f"Checkpointer close skipped: {e}")

    # NOTE: WebSocket Redis Listener, Compliance Monitor, and Autonomous Scheduler
    # shutdown removed — _init_background_services() is disabled (omnichannel stabilization).
    # Re-add shutdown code when _init_background_services() is re-enabled.

    # Shutdown ConfirmationService (VASSAL Phase 3) — before Redis closes
    confirmation_service = getattr(app.state, "confirmation_service", None)
    if confirmation_service:
        await _safe_stop("ConfirmationService", confirmation_service.stop())

    # Shutdown Health Monitor
    health_monitor = getattr(app.state, "health_monitor", None)
    if health_monitor:
        await _safe_stop("Health Monitor", health_monitor.stop())
        if hasattr(health_monitor, "close"):
            await _safe_stop("Health Monitor close", health_monitor.close())

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
        await _safe_stop("Notification Scheduler", notification_scheduler.stop())

    # Shutdown Daily Check-in Notifier
    daily_notifier = getattr(app.state, "daily_notifier", None)
    if daily_notifier:
        await _safe_stop("Daily Check-in Notifier", daily_notifier.stop())

    # Shutdown Weekly Email Reporter
    weekly_reporter = getattr(app.state, "weekly_reporter", None)
    if weekly_reporter:
        await _safe_stop("Weekly Email Reporter", weekly_reporter.stop())

    # Shutdown Team Timesheet Service (auto-logout monitor)
    ts_service = getattr(app.state, "ts_service", None)
    if ts_service:
        await _safe_stop("Timesheet Service", ts_service.stop_auto_logout_monitor())

    # Shutdown Attendance Monitor (escalation + daily digest schedulers)
    attendance_monitor = getattr(app.state, "attendance_monitor", None)
    if attendance_monitor:
        await _safe_stop(
            "Attendance Monitor", attendance_monitor.stop_schedulers(),
        )

    # Shutdown Practice Status Listener (M4 + M5)
    practice_listener = getattr(app.state, "practice_status_listener", None)
    if practice_listener:
        await _safe_stop("Practice Status Listener", practice_listener.stop())

    # Shutdown EventBus
    event_bus = getattr(app.state, "event_bus", None)
    if event_bus:
        await _safe_stop("EventBus", event_bus.stop())

    # Shutdown Database Health Check Loop
    db_health_check_task = getattr(app.state, "db_health_check_task", None)
    if db_health_check_task:
        db_health_check_task.cancel()
        with suppress(asyncio.CancelledError):
            await db_health_check_task
        logger.info("✅ Database Health Check Loop stopped")

    # SYSTEMATIC CLEANUP of persistent HTTP clients and service connections
    # This addresses Stream I: HTTP Client Lifecycle Consolidation
    logger.info("🧹 Performing systematic service cleanup...")

    services_to_close = [
        "alert_service",
        "search_service",
        "ai_client",
        "intelligent_router",
        "tool_executor",
        "mcp_client",
        "faq_cache",
        "memory_service",
        "conversation_service",
        "activity_logger",
        "team_drive_service",
        "vision_rag",
        "pdf_vision_service",
        "jurnal_service",
        "github_publisher",
        "scraper",
        "enrichment_service",
        "nlm_enrichment_service",
        "prime_nexus_service",
    ]

    for attr_name in services_to_close:
        service = getattr(app.state, attr_name, None)
        if service and hasattr(service, "close"):
            try:
                # Call async close method
                if asyncio.iscoroutinefunction(service.close):
                    await service.close()
                else:
                    service.close()
                logger.info(f"✅ Service '{attr_name}' closed successfully")
            except Exception as e:
                logger.warning(f"⚠️ Error closing service '{attr_name}': {e}")

    # Explicitly close any remaining HTTPX clients in state (backup check)
    for attr_name, attr_val in app.state.__dict__.items():
        if attr_name not in services_to_close and hasattr(attr_val, "close"):
            # Check if it looks like an httpx.AsyncClient or our service
            if "client" in attr_name.lower() or "service" in attr_name.lower():
                try:
                    if asyncio.iscoroutinefunction(attr_val.close):
                        await attr_val.close()
                    else:
                        attr_val.close()
                    logger.info(f"✅ Additional service '{attr_name}' closed")
                except Exception as close_err:
                    logger.debug(f"Could not close '{attr_name}': {close_err}")

    # Close channel adapter HTTP clients (security audit 2026-04-03)
    channel_router = getattr(app.state, "channel_router", None)
    if channel_router and hasattr(channel_router, "_adapters"):
        for name, adapter in channel_router._adapters.items():
            if hasattr(adapter, "close"):
                try:
                    await adapter.close()
                    logger.info(f"✅ Channel adapter '{name}' closed")
                except Exception as e:
                    logger.debug(f"Could not close adapter '{name}': {e}")

    # Close persistent Qdrant health check client
    try:
        from backend.app.routers.health import close_qdrant_health_client

        await close_qdrant_health_client()
        logger.info("✅ Qdrant health check client closed")
    except Exception as e:
        logger.debug(f"Qdrant health client close: {e}")

    # Close asyncpg database pool (not in services_to_close because it uses .close() differently)
    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        try:
            await db_pool.close()
            logger.info("✅ Database pool closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing database pool: {e}")

    # Module-level client cleanups (Addressing global clients in specific services)
    try:
        from backend.services.rag.kg_subgraph_property import close_property_subgraph_client

        await close_property_subgraph_client()
        logger.info("✅ Property Subgraph module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing Property Subgraph client: {e}")

    try:
        from backend.services.misc.autonomous_scheduler import close_scheduler_client

        await close_scheduler_client()
        logger.info("✅ Autonomous Scheduler module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing Scheduler client: {e}")

    try:
        from backend.services.rag.agentic.tools import close_agentic_tools_client

        await close_agentic_tools_client()
        logger.info("✅ Agentic Tools module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing Agentic Tools client: {e}")

    # LLM provider HTTP client cleanups (S04 solidification)
    try:
        from backend.services.llm_clients.openrouter_client import openrouter_client

        await openrouter_client.close()
        logger.info("✅ OpenRouter module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing OpenRouter client: {e}")

    try:
        from backend.llm.ollama_client import close_ollama_client

        await close_ollama_client()
        logger.info("✅ Ollama module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing Ollama client: {e}")

    try:
        from backend.llm.deepseek_client import close_deepseek_client

        await close_deepseek_client()
        logger.info("✅ DeepSeek module client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing DeepSeek client: {e}")

    # Close the persistent httpx.AsyncClient used by the email pipeline
    # (Golden Rule #10). Lazy-created on first use by get_email_client().
    try:
        from backend.services.notifications.email_http import close_email_client

        await close_email_client()
        logger.info("✅ Email http client closed")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Error closing email http client: {e}")

    # P0-5 fase 2 (2026-04-29): close every module-level lazy-singleton
    # AsyncClient introduced by the httpx mass rewrite. Each importer is
    # individually try/except'd so a missing module never blocks shutdown.
    _p0_5_close_hooks = (
        ("backend.services.publisher.ig_publisher", "close_ig_publisher_client"),
        ("backend.services.publisher.linkedin_publisher", "close_linkedin_publisher_client"),
        ("backend.services.publisher.x_publisher", "close_x_publisher_client"),
        ("backend.services.newsletter.publisher", "close_newsletter_publisher_client"),
        ("backend.services.visual.fireworks_fallback", "close_fireworks_client"),
        ("backend.services.visual.vision_qa", "close_vision_qa_client"),
        ("backend.services.visual.imagen_client", "close_imagen_client"),
        ("backend.services.layout.layout_qa", "close_layout_qa_client"),
        ("backend.services.review.telegram_adapter", "close_review_telegram_client"),
        ("backend.services.measurer.meta_graph_sampler", "close_meta_graph_sampler_client"),
        ("backend.services.measurer.brevo_stats_client", "close_brevo_stats_client"),
        ("backend.services.measurer.ig_graph_sensor", "close_ig_graph_sensor_client"),
        ("backend.services.intel.intel_validators", "close_intel_validators_client"),
        ("backend.services.council.cli_runners", "close_council_runner_client"),
        ("backend.self_healing.checks.http_api", "close_http_api_check_client"),
        ("backend.services.compliance.lkpm_ready_pack", "close_brevo_client"),
    )
    for module_path, close_name in _p0_5_close_hooks:
        try:
            module = __import__(module_path, fromlist=[close_name])
            close_fn = getattr(module, close_name, None)
            if close_fn is None:
                continue
            await close_fn()
            logger.info(f"✅ P0-5 client closed: {module_path}.{close_name}")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ P0-5 close error {module_path}.{close_name}: {e}")

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
