"""
Router Registration Module
Centralizes all router inclusion logic
"""

from fastapi import FastAPI

from app.modules.identity.router import router as identity_router
from app.modules.knowledge.router import router as knowledge_router
from app.routers import (
    admin_logs,
    agentic_rag,
    agents,
    analytics,
    auth,
    autonomous_agents,
    blog_ask,
    collective_memory,
    conversations,
    crm_auto,
    crm_clients,
    crm_enhanced,
    crm_interactions,
    crm_portal_integration,
    crm_practices,
    crm_shared_memory,
    dashboard_summary,
    debug,
    episodic_memory,
    feedback,
    google_drive,
    handlers,
    health,
    ingest,
    intel,
    knowledge_visa,
    legal_ingest,
    media,
    news,
    newsletter,
    nusantara_health,
    oracle_ingest,
    oracle_universal,
    performance,
    portal,
    portal_invite,
    session,
    team,
    team_activity,
    team_analytics,
    team_drive,
    telegram,
    voice,
    websocket,
    zoho_email,
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
    api.include_router(nusantara_health.router)  # Admin-only archipelago health map
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
    api.include_router(crm_enhanced.router)  # Family members, Documents, Expiry Alerts
    api.include_router(crm_interactions.router)
    api.include_router(crm_practices.router)
    api.include_router(crm_shared_memory.router)
    api.include_router(crm_auto.router)
    api.include_router(crm_portal_integration.router)  # Team ↔ Portal integration

    # Portal routers (Client-facing)
    api.include_router(portal.router)
    api.include_router(portal_invite.router)

    # Ingestion routers
    api.include_router(ingest.router)
    api.include_router(legal_ingest.router)
    api.include_router(oracle_ingest.router)

    # Intelligence & Oracle routers
    api.include_router(intel.router)
    api.include_router(oracle_universal.router)

    # Preview router (for Telegram article previews)
    from app.routers import preview

    api.include_router(preview.router)

    # Communication routers (notifications/whatsapp/instagram removed - will be MCP)
    api.include_router(websocket.router)
    api.include_router(telegram.router)  # Telegram bot integration

    # Integrations routers
    api.include_router(zoho_email.router)
    api.include_router(google_drive.router)
    api.include_router(team_drive.router)  # Service Account based - for Zoho team members

    # Blog routers
    api.include_router(newsletter.router)
    api.include_router(blog_ask.router)  # AskZantara widget on public blog articles

    # News/Intel Feed routers
    api.include_router(news.router)

    # Performance router (productivity removed - will be MCP)
    api.include_router(performance.router)

    # Module routers (Prime Standard)
    api.include_router(identity_router, prefix="/api/auth")
    api.include_router(knowledge_router)

    # Knowledge Base - Visa Types
    api.include_router(knowledge_visa.router)

    # Additional routers (included directly on app instance)
    api.include_router(team.router)  # Team member visibility management
    api.include_router(team_activity.router)
    api.include_router(team_analytics.router)
    api.include_router(media.router)
    # api.include_router(audio.router)  # Already included in app_factory.py with prefix="/api"
    api.include_router(voice.router)  # Fast voice endpoint for realtime voice AI

    # Image generation router
    from app.routers import image_generation

    api.include_router(image_generation.router)

    # Analytics router (Founder-only dashboard)
    api.include_router(analytics.router)

    # Admin Logs router (Admin-only activity logs and audit trail)
    api.include_router(admin_logs.router)

    # Dashboard aggregation router
    api.include_router(dashboard_summary.router)
