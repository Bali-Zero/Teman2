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
# _agentic_rag_orchestrator is a mutable global in orchestrator.py.
# We expose it as a module-level __getattr__ so that consumers like health.py
# who do `from backend.app.dependencies import _agentic_rag_orchestrator`
# always get the current value from the source module (not a stale snapshot).
import backend.app.deps.orchestrator as _orch_mod  # noqa: E402
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
# ORCHESTRATOR DEPENDENCIES
# ============================================================================
from backend.app.deps.orchestrator import get_orchestrator
from backend.app.deps.owner import OWNER_EMAILS, require_owner

# ============================================================================
# SERVICE LOCATOR DEPENDENCIES
# ============================================================================
from backend.app.deps.services import (
    get_ai_client,
    get_cache,
    get_channel_router,
    get_intelligent_router,
    get_memory_service,
    get_search_service,
)


def __getattr__(name: str):
    if name == "_agentic_rag_orchestrator":
        return _orch_mod._agentic_rag_orchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # auth
    "security",
    "get_current_user",
    "get_current_user_optional",
    "get_current_user_email",
    "require_team_member",
    "require_owner",
    "OWNER_EMAILS",
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
    "get_channel_router",
    # orchestrator
    "get_orchestrator",
    "_agentic_rag_orchestrator",  # noqa: F822  (resolved via module __getattr__ above)
]
