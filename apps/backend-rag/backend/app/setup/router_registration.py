"""
Router Registration Module
Centralizes all router inclusion logic.

All router imports are lazy (inside include_routers) to speed up module load time.
This is critical for Fly.io health checks - the server must start listening within 60s.
"""

from fastapi import FastAPI


def include_routers(api: FastAPI) -> None:
    """
    Include all API routers - Prime Standard modular structure.

    All imports are done inside this function (lazy loading) to avoid
    loading heavy dependencies (torch, sentence-transformers, etc.)
    at module import time.

    Args:
        api: FastAPI application instance
    """
    from backend.app.modules.identity.router import router as identity_router
    from backend.app.modules.knowledge.router import router as knowledge_router
    from backend.app.routers import (
        admin_conversation_cleanup,
        admin_logs,
        admin_team_activity,
        agent,  # [NEW] LangGraph agentic layer
        agentic_rag,
        agents,
        analytics,
        article_composer,
        auth,
        autonomous_agents,
        autonomous_execution,
        blog_ask,
        cell_status,  # [CELL] CELL organism dashboard status
        collective_memory,
        conversations,
        crm_analytics,  # [NEW] CRM Analytics dashboard
        crm_clients,
        crm_clients_documents,
        crm_company,  # [NEW] Company-Centric CRM
        crm_enhanced,
        crm_enhanced_alerts,
        crm_enhanced_documents,
        crm_interactions,
        crm_notifications,
        crm_portal_integration,
        crm_practices,
        crm_shared_memory,
        dashboard,  # [NEW] Interactive dashboard for Streamlit zoning map
        dashboard_featured_articles,
        dashboard_summary,
        debug,
        documents_proxy,
        dream,
        dynamic_pricing,  # [NEW] Dynamic scenario pricing
        episodic_memory,
        event_bus,  # [EVENT] EventBus monitoring
        federation,
        feedback,
        google_drive,
        handlers,
        health,
        hr,  # [NEW] HR/Payroll module
        ingest,
        instagram_chat,
        intel,
        intel_analytics,
        intel_scraper,
        kbli_notebook,
        kbli_notebook_chat,
        kg_agentic,
        knowledge_activity,
        knowledge_visa,
        lam_memory,  # [LAM] Episodic memory for agent layer
        legal_ingest,
        lkpm,
        media,
        messaging_identity,
        monitoring_rag,  # [NEW] RAG Retrieval Quality Monitoring
        naga,  # [NAGA] Deep research engine
        news,
        newsletter,
        nusantara_health,
        oracle_ingest,
        oracle_universal,
        performance,
        portal,
        portal_billing,
        portal_drive,
        portal_invite,
        portal_notifications,
        portal_process_timeline,
        portal_taxes,
        portal_visa,
        prime,
        query_analytics,
        session,
        sheets,
        team,
        team_activity,
        team_analytics,
        team_drive,
        team_members,
        telegram,
        telegram_webhook,
        twitter,
        voice,
        webhooks,
        websocket,
        whatsapp_chat,
        whatsapp_conversations,
        workflow_analytics,
        workflow_queue,
        x_monitor,
        zoho_email,
    )

    # Core routers
    api.include_router(auth.router)
    api.include_router(health.router)
    api.include_router(nusantara_health.router)  # Admin-only archipelago health map
    api.include_router(handlers.router)

    # Debug router (dev/staging always, production only if ADMIN_API_KEY is set)
    from backend.app.core.config import settings

    if settings.environment.lower() != "production" or settings.admin_api_key:
        api.include_router(debug.router)
        # Include v1 debug endpoints for backward compatibility
        api.include_router(debug.v1_router)

    # Agent routers
    api.include_router(agent.router)  # [NEW] LangGraph agentic layer
    api.include_router(lam_memory.router)  # [LAM] Episodic memory
    api.include_router(agents.router)
    api.include_router(autonomous_agents.router)
    api.include_router(autonomous_execution.router)  # Phase 7 POC: Autonomous task execution
    api.include_router(agentic_rag.router)
    api.include_router(kg_agentic.router)

    # Conversation & Memory routers
    api.include_router(conversations.router)
    api.include_router(session.router)
    api.include_router(collective_memory.router)
    api.include_router(episodic_memory.router)
    api.include_router(federation.router)
    api.include_router(feedback.router)

    # CRM routers
    api.include_router(crm_clients.router)
    api.include_router(crm_clients_documents.router)
    api.include_router(crm_company.router)  # [NEW] Company-Centric CRM
    api.include_router(crm_enhanced.router)
    api.include_router(crm_enhanced_documents.router)
    api.include_router(crm_enhanced_alerts.router)
    api.include_router(crm_interactions.router)
    api.include_router(crm_notifications.router)
    api.include_router(crm_practices.router)
    api.include_router(crm_shared_memory.router)
    api.include_router(crm_analytics.router)  # [NEW] CRM Analytics dashboard
    api.include_router(crm_portal_integration.router)  # Team ↔ Portal integration

    # HR/Payroll router
    api.include_router(hr.router)  # [NEW] HR/Payroll module

    # Notification router (Automated email alerts)
    from backend.app.modules.notifications.router import router as notifications_router

    api.include_router(notifications_router)

    # Cron notifiers (visa expiry, unpaid invoices, stale practices)
    from backend.app.routers.cron_notifiers import router as cron_notifiers_router

    api.include_router(cron_notifiers_router)

    # Portal routers (Client-facing)
    api.include_router(portal.router)
    api.include_router(portal_billing.router)
    api.include_router(portal_drive.router)
    api.include_router(portal_invite.router)
    api.include_router(portal_notifications.router)
    api.include_router(portal_process_timeline.router)
    api.include_router(portal_taxes.router)
    api.include_router(portal_visa.router)

    # Compliance routers
    api.include_router(lkpm.router)  # LKPM Investment Activity Reports

    # Analytics routers (Admin/reporting)
    api.include_router(analytics.router)

    # Ingestion routers
    api.include_router(ingest.router)
    api.include_router(legal_ingest.router)
    api.include_router(oracle_ingest.router)

    # Naga deep research engine
    api.include_router(naga.router)

    # Intelligence & Oracle routers
    api.include_router(intel.router)
    api.include_router(intel_scraper.router)
    api.include_router(intel_analytics.router)
    api.include_router(oracle_universal.router)
    api.include_router(
        kbli_notebook.router, prefix=settings.API_V1_STR,
    )  # [NEW] KBLI 2025 Notebook Explorer
    api.include_router(
        kbli_notebook_chat.router, prefix=settings.API_V1_STR,
    )

    # Preview router (for Telegram article previews)
    from backend.app.routers import preview

    api.include_router(preview.router)

    # Communication routers (notifications removed - will be MCP)
    api.include_router(websocket.router)
    api.include_router(telegram.router)  # Telegram bot integration (query endpoints)
    api.include_router(
        telegram_webhook.router,
    )  # [NEW] Telegram webhook (multi-channel architecture)
    api.include_router(twitter.router)  # Twitter/X omnichannel API
    api.include_router(twitter.webhook_router)  # X/Twitter Account Activity webhook
    api.include_router(x_monitor.router)  # X/Twitter social listening monitor
    api.include_router(
        whatsapp_chat.router,
    )  # WhatsApp Cloud API with intelligent triage (Gemini 3 Flash + Zan v2)
    # api.include_router(whatsapp_chat.alias_router)  # ❌ DISABLED - Legacy alias causes duplicate responses
    api.include_router(
        whatsapp_conversations.router,
    )  # Omnichannel WhatsApp conversations API (dashboard only)
    api.include_router(instagram_chat.router)  # Instagram DM auto-reply via RAG
    api.include_router(instagram_chat.webhook_router)  # [NEW] Instagram webhook
    api.include_router(webhooks.router)  # External webhooks (OpenClaw, etc.)
    api.include_router(
        messaging_identity.router,
    )  # Admin: Manage phone/telegram → team_member mappings

    # Integrations routers
    api.include_router(zoho_email.router)
    api.include_router(google_drive.router)
    api.include_router(documents_proxy.router)  # Proxy Drive files without Google branding
    api.include_router(team_drive.router)  # Service Account based - for Zoho team members
    api.include_router(sheets.router)  # Google Sheets read/write via SA

    # Admin Drive Auth (for system user OAuth)
    from backend.app.routers import (
        admin_drive_auth,
        admin_drive_health,
        admin_drive_refresh,
        admin_drive_setup,
        admin_zoho_auth,
    )

    api.include_router(admin_drive_auth.router)
    api.include_router(admin_drive_health.router)
    api.include_router(admin_drive_refresh.router)
    api.include_router(admin_drive_setup.router)
    api.include_router(admin_zoho_auth.router)

    # Blog routers
    api.include_router(newsletter.router)
    api.include_router(blog_ask.router)  # AskZantara widget on public blog articles
    api.include_router(article_composer.router)  # Manual article creation with enrichment

    # News/Intel Feed routers
    api.include_router(news.router)

    # Performance router (productivity removed - will be MCP)
    api.include_router(performance.router)
    api.include_router(prime.router)

    # Dynamic scenario pricing
    api.include_router(dynamic_pricing.router)

    # Module routers (Prime Standard)
    api.include_router(dream.router)  # [NEW] Dream Room
    api.include_router(identity_router, prefix="/api/auth")
    api.include_router(knowledge_router)

    # Knowledge Base - Visa Types
    api.include_router(knowledge_visa.router)

    # Knowledge Activity Tracking
    api.include_router(knowledge_activity.router)

    # Additional routers (included directly on app instance)
    api.include_router(team.router)  # Team member visibility management
    api.include_router(team_activity.router)
    api.include_router(team_analytics.router)
    api.include_router(team_members.router)  # [NEW] Team members list for CRM dropdowns
    api.include_router(media.router)
    # api.include_router(audio.router)  # Already included in app_factory.py with prefix="/api"
    api.include_router(voice.router)  # Fast voice endpoint for realtime voice AI

    # Image generation router
    from backend.app.routers import image_generation

    api.include_router(image_generation.router)

    # Query Analytics router (RAG query insights dashboard)
    api.include_router(query_analytics.router)

    # Workflow Analytics router (LangGraph workflow tracking & feedback)
    api.include_router(workflow_analytics.router)

    # Workflow Queue router (PG SKIP LOCKED job queue + LangGraph resume)
    api.include_router(workflow_queue.router)

    # RAG Monitoring router (Retrieval quality metrics and alerts)
    api.include_router(monitoring_rag.router)

    # Admin Conversation Cleanup router
    api.include_router(admin_conversation_cleanup.router)

    # Admin Logs router (Admin-only activity logs and audit trail)
    api.include_router(admin_logs.router)

    # Admin Team Activity router (Complete team activity dashboard)
    api.include_router(admin_team_activity.router)

    # Dashboard aggregation routers
    api.include_router(dashboard.router)  # [NEW] Interactive map dashboard for Streamlit
    api.include_router(dashboard_featured_articles.router)
    api.include_router(dashboard_summary.router)

    # CELL organism dashboard
    api.include_router(cell_status.router)

    # EventBus monitoring
    api.include_router(event_bus.router)
