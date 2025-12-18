"""
Service Initialization Module

Handles initialization of all ZANTARA RAG services with fail-fast for critical services.

Critical services (SearchService, ZantaraAIClient) must initialize successfully.
If any critical service fails, the application will raise RuntimeError to prevent starting in a broken state.

Non-critical services will log errors and continue with degraded functionality.
"""

import asyncio
import json
import logging
from typing import Any

import asyncpg
from fastapi import FastAPI

from app.core.config import settings
from app.core.service_health import ServiceStatus, service_registry
from app.routers.websocket import redis_listener
from llm.zantara_ai_client import ZantaraAIClient
from services.alert_service import AlertService
from services.auto_crm_service import get_auto_crm_service
from services.autonomous_research_service import AutonomousResearchService
from services.autonomous_scheduler import create_and_start_scheduler
from services.client_journey_orchestrator import ClientJourneyOrchestrator
from services.collaborator_service import CollaboratorService
from services.collective_memory_workflow import create_collective_memory_workflow
from services.conversation_service import ConversationService
from services.cross_oracle_synthesis_service import CrossOracleSynthesisService
from services.cultural_rag_service import CulturalRAGService
from services.health_monitor import HealthMonitor
from services.intelligent_router import IntelligentRouter
from services.mcp_client_service import initialize_mcp_client
from services.memory_service_postgres import MemoryServicePostgres
from services.proactive_compliance_monitor import ProactiveComplianceMonitor
from services.query_router import QueryRouter
from services.search_service import SearchService
from services.tool_executor import ToolExecutor
from services.zantara_tools import ZantaraTools

logger = logging.getLogger("zantara.backend")


async def _init_critical_services(app: FastAPI) -> tuple[SearchService | None, ZantaraAIClient | None]:
    """
    Initialize critical services: SearchService and ZantaraAIClient.

    These services must initialize successfully or the application will fail to start.

    Args:
        app: FastAPI application instance

    Returns:
        Tuple of (search_service, ai_client). Both may be None if initialization failed.

    Raises:
        RuntimeError: If critical services fail to initialize
    """
    # Store service registry in app state for health endpoints
    app.state.service_registry = service_registry

    # 1. Search / Qdrant (CRITICAL)
    search_service = None
    try:
        # Initialize SearchService with dependency injection
        from services.collection_manager import CollectionManager
        from services.conflict_resolver import ConflictResolver
        from services.cultural_insights_service import CulturalInsightsService
        from services.query_router_integration import QueryRouterIntegration

        # Create shared services
        collection_manager = CollectionManager(qdrant_url=settings.qdrant_url)
        conflict_resolver = ConflictResolver()
        query_router = QueryRouterIntegration()

        # Create cultural insights service (requires embedder)
        from core.embeddings import create_embeddings_generator

        embedder = create_embeddings_generator()
        cultural_insights = CulturalInsightsService(
            collection_manager=collection_manager, embedder=embedder
        )

        # Create SearchService with dependencies
        search_service = SearchService(
            collection_manager=collection_manager,
            conflict_resolver=conflict_resolver,
            cultural_insights=cultural_insights,
            query_router=query_router,
        )

        # Store services in app state for dependency injection
        app.state.collection_manager = collection_manager
        app.state.conflict_resolver = conflict_resolver
        app.state.cultural_insights = cultural_insights
        app.state.query_router = query_router
        app.state.search_service = search_service
        service_registry.register("search", ServiceStatus.HEALTHY)
        logger.info("✅ SearchService initialized")
    except (ValueError, ConnectionError, RuntimeError) as e:
        error_msg = str(e)
        service_registry.register("search", ServiceStatus.UNAVAILABLE, error=error_msg)
        logger.error(f"❌ CRITICAL: Failed to initialize SearchService: {e}")
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = str(e)
        service_registry.register("search", ServiceStatus.UNAVAILABLE, error=error_msg)
        logger.error(
            f"❌ CRITICAL: Unexpected error initializing SearchService: {e}", exc_info=True
        )

    # 2. AI Client (CRITICAL)
    ai_client = None
    try:
        ai_client = ZantaraAIClient()
        app.state.ai_client = ai_client
        service_registry.register("ai", ServiceStatus.HEALTHY)
        logger.info("✅ ZantaraAIClient initialized")
    except (ValueError, ConnectionError, RuntimeError) as exc:
        error_msg = str(exc)
        service_registry.register("ai", ServiceStatus.UNAVAILABLE, error=error_msg)
        logger.error(f"❌ CRITICAL: Failed to initialize ZantaraAIClient: {exc}")
    except Exception as exc:
        # Catch-all for unexpected errors
        error_msg = str(exc)
        service_registry.register("ai", ServiceStatus.UNAVAILABLE, error=error_msg)
        logger.error(
            f"❌ CRITICAL: Unexpected error initializing ZantaraAIClient: {exc}", exc_info=True
        )

    # Fail-fast if critical services are unavailable
    if service_registry.has_critical_failures():
        error_msg = service_registry.format_failures_message()
        logger.critical(f"🔥 {error_msg}")
        raise RuntimeError(error_msg)

    return search_service, ai_client


