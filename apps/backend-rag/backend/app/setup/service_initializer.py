"""
Service Initialization Module

Handles initialization of all ZANTARA RAG services with **degraded-mode**
semantics for critical services (P0-1, 2026-04-29).

Critical services (SearchService, ZantaraAIClient) are wrapped with the
``@degraded_safe`` decorator: if init fails the exception is logged, the
service name is registered in ``app.state.degraded_services`` (and in the
existing ``service_registry``), and the app keeps booting so uvicorn can
bind 8080. Routers depending on a degraded service must surface a
structured 503 (see ``backend.app.deps.services.get_search_service``).

This replaces the previous fail-fast that raised RuntimeError when a
critical service failed to init — that pattern caused Fly.io to enter a
restart loop on deterministic failures (cicatrix STRUCTURAL 2026-04-29
"Backend /health masks app.state.startup_failed"). With P0-0 already in
main, /health correctly returns 503 on ``app.state.startup_failed``, but
a degraded-but-running backend is preferable to a crash loop because at
least /health and the read-only routers stay reachable for diagnosis.

Non-critical services continue to use the in-place try/except pattern
(no ``raise``), unchanged.

Reference: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-1_searchservice_degraded_mode.md

# Cache bust: 2026-01-01 15:38 UTC - Fixed _init_rag_components function definition
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import random
from typing import Any, Callable

import asyncpg
from fastapi import FastAPI

from backend.app.core.config import settings
from backend.app.core.service_health import ServiceStatus, service_registry

logger = logging.getLogger("zantara.backend")


def _record_genome_scar(service_name: str, exc: Exception) -> None:
    """Best-effort scar registration in the genome KB.

    Symbiosis Pillar 2 (accumulated learning): every degraded init is a
    cicatrix that future agents should be able to query. We swallow ANY
    failure here — a missing/broken genome module must never block app
    startup.
    """
    try:  # noqa: SIM105 — broad catch is intentional, see docstring
        from backend.services.genome.client import (  # type: ignore[import-not-found]
            get_genome_client,
        )

        get_genome_client().record_scar(
            cell="apps/backend-rag",
            scar_id=f"{service_name}_init_failure_{type(exc).__name__}",
            procedure=f"_init_critical_services raised {type(exc).__name__}",
            rationale=str(exc)[:500],
        )
    except Exception:
        # Genome unavailable / contract changed / Redis down — never
        # propagate. The degraded_services set + service_registry are the
        # authoritative signals; genome is the cherry on top.
        return


def degraded_safe(service_name: str) -> Callable[..., Any]:
    """Decorator: catches init failure → registers service as degraded.

    Wraps an ``async def _init_<X>(app: FastAPI, ...)`` so that an
    exception during init does NOT propagate — instead:

    1. The exception is logged (with stack trace) at ERROR level.
    2. ``app.state.degraded_services`` is initialized to a ``set`` if
       missing, and ``service_name`` is added.
    3. A best-effort genome scar is recorded (see ``_record_genome_scar``).
    4. The wrapper returns ``None``, so the caller's destructuring keeps
       working (e.g. ``search_service, ai_client = ...``).

    The decorator does NOT touch ``service_registry`` — that remains the
    init function's responsibility on success, and the per-service
    try/except (still inside the wrapped helper) is responsible for the
    UNAVAILABLE registration on failure. Two-track state is intentional:
    ``service_registry`` is the in-process status board,
    ``degraded_services`` is the user-facing surface (returned in 503
    detail by dependencies).

    P0-0 (in main) made ``/health`` return 503 on
    ``app.state.startup_failed``. With P0-1, ``startup_failed`` stays
    ``False`` even when one critical service is degraded — the health
    endpoint (and downstream routers) can read ``degraded_services`` to
    report granular status.
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        async def wrapper(app: FastAPI, *args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(app, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — by design, see docstring
                logger.exception(
                    "❌ Critical service '%s' init failed; entering degraded mode",
                    service_name,
                )
                if (
                    not hasattr(app.state, "degraded_services")
                    or app.state.degraded_services is None
                ):
                    app.state.degraded_services = set()
                app.state.degraded_services.add(service_name)
                _record_genome_scar(service_name, exc)
                return None
        return wrapper
    return decorator


@degraded_safe("search")
async def _init_search_service(app: FastAPI) -> Any:
    """Initialize SearchService and verify Qdrant reachability.

    On failure: ``@degraded_safe`` catches, registers ``search`` in
    ``app.state.degraded_services``, returns None. On success: registers
    HEALTHY in ``service_registry``. The ``SEARCH_FORCE_FAIL`` env var
    deterministically triggers the degraded path for local end-to-end
    verification (see Phase 5 of the P0-1 prompt) — guarded by an env
    check so it never accidentally trips in CI.
    """
    if os.getenv("SEARCH_FORCE_FAIL") == "1":
        # Test/verification hook only. Raising here exercises the
        # @degraded_safe path end-to-end without breaking Qdrant.
        raise RuntimeError(
            "SEARCH_FORCE_FAIL=1 — synthetic degraded-mode injection (P0-1)",
        )

    from backend.services.ingestion.collection_manager import CollectionManager
    from backend.services.misc.cultural_insights_service import CulturalInsightsService
    from backend.services.routing.conflict_resolver import ConflictResolver
    from backend.services.routing.query_router_integration import QueryRouterIntegration
    from backend.services.search.search_service import SearchService

    # Create shared services
    collection_manager = CollectionManager(qdrant_url=settings.qdrant_url)
    conflict_resolver = ConflictResolver()
    query_router = QueryRouterIntegration()

    # Create cultural insights service (requires embedder)
    from backend.core.embeddings import create_embeddings_generator

    embedder = create_embeddings_generator()
    cultural_insights = CulturalInsightsService(
        collection_manager=collection_manager, embedder=embedder,
    )

    # Create SearchService with dependencies
    search_service = SearchService(
        collection_manager=collection_manager,
        conflict_resolver=conflict_resolver,
        cultural_insights=cultural_insights,
        query_router=query_router,
    )

    # Add cross-encoder reranking methods to SearchService instance
    # (non-critical: a failure here doesn't degrade SearchService itself)
    if settings.reranker_backend == "cross-encoder":
        try:
            from backend.services.rag.reranker_integration import add_cross_encoder_reranking

            add_cross_encoder_reranking(search_service)
        except Exception as e:
            logger.warning(f"⚠️ Cross-encoder reranking setup failed (non-critical): {e}")

    # Store services in app state for dependency injection. ONLY done on
    # the success path — partially-initialized state would mislead
    # downstream code into thinking SearchService is ready.
    app.state.collection_manager = collection_manager
    app.state.conflict_resolver = conflict_resolver
    app.state.cultural_insights = cultural_insights
    app.state.query_router = query_router
    app.state.search_service = search_service

    # Verify Qdrant is actually reachable before registering as HEALTHY.
    # Note: a Qdrant probe failure here is registered as UNAVAILABLE in
    # service_registry but does NOT trip degraded_safe (we don't re-raise)
    # — the SearchService object exists, callers will discover Qdrant
    # downtime at request time. This preserves prior behavior.
    try:
        import httpx as _httpx

        _headers = {}
        if settings.qdrant_api_key:
            _headers["api-key"] = settings.qdrant_api_key
        async with _httpx.AsyncClient(
            base_url=settings.qdrant_url, headers=_headers, timeout=5.0,
        ) as _qdrant_check:
            _resp = await _qdrant_check.get("/collections")
            _resp.raise_for_status()
        service_registry.register("search", ServiceStatus.HEALTHY)
        logger.info("✅ SearchService initialized (Qdrant verified)")
    except Exception as qdrant_err:
        service_registry.register(
            "search", ServiceStatus.UNAVAILABLE,
            error=f"SearchService created but Qdrant unreachable: {qdrant_err}",
        )
        logger.error(
            f"❌ SearchService created but Qdrant unreachable — marking UNAVAILABLE: {qdrant_err}",
        )

    return search_service


@degraded_safe("ai_client")
async def _init_ai_client(app: FastAPI) -> Any:
    """Initialize ZantaraAIClient.

    On failure: ``@degraded_safe`` catches, registers ``ai_client`` in
    ``app.state.degraded_services``, returns None.
    """
    from backend.llm.zantara_ai_client import ZantaraAIClient

    ai_client = ZantaraAIClient()
    app.state.ai_client = ai_client
    service_registry.register("ai", ServiceStatus.HEALTHY)
    logger.info("✅ ZantaraAIClient initialized")
    return ai_client


async def _init_critical_services(
    app: FastAPI,
) -> tuple[Any, Any]:
    """
    Initialize critical services: SearchService and ZantaraAIClient.

    P0-1 (2026-04-29): no longer raises on failure. Each helper is
    wrapped with ``@degraded_safe`` which logs, registers the service in
    ``app.state.degraded_services``, and returns None. The app keeps
    booting so uvicorn binds 8080; routers depending on these services
    must surface 503 (see ``backend.app.deps.services``).

    Args:
        app: FastAPI application instance

    Returns:
        Tuple of (search_service, ai_client). Either may be None if
        initialization failed; callers must handle the None case.
    """
    # Store service registry in app state for health endpoints
    app.state.service_registry = service_registry

    # 1. Search / Qdrant (CRITICAL — degraded-mode on failure)
    search_service = await _init_search_service(app)

    # 2. AI Client (CRITICAL — degraded-mode on failure)
    ai_client = await _init_ai_client(app)

    # P0-1: NO `raise RuntimeError` here. The previous fail-fast caused
    # Fly.io restart loops on deterministic failures (cicatrix
    # STRUCTURAL 2026-04-29). Health endpoint surfaces degraded state via
    # `app.state.degraded_services`; per-router dependencies surface 503
    # to clients. This is intentional graceful degradation.
    if service_registry.has_critical_failures():
        failures = service_registry.format_failures_message()
        logger.warning(
            "⚠️ Critical service(s) degraded but app continues to boot: %s",
            failures,
        )

    return search_service, ai_client


async def _init_tool_stack(app: FastAPI) -> Any:
    """
    Initialize tool stack: Python-native tools and MCP client.

    Args:
        app: FastAPI application instance

    Returns:
        ToolExecutor instance
    """
    from backend.services.misc.mcp_client_service import initialize_mcp_client
    from backend.services.misc.tool_executor import ToolExecutor
    from backend.services.misc.zantara_tools import ZantaraTools

    # Tool stack (Python-native + MCP)
    zantara_tools = ZantaraTools()

    # Initialize MCP Client (optional - fails gracefully)
    mcp_client = None
    try:
        mcp_client = await initialize_mcp_client()
        logger.info(f"✅ MCP Client initialized with {len(mcp_client.available_tools)} tools")
        service_registry.register("mcp", ServiceStatus.HEALTHY, critical=False)
    except Exception as e:
        logger.warning(f"⚠️ MCP Client initialization failed (non-critical): {e}")
        service_registry.register("mcp", ServiceStatus.DEGRADED, critical=False)

    tool_executor = ToolExecutor(
        zantara_tools=zantara_tools,
        mcp_client=mcp_client,  # MCP tools (filesystem, memory, brave-search, etc.)
    )
    service_registry.register("tools", ServiceStatus.HEALTHY, critical=False)

    # State persistence
    app.state.tool_executor = tool_executor
    app.state.zantara_tools = zantara_tools
    app.state.mcp_client = mcp_client  # MCP tools client

    return tool_executor


async def _init_rag_components(app: FastAPI, search_service: Any) -> Any:
    """
    Initialize RAG components: CulturalRAGService and QueryRouter.

    Args:
        app: FastAPI application instance
        search_service: SearchService instance (may be None)

    Returns:
        QueryRouter instance
    """
    from backend.services.misc.cultural_rag_service import CulturalRAGService
    from backend.services.routing.query_router import QueryRouter

    # Initialize CulturalRAGService with CulturalInsightsService
    cultural_insights_service = getattr(app.state, "cultural_insights", None)
    if cultural_insights_service:
        cultural_rag_service = CulturalRAGService(
            cultural_insights_service=cultural_insights_service,
        )
    else:
        # Fallback to search_service for backward compatibility
        cultural_rag_service = CulturalRAGService(search_service=search_service)

    app.state.cultural_rag = cultural_rag_service
    query_router = QueryRouter()
    service_registry.register("rag", ServiceStatus.HEALTHY, critical=False)

    app.state.query_router = query_router

    return query_router


async def _init_specialized_agents(
    _app: FastAPI,
    search_service: Any,
    ai_client: Any,
    query_router: Any,
) -> tuple[Any, Any, Any]:
    """
    Initialize specialized agents: AutonomousResearch, CrossOracle, ClientJourney.

    Args:
        app: FastAPI application instance
        search_service: SearchService instance
        ai_client: ZantaraAIClient instance
        query_router: QueryRouter instance

    Returns:
        Tuple of (autonomous_research_service, cross_oracle_synthesis_service, client_journey_orchestrator)
    """
    from backend.services.misc.autonomous_research_service import AutonomousResearchService
    from backend.services.misc.client_journey_orchestrator import ClientJourneyOrchestrator
    from backend.services.oracle.cross_oracle_synthesis_service import CrossOracleSynthesisService

    autonomous_research_service = None
    cross_oracle_synthesis_service = None
    client_journey_orchestrator = None

    # Since we fail-fast on critical services, ai_client and search_service are guaranteed
    try:
        autonomous_research_service = AutonomousResearchService(
            search_service=search_service,
            query_router=query_router,
            zantara_ai_service=ai_client,
        )
        logger.info("✅ AutonomousResearchService initialized")
    except Exception as e:
        # Exception contains service init error, not credentials
        logger.error(
            f"❌ Failed to initialize AutonomousResearchService: {e}",
        )  # nosemgrep: python-logger-credential-disclosure

    try:
        cross_oracle_synthesis_service = CrossOracleSynthesisService(
            search_service=search_service, zantara_ai_client=ai_client,
        )
        logger.info("✅ CrossOracleSynthesisService initialized")
    except Exception as e:
        # Exception contains service init error, not credentials
        logger.error(
            f"❌ Failed to initialize CrossOracleSynthesisService: {e}",
        )  # nosemgrep: python-logger-credential-disclosure

    try:
        client_journey_orchestrator = ClientJourneyOrchestrator()
        logger.info("✅ ClientJourneyOrchestrator initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize ClientJourneyOrchestrator: {e}")

    return autonomous_research_service, cross_oracle_synthesis_service, client_journey_orchestrator


async def initialize_database_services(app: FastAPI) -> asyncpg.Pool | None:
    """
    Initialize database services: Database pool and Team Timesheet service.

    Args:
        app: FastAPI application instance

    Returns:
        Database pool instance or None if initialization failed
    """
    if not settings.database_url:
        service_registry.register(
            "database",
            ServiceStatus.UNAVAILABLE,
            error="DATABASE_URL not configured",
            critical=False,
        )
        logger.warning("⚠️ DATABASE_URL not configured - Team Timesheet Service unavailable")
        app.state.ts_service = None
        return None

    logger.info(f"DEBUG: DATABASE_URL is set: {settings.database_url[:15]}...")

    max_retries = 5
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            logger.info(f"Database initialization attempt {attempt + 1}/{max_retries}")

            # Prepare DSN and SSL options for asyncpg
            dsn = settings.database_url
            ssl_context = None

            # Handle sslmode= manually for asyncpg (which doesn't support sslmode in DSN)
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(dsn)
            params = parse_qs(parsed.query)
            sslmode = params.pop("sslmode", [None])[0]
            if sslmode == "disable":
                ssl_context = False
                logger.info("DEBUG: Detected sslmode=disable, setting ssl=False explicitly")
            # Rebuild DSN without sslmode
            clean_query = urlencode(params, doseq=True)
            dsn = urlunparse(parsed._replace(query=clean_query))

            # Create asyncpg pool for team timesheet service
            async def init_db_connection(conn: asyncpg.Connection) -> None:
                await conn.set_type_codec(
                    "jsonb",
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema="pg_catalog",
                )
                await conn.set_type_codec(
                    "json",
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema="pg_catalog",
                )
                # Prevent runaway queries (30s covers RAG KG traversal ~5-10s)
                await conn.execute("SET statement_timeout = '30s'")
                # Validate connection
                await conn.execute("SELECT 1")

            # Configure pool kwargs
            pool_kwargs = {
                "dsn": dsn,
                "min_size": getattr(settings, "db_pool_min_size", None) or 2,
                "max_size": getattr(settings, "db_pool_max_size", None) or 10,
                "command_timeout": getattr(settings, "db_command_timeout", None) or 30,
                # 30s ensures stale connections are dropped before the first request hits
                # after a Fly.io cold start (~35s). Previously 300s caused
                # "connection was closed in the middle of operation" on POST /api/crm/clients.
                # Combined with _database_health_check_loop (every 15s) and InterfaceError
                # handler in exception_handlers.py → full stale connection coverage.
                "max_inactive_connection_lifetime": 30.0,
                "init": init_db_connection,
                # Required for PgBouncer transaction mode — prevents prepared statement leak
                "statement_cache_size": 0,
            }

            # Add ssl parameter if explicitly determined
            if ssl_context is False:
                pool_kwargs["ssl"] = False

            db_pool = await asyncpg.create_pool(**pool_kwargs)

            # Verify pool works
            async with db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    raise ValueError("Pool validation failed")

            from backend.services.analytics.attendance_monitor import AttendanceMonitor
            from backend.services.analytics.daily_checkin_notifier import init_daily_notifier
            from backend.services.analytics.team_timesheet_service import init_timesheet_service
            from backend.services.analytics.weekly_email_reporter import init_weekly_reporter

            attendance_monitor = AttendanceMonitor(db_pool)
            await attendance_monitor.start_schedulers()
            app.state.attendance_monitor = attendance_monitor

            ts_service = init_timesheet_service(db_pool, attendance_monitor=attendance_monitor)
            app.state.ts_service = ts_service
            app.state.db_pool = db_pool  # Store pool for other services

            # Initialize daily check-in notifier (emails at 10:00 Bali time)
            daily_notifier = init_daily_notifier(db_pool)
            app.state.daily_notifier = daily_notifier

            # Initialize weekly email activity reporter (emails Sundays at 16:00 Bali time)
            weekly_reporter = init_weekly_reporter(db_pool)
            app.state.weekly_reporter = weekly_reporter

            # Start background tasks
            await ts_service.start_auto_logout_monitor()
            await daily_notifier.start()
            await weekly_reporter.start()

            # Start health check task
            app.state.db_health_check_task = asyncio.create_task(
                _database_health_check_loop(db_pool),
            )

            # Initialize GraphService (non-critical — KG traversal tool)
            try:
                from backend.services.misc.graph_service import GraphService

                graph_service = GraphService(db_pool=db_pool)
                app.state.graph_service = graph_service
                logger.info("✅ GraphService initialized")
            except Exception as e:
                logger.warning(f"⚠️ GraphService initialization failed (non-critical): {e}")
                app.state.graph_service = None

            service_registry.register("database", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ Database services initialized successfully")
            try:
                from backend.app.metrics import database_init_success_total

                database_init_success_total.inc()
            except ImportError:
                pass

            return db_pool

        except (asyncpg.PostgresError, ValueError, ConnectionError) as e:
            error_type = type(e).__name__
            is_transient = _is_transient_error(e)

            logger.warning(
                f"⚠️ Database initialization failed (attempt {attempt + 1}/{max_retries}): {e}",
                extra={
                    "attempt": attempt + 1,
                    "error_type": error_type,
                    "is_transient": is_transient,
                },
            )

            try:
                from backend.app.metrics import database_init_failed_total

                database_init_failed_total.labels(
                    error_type=error_type, is_transient=str(is_transient),
                ).inc()
            except ImportError:
                pass

            if attempt < max_retries - 1 and is_transient:
                # Exponential backoff with jitter
                delay = base_delay * (2**attempt) + (random.random() * 0.5)
                logger.info(f"Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
            else:
                # Permanent error or max retries reached
                service_registry.register(
                    "database",
                    ServiceStatus.UNAVAILABLE,
                    error=str(e),
                    critical=False,
                )
                logger.error(f"❌ Database initialization failed permanently: {e}")
                try:
                    from backend.app.metrics import database_init_permanent_failure_total

                    database_init_permanent_failure_total.inc()
                except ImportError:
                    pass
                app.state.ts_service = None
                app.state.db_pool = None
                app.state.db_init_error = str(e)
                return None
        except Exception as e:
            # Catch-all for unexpected errors
            error_type = type(e).__name__
            is_transient = _is_transient_error(e)

            logger.warning(
                f"⚠️ Unexpected database error (attempt {attempt + 1}/{max_retries}): {e}",
                extra={
                    "attempt": attempt + 1,
                    "error_type": error_type,
                    "is_transient": is_transient,
                },
            )

            try:
                from backend.app.metrics import database_init_failed_total

                database_init_failed_total.labels(
                    error_type=error_type, is_transient=str(is_transient),
                ).inc()
            except ImportError:
                pass

            if attempt < max_retries - 1 and is_transient:
                delay = base_delay * (2**attempt) + (random.random() * 0.5)
                logger.info(f"Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
            else:
                service_registry.register(
                    "database", ServiceStatus.UNAVAILABLE, error=str(e), critical=False,
                )
                logger.error(f"❌ Unexpected error initializing database: {e}")
                app.state.ts_service = None
                app.state.db_pool = None
                app.state.db_init_error = str(e)
                return None

    return None


def _is_transient_error(error: Exception) -> bool:
    """Determine if error is transient and retryable."""
    error_msg = str(error).lower()

    transient_patterns = [
        "connection",
        "timeout",
        "temporarily unavailable",
        "too many connections",
        "server closed",
        "network",
    ]

    return any(pattern in error_msg for pattern in transient_patterns)


async def _database_health_check_loop(db_pool: asyncpg.Pool) -> None:
    """Periodic health check for database pool with automatic stale connection recovery."""
    check_interval = 15  # seconds (fast recovery for Fly.io cold starts)
    from backend.app.core.service_health import ServiceStatus, service_registry

    while True:
        try:
            await asyncio.sleep(check_interval)

            # Check pool health
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("SELECT 1")

                # Pool is healthy
                service_registry.register("database", ServiceStatus.HEALTHY)
                try:
                    from backend.app.metrics import database_health_check_success_total

                    database_health_check_success_total.inc()
                except ImportError:
                    pass

            except Exception as e:
                logger.warning(f"Database health check failed: {e}")
                service_registry.register(
                    "database",
                    ServiceStatus.DEGRADED,
                    error=str(e),
                )
                try:
                    from backend.app.metrics import database_health_check_failed_total

                    database_health_check_failed_total.inc()
                except ImportError:
                    pass

                # Try to recover stale connections by expiring the pool
                if _is_transient_error(e):
                    logger.info("Attempting database pool recovery — expiring idle connections...")
                    try:
                        await db_pool.expire_connections()
                        # Verify recovery worked
                        async with db_pool.acquire() as test_conn:
                            await test_conn.execute("SELECT 1")
                        service_registry.register("database", ServiceStatus.HEALTHY)
                        logger.info("✅ Database pool recovered successfully")
                    except Exception as recovery_err:
                        logger.error(f"❌ Database pool recovery failed: {recovery_err}")

        except asyncio.CancelledError:
            logger.info("Database health check loop cancelled")
            break
        except Exception as e:
            logger.exception(f"Error in database health check loop: {e}")


async def initialize_faq_cache_service(app: FastAPI) -> None:
    """
    Initialize FAQ Cache service for reducing API costs.

    Non-critical service - if Redis is unavailable, system continues without caching.

    Args:
        app: FastAPI application instance
    """
    try:
        from backend.services.caching import NotebookLMCacheService

        # Check feature flag
        enable_cache = os.getenv("ENABLE_FAQ_CACHE", "true").lower() == "true"

        if not enable_cache:
            logger.info("ℹ️  FAQ cache disabled (ENABLE_FAQ_CACHE=false)")
            app.state.faq_cache = None
            service_registry.register("faq_cache", ServiceStatus.UNAVAILABLE)
            return

        cache_service = NotebookLMCacheService()
        await cache_service.initialize()

        if cache_service.redis_client:
            app.state.faq_cache = cache_service
            service_registry.register("faq_cache", ServiceStatus.HEALTHY)
            logger.info("✅ FAQ Cache service initialized (Redis connected successfully)")
            # NOTE: Stats fetching moved to dedicated /health/cache endpoint
            # to avoid blocking startup with slow Redis scan operations
        else:
            logger.warning("⚠️  FAQ cache disabled (Redis connection failed)")
            app.state.faq_cache = None
            service_registry.register("faq_cache", ServiceStatus.DEGRADED)

    except Exception as e:
        logger.warning(f"⚠️  FAQ Cache initialization failed: {e}")
        app.state.faq_cache = None
        service_registry.register("faq_cache", ServiceStatus.DEGRADED, error=str(e))


async def initialize_crm_and_memory_services(
    app: FastAPI, ai_client: Any, db_pool: asyncpg.Pool | None,
) -> None:
    """
    Initialize CRM and Memory services: MemoryService, ConversationService.

    Args:
        app: FastAPI application instance
        ai_client: ZantaraAIClient instance
        db_pool: Database pool instance (may be None)
    """
    try:
        # Initialize Memory Service (Postgres)
        # MemoryServicePostgres expects database_url string, not Pool object
        from backend.app.core.config import settings
        from backend.services.memory import MemoryServicePostgres
        from backend.services.memory.collective_memory_workflow import (
            create_collective_memory_workflow,
        )
        from backend.services.misc.conversation_service import ConversationService

        app.state.memory_service = MemoryServicePostgres(settings.database_url)
        await app.state.memory_service.connect()

        # Initialize Conversation Service
        app.state.conversation_service = ConversationService(db_pool)
        logger.info("✅ Conversation Service initialized")

        # Initialize Audit Logger and Metrics
        if db_pool:
            from backend.app.services.crm.audit_logger import audit_logger
            from backend.app.services.crm.metrics import metrics_collector

            audit_logger.initialize(db_pool)
            metrics_collector.initialize(db_pool)

        # Initialize Activity Logger
        from backend.services.monitoring.activity_logger import activity_logger

        await activity_logger.initialize(db_pool)
        app.state.activity_logger = activity_logger
        logger.info("✅ Activity Logger initialized")

        # Initialize Collective Memory Workflow
        collective_memory_workflow = create_collective_memory_workflow(
            memory_service=app.state.memory_service,
        )
        app.state.collective_memory_workflow = collective_memory_workflow
        service_registry.register("memory", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ CollectiveMemoryWorkflow initialized")
    except Exception as e:
        service_registry.register("memory", ServiceStatus.DEGRADED, error=str(e), critical=False)
        logger.error(f"❌ Failed to initialize CRM/Memory services: {e}")
        # Do NOT reset db_pool here, as it affects other services
        app.state.crm_init_error = str(e)


async def initialize_intelligent_router(
    app: FastAPI,
    ai_client: Any,
    search_service: Any,
    tool_executor: Any,
    cultural_rag_service: Any,
    autonomous_research_service: Any,
    cross_oracle_synthesis_service: Any,
    client_journey_orchestrator: Any,
    collaborator_service: Any,
    db_pool: asyncpg.Pool | None,
) -> None:
    """
    Initialize IntelligentRouter with all required services.

    Args:
        app: FastAPI application instance
        ai_client: ZantaraAIClient instance
        search_service: SearchService instance
        tool_executor: ToolExecutor instance
        cultural_rag_service: CulturalRAGService instance
        autonomous_research_service: AutonomousResearchService instance (may be None)
        cross_oracle_synthesis_service: CrossOracleSynthesisService instance (may be None)
        client_journey_orchestrator: ClientJourneyOrchestrator instance (may be None)
        collaborator_service: CollaboratorService instance (may be None)
        db_pool: Database pool instance (may be None)
    """
    from backend.services.crm.collaborator_service import CollaboratorService
    from backend.services.routing.intelligent_router import IntelligentRouter

    # Initialize CollaboratorService for user identity lookup
    if collaborator_service is None:
        try:
            collaborator_service = CollaboratorService()
            app.state.collaborator_service = collaborator_service
            logger.info("✅ CollaboratorService initialized")
        except Exception as e:
            logger.warning(f"⚠️ CollaboratorService initialization failed: {e}")
            app.state.collaborator_service = None

    # Initialize IntelligentRouter (critical services are guaranteed available)
    try:
        intelligent_router = IntelligentRouter(
            ai_client=ai_client,
            search_service=search_service,
            tool_executor=tool_executor,
            cultural_rag_service=cultural_rag_service,
            autonomous_research_service=autonomous_research_service,
            cross_oracle_synthesis_service=cross_oracle_synthesis_service,
            client_journey_orchestrator=client_journey_orchestrator,
            # personality_service removed - replaced by Zantara Identity Layer
            collaborator_service=collaborator_service,
            db_pool=db_pool,
        )
        app.state.intelligent_router = intelligent_router
        service_registry.register("router", ServiceStatus.HEALTHY, critical=True)
        logger.info("✅ IntelligentRouter initialized with full services")
    except Exception as e:
        service_registry.register("router", ServiceStatus.UNAVAILABLE, error=str(e), critical=True)
        logger.error(f"❌ Failed to initialize IntelligentRouter: {e}")
        app.state.intelligent_router = None

    # Initialize SpecializedServiceRouter (wraps the 3 specialized services for OrchestratorCore)
    try:
        from backend.services.routing.specialized_service_router import SpecializedServiceRouter

        specialized_router = SpecializedServiceRouter(
            autonomous_research_service=autonomous_research_service,
            cross_oracle_synthesis_service=cross_oracle_synthesis_service,
            client_journey_orchestrator=client_journey_orchestrator,
        )
        app.state.specialized_router = specialized_router
        service_registry.register("specialized_router", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ SpecializedServiceRouter initialized (AutonomousResearch + CrossOracle + ClientJourney)")
    except Exception as e:
        logger.warning(f"⚠️ SpecializedServiceRouter initialization failed (non-critical): {e}")
        app.state.specialized_router = None


async def _init_background_services(
    app: FastAPI,
    search_service: Any,
    ai_client: Any,
    db_pool: asyncpg.Pool | None,
) -> None:
    """
    Initialize background services: HealthMonitor, ComplianceMonitor, Scheduler, WebSocket.

    Args:
        app: FastAPI application instance
        search_service: SearchService instance
        ai_client: ZantaraAIClient instance
        db_pool: Database pool instance (may be None)
    """
    from backend.app.routers.websocket import redis_listener
    from backend.services.misc.autonomous_scheduler import create_and_start_scheduler
    from backend.services.misc.proactive_compliance_monitor import ProactiveComplianceMonitor
    from backend.services.monitoring.alert_service import AlertService
    from backend.services.monitoring.health_monitor import HealthMonitor

    # Plugin System: Modern system available in core/plugins/
    logger.info("🔌 Plugin System: Using HealthMonitor for monitoring")

    # Health Monitor (Self-Healing Monitoring)
    try:
        logger.info("🏥 Initializing Health Monitor (Self-Healing System)...")
        alert_service = getattr(app.state, "alert_service", None)
        if alert_service is None:
            alert_service = AlertService()
            app.state.alert_service = alert_service

        health_monitor = HealthMonitor(alert_service=alert_service, check_interval=60)

        # Inject dependencies for accurate monitoring
        health_monitor.set_services(
            memory_service=getattr(app.state, "memory_service", None),
            intelligent_router=getattr(app.state, "intelligent_router", None),
            tool_executor=getattr(app.state, "tool_executor", None),
            app_state=app.state,  # Pass app.state for dynamic lookups
        )

        await health_monitor.start()

        app.state.health_monitor = health_monitor
        service_registry.register("health_monitor", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Health Monitor: Active (check_interval=60s)")
    except Exception as e:
        service_registry.register(
            "health_monitor", ServiceStatus.DEGRADED, error=str(e), critical=False,
        )
        logger.error(f"❌ Failed to initialize Health Monitor: {e}")

    # WebSocket Redis Listener
    try:
        logger.info("🔌 Starting WebSocket Redis Listener...")
        redis_task = asyncio.create_task(redis_listener())
        app.state.redis_listener_task = redis_task
        service_registry.register("websocket", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ WebSocket Redis Listener started")
    except Exception as e:
        service_registry.register("websocket", ServiceStatus.DEGRADED, error=str(e), critical=False)
        logger.error(f"❌ Failed to start WebSocket Redis Listener: {e}")

    # Proactive Compliance Monitor (Business Value)
    try:
        logger.info("⚖️ Initializing Proactive Compliance Monitor...")
        # In production, we would pass the notification service here
        compliance_monitor = ProactiveComplianceMonitor(search_service=search_service)
        await compliance_monitor.start()

        app.state.compliance_monitor = compliance_monitor
        service_registry.register("compliance", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Proactive Compliance Monitor: Active")
    except Exception as e:
        service_registry.register(
            "compliance", ServiceStatus.DEGRADED, error=str(e), critical=False,
        )
        logger.error(f"❌ Failed to initialize Compliance Monitor: {e}")

    # Autonomous Scheduler (All Autonomous Agents)
    try:
        logger.info("🤖 Initializing Autonomous Scheduler...")

        autonomous_scheduler = await create_and_start_scheduler(
            db_pool=db_pool,
            ai_client=ai_client,
            search_service=search_service,
        )
        logger.info("DEBUG: Scheduler started")

        app.state.autonomous_scheduler = autonomous_scheduler
        service_registry.register("autonomous_scheduler", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Autonomous Scheduler: Active")
    except Exception as e:
        service_registry.register(
            "autonomous_scheduler", ServiceStatus.DEGRADED, error=str(e), critical=False,
        )
        logger.error(f"❌ Failed to initialize Autonomous Scheduler: {e}")



# NOTE: The Generals (CodingGeneral, IntelligenceGeneral) were removed 2026-04-03.
# backend/generals/ directory never existed — imports always failed silently.
# Their responsibilities are covered by:
#   - CodingGeneral → Core Guardian V3 (external, runs every 3h)
#   - IntelligenceGeneral → Intel Pipeline (Chain 4) + War Room
# See: docs/superpowers/specs/2026-04-03-agent-mesh-vision.md §8



async def initialize_channel_router(
    app: FastAPI,
    ai_client: Any,
    db_pool: asyncpg.Pool | None,
) -> None:
    """
    Initialize Multi-Channel Architecture (ChannelRouter + adapters).

    Registers channel adapters for Telegram, Web, WhatsApp, Instagram, and Twitter.
    Configures each adapter with appropriate settings and services.

    Args:
        app: FastAPI application instance
        ai_client: ZantaraAIClient instance (for conversation processing)
        db_pool: Database pool instance (for conversation persistence)
    """
    try:
        # Import channel components
        from backend.channels.router import ChannelRouter
        from backend.channels.telegram.adapter import TelegramChannelAdapter
        from backend.channels.web.adapter import WebChannelAdapter
        from backend.conversation.engine import ConversationEngine

        # Create orchestrator for channel router (request-scoped orchestrator in deps/orchestrator.py
        # is separate — this one is for channel adapters which don't go through FastAPI Depends)
        orchestrator = getattr(app.state, "orchestrator", None)
        if not orchestrator:
            # Create a dedicated orchestrator for channel router
            # Uses tools from tool_executor if available, otherwise empty list
            from backend.services.rag.agentic import AgenticRAGOrchestrator
            from backend.services.rag.agentic.tools import create_default_tools

            # Get retriever (search_service) and db_pool for orchestrator
            search_service = getattr(app.state, "search_service", None)
            getattr(app.state, "tool_executor", None)

            # Create tools list from ZantaraTools or use default tools
            tools = create_default_tools(search_service=search_service)

            orchestrator = AgenticRAGOrchestrator(
                tools=tools,
                db_pool=db_pool,
                retriever=search_service,
                faq_cache=getattr(app.state, "faq_cache", None),  # FAQ cache from Step 2.5
            )
            logger.info(f"✅ Fallback orchestrator created with {len(tools)} tools")

            # Eagerly initialize async components (MemoryOrchestrator, KG LangGraph)
            # to avoid first-query latency spike
            try:
                await orchestrator.initialize()
            except Exception as e:
                logger.warning(f"⚠️ Orchestrator async init failed (non-fatal): {e}")

        # Initialize ConversationEngine (bridge between channels and orchestrator)
        conversation_engine = ConversationEngine(orchestrator)
        app.state.conversation_engine = conversation_engine
        logger.info("✅ ConversationEngine initialized")

        # Initialize ChannelRouter
        channel_router = ChannelRouter(conversation_engine)
        app.state.channel_router = channel_router
        channel_router._db_pool = db_pool  # Enable conversation persistence
        conversation_engine._db_pool = db_pool  # Enable cross-channel context injection
        logger.info("✅ ChannelRouter initialized")

        # Register Telegram adapter (if configured)
        telegram_token = settings.telegram_bot_token
        if telegram_token:
            telegram_config = {
                "bot_token": telegram_token,
                "max_message_length": 4096,
                "update_interval": 1.5,
                "parse_mode": "Markdown",
            }
            telegram_adapter = TelegramChannelAdapter(telegram_config)
            channel_router.register_adapter("telegram", telegram_adapter)
            logger.info("✅ TelegramChannelAdapter registered")
        else:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not configured, Telegram adapter disabled")

        # Register Web adapter (always enabled)
        web_config = {
            "max_message_length": 100000,
            "supports_markdown": True,
            "supports_media": True,
            "stream_mode": "sse",
        }
        web_adapter = WebChannelAdapter(web_config)
        channel_router.register_adapter("web", web_adapter)
        logger.info("✅ WebChannelAdapter registered")

        # Register WhatsApp adapter (if configured)
        whatsapp_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        whatsapp_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        if whatsapp_token and whatsapp_phone_id:
            from backend.channels.whatsapp.adapter import WhatsAppChannelAdapter

            whatsapp_config = {
                "access_token": whatsapp_token,
                "phone_number_id": whatsapp_phone_id,
                "max_message_length": 1600,
            }
            whatsapp_adapter = WhatsAppChannelAdapter(whatsapp_config)
            channel_router.register_adapter("whatsapp", whatsapp_adapter)
            logger.info("✅ WhatsAppChannelAdapter registered")
        else:
            logger.warning("⚠️ WhatsApp credentials not configured, adapter disabled")

        # Register Instagram adapter (if configured)
        instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if instagram_token and instagram_account_id:
            from backend.channels.instagram.adapter import InstagramChannelAdapter

            instagram_config = {
                "access_token": instagram_token,
                "instagram_account_id": instagram_account_id,
            }
            instagram_adapter = InstagramChannelAdapter(instagram_config)
            channel_router.register_adapter("instagram", instagram_adapter)
            logger.info("✅ InstagramChannelAdapter registered")
        else:
            logger.warning("⚠️ Instagram credentials not configured, adapter disabled")

        # Twitter adapter quarantined 2026-04-30 — CRC handshake broken.
        # See apps/backend-rag/backend/channels/.disabled-2026-04-30/README.md
        # and CLAUDE.md §10 for reactivation criteria.

        # Initialize channel optimizations (rate limiter, Redis dedup, DLQ, metrics)
        from backend.channels.optimizations import delivery_manager, initialize_optimizations

        initialize_optimizations(db_pool=db_pool)

        # Start DLQ retry loop if delivery_manager has DB access
        if delivery_manager and db_pool:
            delivery_manager._db_pool = db_pool
            await delivery_manager.start_retry_loop(channel_router.adapters)
            logger.info("✅ DLQ retry loop started")

        # Register service in health monitoring
        service_registry.register("channel_router", ServiceStatus.HEALTHY, critical=False)

        # Log registered channels
        available_channels = channel_router.get_available_channels()
        logger.info(f"📡 Multi-Channel Architecture ready: {available_channels}")

    except Exception as e:
        service_registry.register(
            "channel_router", ServiceStatus.DEGRADED, error=str(e), critical=False,
        )
        logger.error(f"❌ Failed to initialize Channel Router: {e}", exc_info=True)
        app.state.channel_router_init_error = str(e)


async def initialize_services(app: FastAPI) -> None:
    """
    Initialize all ZANTARA RAG services with fail-fast for critical services.

    Critical services (SearchService, ZantaraAIClient) must initialize successfully.
    If any critical service fails, the application will raise RuntimeError to
    prevent starting in a broken state.

    Non-critical services will log errors and continue with degraded functionality.

    Args:
        app: FastAPI application instance
    """
    if getattr(app.state, "services_initialized", False):
        return

    logger.info("🚀 Initializing ZANTARA RAG services...")

    # 0. RedisManager (must be first — all Redis consumers depend on it)
    try:
        from backend.core.redis_manager import RedisManager

        redis_manager = RedisManager.get_instance()
        redis_manager.initialize()
        app.state.redis_manager = redis_manager
        logger.info(f"RedisManager initialized (available={redis_manager.available})")
    except Exception as e:
        logger.warning(f"RedisManager initialization failed: {e} — Redis features disabled")

    # 0.1 KG cache proactive invalidation listener (HIGH-13).
    # Subscribes to `zantara:kg:invalidate` and wipes local KG cache entries
    # the moment a peer cell increments the KG version. Falls back to the
    # existing lazy on-read check if Redis is down.
    try:
        from backend.services.rag.kg_cache import start_invalidation_listener

        listener = await start_invalidation_listener()
        app.state.kg_invalidate_listener = listener
        logger.info("✅ KG cache invalidation listener started")
    except Exception as e:
        logger.warning(
            "KG cache invalidation listener failed to start: %s — "
            "falling back to lazy version check only",
            e,
        )

    # 0.5 VASSAL Phase 3: ConfirmationService + ToolAuthorizer wiring.
    # Must happen after RedisManager (the service depends on it) and
    # before anything that calls execute_tool (which reads the module-level
    # authorizer and confirmation service singletons).
    try:
        from backend.services.agents.confirmation_service import ConfirmationService
        from backend.services.agents.tool_authorizer import ToolAuthorizer
        from backend.services.rag.agentic.tool_executor import configure_tool_executor

        redis_mgr = getattr(app.state, "redis_manager", None)
        confirmation_service = ConfirmationService(redis_manager=redis_mgr)
        await confirmation_service.start()
        app.state.confirmation_service = confirmation_service

        authorizer = ToolAuthorizer()
        configure_tool_executor(
            authorizer=authorizer,
            confirmation_service=confirmation_service,
        )
        logger.info(
            "✅ VASSAL Phase 3: ConfirmationService + ToolAuthorizer wired "
            "(Redis available=%s)",
            getattr(redis_mgr, "available", False),
        )
    except Exception as e:
        logger.warning(
            "⚠️ VASSAL Phase 3: ConfirmationService wiring failed: %s — "
            "confirmation gates will fail-closed (deny)",
            e,
        )

    # 1. Critical services (fail-fast)
    search_service, ai_client = await _init_critical_services(app)

    # 2. Tool stack
    tool_executor = await _init_tool_stack(app)

    # 2.5 FAQ Cache (non-critical, graceful degradation)
    await initialize_faq_cache_service(app)

    # 3. RAG components (CulturalRAGService initialized inside _init_rag_components)
    query_router = await _init_rag_components(app, search_service)
    cultural_rag_service = app.state.cultural_rag  # Already set by _init_rag_components

    # 4. Specialized agents
    (
        autonomous_research_service,
        cross_oracle_synthesis_service,
        client_journey_orchestrator,
    ) = await _init_specialized_agents(app, search_service, ai_client, query_router)

    # Store specialized agents in app.state for router access
    app.state.cross_oracle_synthesis_service = cross_oracle_synthesis_service
    app.state.autonomous_research_service = autonomous_research_service
    app.state.client_journey_orchestrator = client_journey_orchestrator

    # 5. Database services
    db_pool = await initialize_database_services(app)

    # 6. CRM & Memory
    await initialize_crm_and_memory_services(app, ai_client, db_pool)

    # 7. CollaboratorService (needed for IntelligentRouter)
    from backend.services.crm.collaborator_service import CollaboratorService

    collaborator_service = None
    try:
        collaborator_service = CollaboratorService()
        app.state.collaborator_service = collaborator_service
        logger.info("✅ CollaboratorService initialized")
    except Exception as e:
        logger.warning(f"⚠️ CollaboratorService initialization failed: {e}")
        app.state.collaborator_service = None

    # 8. Intelligent Router
    await initialize_intelligent_router(
        app,
        ai_client,
        search_service,
        tool_executor,
        cultural_rag_service,
        autonomous_research_service,
        cross_oracle_synthesis_service,
        client_journey_orchestrator,
        collaborator_service,
        db_pool,
    )

    # 9. Multi-Channel Architecture (Telegram, Web, WhatsApp, Instagram, Twitter)
    await initialize_channel_router(app, ai_client, db_pool)

    # 10. Background services (DISABLED for omnichannel stabilization)
    # await _init_background_services(app, search_service, ai_client, db_pool)

    # 11. The Generals — REMOVED (code dead, see note at line ~798)

    # 10b. Health Monitor (extracted from _init_background_services)
    try:
        from backend.services.monitoring.alert_service import AlertService
        from backend.services.monitoring.health_monitor import HealthMonitor

        alert_service = getattr(app.state, "alert_service", None)
        if alert_service is None:
            alert_service = AlertService()
            app.state.alert_service = alert_service

        health_monitor = HealthMonitor(alert_service=alert_service, check_interval=60)
        health_monitor.set_services(
            memory_service=getattr(app.state, "memory_service", None),
            intelligent_router=getattr(app.state, "intelligent_router", None),
            tool_executor=getattr(app.state, "tool_executor", None),
            app_state=app.state,
        )
        await health_monitor.start()
        app.state.health_monitor = health_monitor
        service_registry.register("health_monitor", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Health Monitor: Active (check_interval=60s)")
    except Exception as e:
        service_registry.register(
            "health_monitor", ServiceStatus.DEGRADED, error=str(e), critical=False,
        )
        logger.error(f"❌ Failed to initialize Health Monitor: {e}")

    # 10c. Olympus DB Guardian
    # Background workers kill switch (2026-04-12 incident): skip Olympus when
    # DISABLE_BACKGROUND_WORKERS=1 — Olympus heartbeat/pulse loops corrupt the
    # asyncpg pool on transient PG errors, causing ConnectionDoesNotExistError storms.
    if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
        logger.warning("⚠️ DISABLE_BACKGROUND_WORKERS=1 — skipping Olympus (full init)")
        app.state.olympus = None
    elif db_pool:
        try:
            from backend.services.olympus.guardian import OlympusGuardian

            olympus = OlympusGuardian(db_pool=db_pool, alert_service=alert_service)
            await olympus.initialize()
            await olympus.start()
            app.state.olympus = olympus
            service_registry.register("olympus", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ Olympus DB Guardian: Active (heartbeat + pulse)")
        except Exception as e:
            service_registry.register(
                "olympus", ServiceStatus.DEGRADED, error=str(e), critical=False,
            )
            logger.error(f"❌ Failed to initialize Olympus: {e}")
    else:
        logger.warning("⚠️ Olympus skipped: no db_pool")

    # 12. LangGraph Agent Layer - Inject services into workflow nodes
    logger.debug("Injecting services into LangGraph agent nodes...")
    try:
        from backend.app.agents.graph import set_db_pool, set_llm_gateway, set_search_service
        from backend.services.rag.agentic.llm_gateway import LLMGateway

        # Inject SearchService (already initialized)
        if search_service:
            set_search_service(search_service)
            logger.info("✅ SearchService injected into LangGraph agent nodes")
        else:
            logger.warning("⚠️ SearchService not available for LangGraph agent injection")

        # Inject DB pool for conversation history
        if db_pool:
            set_db_pool(db_pool)
            logger.info("✅ DB pool injected into LangGraph agent nodes (conversation history)")

        # Create and inject LLMGateway
        try:
            llm_gateway = LLMGateway()
            set_llm_gateway(llm_gateway)
            logger.info("✅ LLMGateway created and injected into LangGraph agent nodes")
        except Exception as llm_error:
            logger.warning(f"⚠️ LLMGateway initialization failed: {llm_error}")
            logger.info("Agent workflow will use fallback mock responses")

    except Exception as e:
        logger.warning(f"⚠️ LangGraph agent service injection failed: {e}")
        logger.info("Agent workflow will continue with fallback behavior")

    # 13. NLM Enrichment Service (feature-flagged, non-critical)
    nlm_enrichment_enabled = os.getenv("ENABLE_NLM_ENRICHMENT", "false").lower() in (
        "true",
        "1",
    )
    if nlm_enrichment_enabled:
        try:
            from backend.services.oracle.nlm_enrichment_service import (
                NLMEnrichmentService,
            )

            nlm_service = NLMEnrichmentService(
                bridge_url=os.getenv("NLM_BRIDGE_URL", "http://100.107.22.111:18790"),
                bridge_secret=os.getenv("NLM_BRIDGE_SECRET", ""),
            )
            app.state.nlm_enrichment_service = nlm_service
            service_registry.register("nlm_enrichment", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ NLM Enrichment Service initialized (ENABLE_NLM_ENRICHMENT=true)")
        except Exception as e:
            app.state.nlm_enrichment_service = None
            service_registry.register(
                "nlm_enrichment",
                ServiceStatus.DEGRADED,
                error=str(e),
                critical=False,
            )
            logger.warning(f"⚠️ NLM Enrichment Service initialization failed: {e}")
    else:
        app.state.nlm_enrichment_service = None
        logger.info("⚠️ NLM Enrichment Service DISABLED (set ENABLE_NLM_ENRICHMENT=true to enable)")

    # Register workflow chain executors (lazy — only imports, no heavy init)
    try:
        import backend.services.workflow.chains  # noqa: F401

        logger.info("✅ Workflow chain executors registered")
    except Exception as e:
        logger.warning(f"⚠️ Workflow chain registration failed (non-critical): {e}")

    logger.info("DEBUG: Setting services_initialized to True")
    app.state.services_initialized = True
    logger.info("✅ ZANTARA Services Initialization Complete.")
    logger.info(f"📊 Service Status: {service_registry.get_status()['overall']}")



def _clean_database_dsn(dsn: str) -> tuple[str, bool | None]:
    """
    Clean DATABASE_URL for asyncpg compatibility.

    Strips sslmode= param (asyncpg doesn't support it in DSN).
    Returns (cleaned_dsn, ssl_context) where ssl_context is False
    if sslmode=disable, None otherwise.
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(dsn)
    params = parse_qs(parsed.query)
    sslmode = params.pop("sslmode", [None])[0]
    ssl_context: bool | None = None
    if sslmode == "disable":
        ssl_context = False
    clean_query = urlencode(params, doseq=True)
    cleaned_dsn = urlunparse(parsed._replace(query=clean_query))
    return cleaned_dsn, ssl_context

async def initialize_services_light(app: FastAPI) -> None:
    """
    Light initialization for the 'api' process group.

    Initializes only DB pool + Redis cache — skips SearchService (Qdrant)
    and ZantaraAIClient (LLM warmup). Starts in <5s vs ~30s for full init.

    Args:
        app: FastAPI application instance
    """
    logger.info("🚀 [API PROCESS] Light init: DB + Redis only (skipping RAG services)")

    # 1. Database pool (CRITICAL)
    try:
        dsn, ssl_ctx = _clean_database_dsn(settings.database_url)
        async def _light_init_connection(conn):
            """Set statement timeout for api process pool connections."""
            await conn.execute("SET statement_timeout = '30s'")

        pool_kwargs: dict = {
            "dsn": dsn,
            "min_size": 2,
            "max_size": 10,
            "command_timeout": 60,
            "max_inactive_connection_lifetime": 30.0,
            "init": _light_init_connection,
            # Required for PgBouncer transaction mode — prevents prepared statement leak
            "statement_cache_size": 0,
        }
        if ssl_ctx is not None:
            pool_kwargs["ssl"] = ssl_ctx
        db_pool = await asyncpg.create_pool(**pool_kwargs)
        app.state.db_pool = db_pool
        service_registry.register("database", ServiceStatus.HEALTHY)
        logger.info("✅ DB pool initialized (light)")
    except Exception as e:
        logger.error(f"❌ DB pool failed in light init: {e}")
        service_registry.register("database", ServiceStatus.UNAVAILABLE, error=str(e))
        raise RuntimeError(f"DB pool failed in light init: {e}") from e

    # 2. Redis cache (non-critical)
    try:
        from backend.core.cache import CacheService
        cache = CacheService()
        app.state.cache = cache
        service_registry.register("cache", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Redis cache initialized (light)")
    except Exception as e:
        logger.warning(f"⚠️ Redis cache failed (non-critical): {e}")
        app.state.cache = None

    # Background workers kill switch — set DISABLE_BACKGROUND_WORKERS=1 to skip
    # all non-critical async workers that hold DB connections (incident mitigation).
    # Introduced 2026-04-12 during the disk-full + cascading pool-corruption incident
    # where Olympus Guardian's heartbeat/pulse loops poisoned the asyncpg pool by
    # retrying failed queries without pool recreation, causing ConnectionDoesNotExistError
    # storms that blocked login. Keep this flag in place as a safety switch.
    if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
        logger.warning(
            "⚠️ DISABLE_BACKGROUND_WORKERS=1 — skipping Timesheet + Olympus + other async workers",
        )
        app.state.ts_service = None
        app.state.attendance_monitor = None
        app.state.olympus = None
    else:
        # 3. Timesheet service (requires DB pool, used by team_activity router)
        try:
            from backend.services.analytics.attendance_monitor import AttendanceMonitor
            from backend.services.analytics.team_timesheet_service import init_timesheet_service
            attendance_monitor = AttendanceMonitor(db_pool)
            await attendance_monitor.start_schedulers()
            app.state.attendance_monitor = attendance_monitor
            ts_service = init_timesheet_service(db_pool, attendance_monitor=attendance_monitor)
            app.state.ts_service = ts_service
            await ts_service.start_auto_logout_monitor()
            logger.info("✅ Timesheet service initialized (light)")
        except Exception as e:
            logger.warning(f"⚠️ Timesheet service failed (non-critical): {e}")
            app.state.ts_service = None
            app.state.attendance_monitor = None

        # 4. Olympus DB Guardian (non-critical, uses only db_pool)
        try:
            from backend.services.olympus.guardian import OlympusGuardian

            olympus = OlympusGuardian(db_pool=db_pool, alert_service=None)
            await olympus.initialize()
            await olympus.start()
            app.state.olympus = olympus
            logger.info("✅ Olympus DB Guardian initialized (light)")
        except Exception as e:
            logger.warning(f"⚠️ Olympus Guardian failed (non-critical): {e}")
            app.state.olympus = None

    # 5. Mark RAG services as intentionally not-initialized (light mode)
    app.state.search_service = None
    app.state.ai_client = None
    app.state.orchestrator = None
    app.state.intelligent_router = None
    app.state.memory_service = None
    app.state.channel_router = None

    logger.info("✅ Light init complete — RAG services intentionally skipped")
