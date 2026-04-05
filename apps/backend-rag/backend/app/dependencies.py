"""
FastAPI Dependency Injection — Backward-Compatible Re-Export Hub

This module re-exports all dependencies from backend.app.deps sub-modules.
ALL routers continue to import from here without any changes.

Sub-modules (do not import directly in routers — use this module):
- backend.app.deps.auth        → auth + RBAC dependencies
- backend.app.deps.database    → asyncpg pool dependencies
- backend.app.deps.services    → service locator dependencies
- backend.app.deps.orchestrator → AgenticRAG orchestrator

ARCHITECTURE:
- Services are initialized in app.setup.service_initializer::initialize_services()
- Services are stored in app.state (FastAPI standard)
- This module provides getter functions that routers can use via Depends()

PATTERN:
- All dependencies use Request object to access app.state
- This allows easy mocking in tests
- Fail-fast: raises HTTPException if service not initialized

See: app.setup.service_initializer::initialize_services() for initialization logic
"""

# ============================================================================
# AUTH DEPENDENCIES
# ============================================================================
from backend.app.deps.auth import (
    get_current_portal_client,
    get_current_user,
    get_current_user_email,
    get_current_user_optional,
    require_team_member,
    security,
)

# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================
from backend.app.deps.database import (
    get_database,
    get_database_pool,
    get_db,
    get_optional_database_pool,
)

# ============================================================================
# SERVICE LOCATOR DEPENDENCIES
# ============================================================================
from backend.app.deps.services import (
    get_ai_client,
    get_cache,
    get_channel_router,
    get_intelligent_router,
    get_memory_service,
    get_retriever,
    get_search_service,
)

# ============================================================================
# ORCHESTRATOR DEPENDENCIES
# ============================================================================
from backend.app.deps.orchestrator import (
    _agentic_rag_orchestrator,
    get_orchestrator,
)

__all__ = [
    # auth
    "security",
    "get_current_user",
    "get_current_user_optional",
    "get_current_user_email",
    "require_team_member",
    "get_current_portal_client",
    # database
    "get_database_pool",
    "get_database",
    "get_db",
    "get_optional_database_pool",
    # services
    "get_search_service",
    "get_ai_client",
    "get_intelligent_router",
    "get_memory_service",
    "get_cache",
    "get_retriever",
    "get_channel_router",
    # orchestrator
    "get_orchestrator",
    "_agentic_rag_orchestrator",
]