async def _init_tool_stack(app: FastAPI) -> ToolExecutor:
    """
    Initialize tool stack: Python-native tools and MCP client.

    Args:
        app: FastAPI application instance

    Returns:
        ToolExecutor instance
    """
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


async def _init_rag_components(
    app: FastAPI, search_service: SearchService | None
) -> QueryRouter:
    """
    Initialize RAG components: CulturalRAGService and QueryRouter.

    Args:
        app: FastAPI application instance
        search_service: SearchService instance (may be None)

    Returns:
        QueryRouter instance
    """
    # Initialize CulturalRAGService with CulturalInsightsService
    cultural_insights_service = getattr(app.state, "cultural_insights", None)
    if cultural_insights_service:
        cultural_rag_service = CulturalRAGService(
            cultural_insights_service=cultural_insights_service
        )
    else:
        # Fallback to search_service for backward compatibility
        cultural_rag_service = CulturalRAGService(search_service=search_service)
    query_router = QueryRouter()
    service_registry.register("rag", ServiceStatus.HEALTHY, critical=False)

    app.state.query_router = query_router

    return query_router


async def _init_specialized_agents(
    app: FastAPI,
    search_service: SearchService,
    ai_client: ZantaraAIClient,
    query_router: QueryRouter,
) -> tuple[
    AutonomousResearchService | None,
    CrossOracleSynthesisService | None,
    ClientJourneyOrchestrator | None,
]:
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
            f"❌ Failed to initialize AutonomousResearchService: {e}"
        )  # nosemgrep: python-logger-credential-disclosure

    try:
        cross_oracle_synthesis_service = CrossOracleSynthesisService(
            search_service=search_service, zantara_ai_client=ai_client
        )
        logger.info("✅ CrossOracleSynthesisService initialized")
    except Exception as e:
        # Exception contains service init error, not credentials
        logger.error(
            f"❌ Failed to initialize CrossOracleSynthesisService: {e}"
        )  # nosemgrep: python-logger-credential-disclosure

    try:
        client_journey_orchestrator = ClientJourneyOrchestrator()
        logger.info("✅ ClientJourneyOrchestrator initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize ClientJourneyOrchestrator: {e}")

    return autonomous_research_service, cross_oracle_synthesis_service, client_journey_orchestrator


