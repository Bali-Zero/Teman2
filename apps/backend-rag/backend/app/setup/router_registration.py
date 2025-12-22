"""
Router Registration Module
Centralizes all router inclusion logic
"""

from fastapi import FastAPI

from app.modules.identity.router import router as identity_router
from app.modules.knowledge.router import router as knowledge_router
from app.routers import (
    agentic_rag,
    agents,
    auth,
    autonomous_agents,
    collective_memory,
    conversations,
    crm_clients,
    crm_interactions,
    crm_practices,
    crm_shared_memory,
    debug,
    episodic_memory,
    feedback,
    handlers,
    health,
    ingest,
    intel,
    legal_ingest,
    media,
    oracle_ingest,
    oracle_universal,
    performance,
    session,
    team_activity,
    team_analytics,
    websocket,
)

# NOTE: Removed routers (will be MCP):
# - productivity (Gmail/Calendar)
# - notifications (Email/SMS/Slack/Discord)
# - whatsapp (Meta WhatsApp)
# - instagram (Meta Instagram)


def include_routers(api: FastAPI) -> None:
    """
    Include all API routers - Prime Standard modular structure

    Args:
        api: FastAPI application instance
    """
    # Core routers
    api.include_router(auth.router)
    api.include_router(health.router)
    api.include_router(handlers.router)

    # Debug router (dev/staging always, production only if ADMIN_API_KEY is set)
    from app.core.config import settings

    if settings.environment.lower() != "production" or settings.admin_api_key:
        api.include_router(debug.router)
        # Include v1 debug endpoints for backward compatibility
        api.include_router(debug.v1_router)

    # Agent routers
    api.include_router(agents.router)
    api.include_router(autonomous_agents.router)
    api.include_router(agentic_rag.router)

    # Conversation & Memory routers
    api.include_router(conversations.router)
    api.include_router(session.router)
    api.include_router(collective_memory.router)
    api.include_router(episodic_memory.router)
    api.include_router(feedback.router)

    # CRM routers
    api.include_router(crm_clients.router)
    api.include_router(crm_interactions.router)
    api.include_router(crm_practices.router)
    api.include_router(crm_shared_memory.router)

    # Ingestion routers
    api.include_router(ingest.router)
    api.include_router(legal_ingest.router)
    api.include_router(oracle_ingest.router)

    # Intelligence & Oracle routers
    api.include_router(intel.router)
    api.include_router(oracle_universal.router)

    # Communication routers (notifications/whatsapp/instagram removed - will be MCP)
    api.include_router(websocket.router)

    # Performance router (productivity removed - will be MCP)
    api.include_router(performance.router)

    # Module routers (Prime Standard)
    api.include_router(identity_router, prefix="/api/auth")
    api.include_router(knowledge_router)

    # Additional routers (included directly on app instance)
    api.include_router(team_activity.router)
    api.include_router(team_analytics.router)
    api.include_router(media.router)

    # Image generation router
    from app.routers import image_generation

    api.include_router(image_generation.router)