async def _init_database_services(app: FastAPI) -> asyncpg.Pool | None:
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
    try:
        # Create asyncpg pool for team timesheet service
        async def init_db_connection(conn):
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

        db_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            init=init_db_connection,
        )

        from services.team_timesheet_service import init_timesheet_service

        ts_service = init_timesheet_service(db_pool)
        app.state.ts_service = ts_service
        app.state.db_pool = db_pool  # Store pool for other services

        # Start background tasks
        await ts_service.start_auto_logout_monitor()
        service_registry.register("database", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Team Timesheet Service initialized with auto-logout monitor")
        return db_pool
    except (asyncpg.PostgresError, ValueError, ConnectionError) as e:
        service_registry.register(
            "database", ServiceStatus.UNAVAILABLE, error=str(e), critical=False
        )
        logger.error(f"❌ Failed to initialize Team Timesheet Service: {e}")
        app.state.ts_service = None
        app.state.db_pool = None
        app.state.db_init_error = str(e)
        return None
    except Exception as e:
        # Catch-all for unexpected errors
        service_registry.register(
            "database", ServiceStatus.UNAVAILABLE, error=str(e), critical=False
        )
        logger.error(f"❌ Unexpected error initializing database: {e}")
        app.state.ts_service = None
        app.state.db_pool = None
        app.state.db_init_error = str(e)
        return None


async def _init_crm_memory(
    app: FastAPI, ai_client: ZantaraAIClient, db_pool: asyncpg.Pool | None
) -> None:
    """
    Initialize CRM and Memory services: AutoCRM, MemoryService, ConversationService.

    Args:
        app: FastAPI application instance
        ai_client: ZantaraAIClient instance
        db_pool: Database pool instance (may be None)
    """
    try:
        # Initialize AutoCRMService with centralized database pool
        if db_pool:
            auto_crm_service = get_auto_crm_service(ai_client=ai_client, db_pool=db_pool)
            await auto_crm_service.connect()  # No-op, but kept for compatibility
            app.state.auto_crm_service = auto_crm_service
            logger.info("✅ AutoCRMService initialized with centralized database pool")
        else:
            logger.warning(
                "⚠️ Database pool not available, AutoCRMService will use dependency injection"
            )
            auto_crm_service = get_auto_crm_service(ai_client=ai_client)
            await auto_crm_service.connect()
            app.state.auto_crm_service = auto_crm_service

        # Initialize Memory Service (Postgres)
        app.state.memory_service = MemoryServicePostgres(app.state.db_pool)
        await app.state.memory_service.connect()

        # Initialize Conversation Service
        app.state.conversation_service = ConversationService(app.state.db_pool)
        logger.info("✅ Conversation Service initialized")

        # Initialize Collective Memory Workflow
        collective_memory_workflow = create_collective_memory_workflow(
            memory_service=app.state.memory_service
        )
        app.state.collective_memory_workflow = collective_memory_workflow
        service_registry.register("memory", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ CollectiveMemoryWorkflow initialized")
    except Exception as e:
        service_registry.register("memory", ServiceStatus.DEGRADED, error=str(e), critical=False)
        logger.error(f"❌ Failed to initialize CRM/Memory services: {e}")
        # Do NOT reset db_pool here, as it affects other services
        app.state.crm_init_error = str(e)


async def _init_intelligent_router(
    app: FastAPI,
    ai_client: ZantaraAIClient,
    search_service: SearchService,
    tool_executor: ToolExecutor,
    cultural_rag_service: CulturalRAGService,
    autonomous_research_service: AutonomousResearchService | None,
    cross_oracle_synthesis_service: CrossOracleSynthesisService | None,
    client_journey_orchestrator: ClientJourneyOrchestrator | None,
    collaborator_service: CollaboratorService | None,
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
        service_registry.register("router", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ IntelligentRouter initialized with full services")
    except Exception as e:
        service_registry.register("router", ServiceStatus.UNAVAILABLE, error=str(e), critical=False)
        logger.error(f"❌ Failed to initialize IntelligentRouter: {e}")
        app.state.intelligent_router = None


async def _init_background_services(
    app: FastAPI,
    search_service: SearchService,
    ai_client: ZantaraAIClient,
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
        )

        await health_monitor.start()

        app.state.health_monitor = health_monitor
        service_registry.register("health_monitor", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Health Monitor: Active (check_interval=60s)")
    except Exception as e:
        service_registry.register(
            "health_monitor", ServiceStatus.DEGRADED, error=str(e), critical=False
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
            "compliance", ServiceStatus.DEGRADED, error=str(e), critical=False
        )
        logger.error(f"❌ Failed to initialize Compliance Monitor: {e}")

    # Autonomous Scheduler (All Autonomous Agents)
    try:
        logger.info("🤖 Initializing Autonomous Scheduler...")

        autonomous_scheduler = await create_and_start_scheduler(
            db_pool=db_pool,
            ai_client=ai_client,
            search_service=search_service,
            auto_ingestion_enabled=True,  # Daily regulatory updates
            self_healing_enabled=True,  # Continuous health monitoring
            conversation_trainer_enabled=True,  # Learn from conversations
            client_value_predictor_enabled=True,  # Nurture high-value clients
            knowledge_graph_enabled=True,  # Build knowledge graphs
        )
        logger.info("DEBUG: Scheduler started")

        app.state.autonomous_scheduler = autonomous_scheduler
        service_registry.register("autonomous_scheduler", ServiceStatus.HEALTHY, critical=False)
        logger.info("✅ Autonomous Scheduler: Active (5 agents registered)")
    except Exception as e:
        service_registry.register(
            "autonomous_scheduler", ServiceStatus.DEGRADED, error=str(e), critical=False
        )
        logger.error(f"❌ Failed to initialize Autonomous Scheduler: {e}")


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

    # 1. Critical services (fail-fast)
    search_service, ai_client = await _init_critical_services(app)

    # 2. Tool stack
    tool_executor = await _init_tool_stack(app)

    # 3. RAG components
    query_router = await _init_rag_components(app, search_service)
    cultural_insights_service = getattr(app.state, "cultural_insights", None)
    if cultural_insights_service:
        cultural_rag_service = CulturalRAGService(
            cultural_insights_service=cultural_insights_service
        )
    else:
        # Fallback to search_service for backward compatibility
        cultural_rag_service = CulturalRAGService(search_service=search_service)

    # 4. Specialized agents
    autonomous_research_service, cross_oracle_synthesis_service, client_journey_orchestrator = (
        await _init_specialized_agents(app, search_service, ai_client, query_router)
    )

    # 5. Database services
    db_pool = await _init_database_services(app)

    # 6. CRM & Memory
    await _init_crm_memory(app, ai_client, db_pool)

    # 7. CollaboratorService (needed for IntelligentRouter)
    collaborator_service = None
    try:
        collaborator_service = CollaboratorService()
        app.state.collaborator_service = collaborator_service
        logger.info("✅ CollaboratorService initialized")
    except Exception as e:
        logger.warning(f"⚠️ CollaboratorService initialization failed: {e}")
        app.state.collaborator_service = None

    # 8. Intelligent Router
    await _init_intelligent_router(
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

    # 9. Background services
    await _init_background_services(app, search_service, ai_client, db_pool)

    logger.info("DEBUG: Setting services_initialized to True")
    app.state.services_initialized = True
    logger.info("✅ ZANTARA Services Initialization Complete.")
    logger.info(f"📊 Service Status: {service_registry.get_status()['overall']}")

