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
        admin_practice_auto_create,
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
        bridge,  # [BRIDGE] Pro<->Fly bidirectional bridge
        cell_status,  # [CELL] CELL organism dashboard status
        channel_health,  # [HEARTBEAT] Sprint 1.B 2026-05-02 — Cell-side bridge
        channels,  # Channel health, DLQ, unified conversations
        collective_memory,
        conversations,
        crm_analytics,  # [NEW] CRM Analytics dashboard
        crm_clients,
        crm_clients_documents,
        crm_company,  # [NEW] Company-Centric CRM
        crm_enhanced,
        crm_enhanced_alerts,
        crm_enhanced_documents,
        crm_intelligence,
        crm_interactions,
        crm_notifications,
        crm_portal_integration,
        crm_practices,
        crm_shared_memory,
        crm_tax_pilot,
        dashboard,  # [NEW] Interactive dashboard for Streamlit zoning map
        dashboard_featured_articles,
        dashboard_summary,
        debug,
        documents_proxy,
        dream,
        dynamic_pricing,  # [NEW] Dynamic scenario pricing
        episodic_memory,
        event_bus,  # [EVENT] EventBus monitoring
        experience,  # [EXP] Experience Library — trajectory recording/query
        federation,
        feedback,
        funnel,  # [FUNNEL] Cross-funnel lead tracking (v2-foundation)
        funnel_email,  # [4APPS] Drip email scheduler + unsubscribe (homepage apps)
        google_drive,
        handlers,
        health,
        hr,  # [NEW] HR/Payroll module
        hr_late_reply,  # [NEW] Late check-in reply form (token-auth, public)
        hr_owner_cashout,  # [NEW] Owner-only weekly cashout
        ingest,
        instagram_chat,
        intel_lake,
        kbli_notebook,
        kbli_notebook_chat,
        kg_agentic,
        knowledge_activity,
        knowledge_visa,
        lam_memory,  # [LAM] Episodic memory for agent layer
        lead_capture,  # [4APPS] POST /api/lead/capture — homepage → WhatsApp handoff
        legal_ingest,
        lkpm,
        media,
        messaging_identity,
        metabolic_health,  # [METABOLIC] SYMBIOSIS Pillar 7 — 4 metabolic metrics (read-only)
        monitoring_rag,  # [NEW] RAG Retrieval Quality Monitoring
        naga,  # [NAGA] Deep research engine
        news,
        newsletter,
        nusantara_health,
        observed_shell,  # [OBSERVED-SHELL] Sprint 1 PR-1.2 — cell-core observability bridge
        olympus,  # [OLYMPUS] DB Guardian health + internal management
        omnichannel,  # [NEW] Unified inbox for cross-channel conversations
        oracle_ingest,
        oracle_universal,
        performance,
        portal,
        portal_admin,
        portal_billing,
        portal_drive,
        portal_invite,
        portal_matters,
        portal_notifications,
        portal_process_timeline,
        portal_taxes,
        portal_visa,
        prime,
        prime_v2,  # [PRIME NEXUS] Layered geospatial intelligence API
        query_analytics,
        session,
        sheets,
        skill,  # [SKILL] Skill Registry — canonical procedures (Sprint 5.2 W3-4)
        team,
        team_activity,
        team_analytics,
        team_drive,
        # team_members,  # DISABLED: duplicates team.py /members endpoint (audit 2026-04-03)
        telegram,
        telegram_webhook,
        twitter,  # RE-ENABLED 2026-04-29 (P0-6 zero-crash audit) — CRC was actually working
        visa_check,  # [4APPS] Homepage Visa Check app (Clock + Match branches)
        visa_oracle,
        voice,
        webhooks,
        websocket,
        whatsapp_chat,
        whatsapp_conversations,
        workflow_analytics,
        workflow_queue,
        zoho_email,
    )

    # Core routers
    api.include_router(auth.router)
    api.include_router(health.router)
    api.include_router(nusantara_health.router)  # Admin-only archipelago health map
    # [OLYMPUS] /health/db is now in health.py; internal routes remain separate
    api.include_router(olympus.internal_router)  # [OLYMPUS] /internal/olympus/*
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
    api.include_router(experience.router)  # [EXP] Experience Library
    api.include_router(skill.router)  # [SKILL] Skill Registry
    api.include_router(metabolic_health.router)  # [METABOLIC] SYMBIOSIS Pillar 7 — read-only metrics
    api.include_router(federation.router)
    api.include_router(feedback.router)
    api.include_router(funnel.router)  # [FUNNEL] Cross-funnel lead tracking (v2-foundation)

    # [4APPS] Homepage apps (Visa Check first; kbli/tax/zoning to follow)
    api.include_router(lead_capture.router)  # POST /api/lead/capture
    api.include_router(visa_check.router)  # /api/visa/check|clock|match (Clock + Match branches)
    api.include_router(funnel_email.router)  # /api/funnel_email (drip + unsubscribe)

    # CRM routers
    api.include_router(crm_clients.router)
    api.include_router(crm_clients_documents.router)
    api.include_router(crm_company.router)  # [NEW] Company-Centric CRM
    api.include_router(crm_enhanced.router)
    api.include_router(crm_enhanced_documents.router)
    api.include_router(crm_enhanced_alerts.router)
    api.include_router(crm_intelligence.router)
    api.include_router(crm_interactions.router)
    api.include_router(crm_notifications.router)
    api.include_router(crm_practices.router)
    api.include_router(crm_shared_memory.router)
    api.include_router(crm_tax_pilot.router)
    api.include_router(crm_analytics.router)  # [NEW] CRM Analytics dashboard
    api.include_router(crm_portal_integration.router)  # Team ↔ Portal integration

    # Channel system + Omnichannel router (unified inbox)
    api.include_router(channel_health.router)  # /api/channels/{name}/health Cell heartbeat bridge
    api.include_router(channels.router)  # Channel health, DLQ, unified conversations
    api.include_router(omnichannel.router)  # [NEW] Unified inbox threads API
    api.include_router(observed_shell.router)  # /api/observed-shell/emit (Sprint 1 PR-1.2)

    # HR/Payroll router
    api.include_router(hr.router)  # [NEW] HR/Payroll module
    api.include_router(hr_late_reply.router)  # [NEW] Late check-in reply form
    api.include_router(hr_owner_cashout.router)  # [NEW] Owner weekly cashout

    # Notification router (Automated email alerts)
    from backend.app.modules.notifications.router import router as notifications_router

    api.include_router(notifications_router)

    # Cron notifiers (visa expiry, unpaid invoices, stale practices)
    from backend.app.routers.cron_notifiers import router as cron_notifiers_router

    api.include_router(cron_notifiers_router)

    # Portal routers (Client-facing)
    api.include_router(portal.router)
    api.include_router(portal_admin.router)  # superuser impersonation support
    api.include_router(portal_billing.router)
    api.include_router(portal_drive.router)
    api.include_router(portal_invite.router)
    api.include_router(portal_matters.router)
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
    # RE-ENABLED 2026-04-29 (P0-6 zero-crash audit). The CRC handshake at
    # backend/app/routers/twitter.py was actually correct; the disable from
    # 2026-04-03 was conservative. Now lives behind the ack-first
    # persistence layer (services/channels/inbound_webhook_repo.py) so any
    # handler exception lands in inbound_webhooks for the WebhookProcessor
    # to retry.
    api.include_router(twitter.router)
    api.include_router(twitter.webhook_router)
    api.include_router(
        whatsapp_chat.router,
    )  # WhatsApp Cloud API with intelligent triage (Gemini 3 Flash + Zan v2)
    # api.include_router(whatsapp_chat.alias_router)  # ❌ DISABLED - Legacy alias causes duplicate responses
    api.include_router(
        whatsapp_conversations.router,
    )  # Omnichannel WhatsApp conversations API (dashboard only)
    api.include_router(instagram_chat.router)  # Instagram DM auto-reply via RAG
    api.include_router(instagram_chat.webhook_router)  # [NEW] Instagram webhook
    api.include_router(intel_lake.router)  # Intel Lake Wave 1 ingest (mig 168)
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
        admin_crm_kg,
        admin_drive_auth,
        admin_drive_health,
        admin_drive_refresh,
        admin_drive_setup,
        admin_zoho_auth,
    )

    api.include_router(admin_crm_kg.router)
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
    api.include_router(prime_v2.router)  # [PRIME NEXUS] v2 layered API

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
    # api.include_router(team_members.router)  # DISABLED: duplicates team.py (audit 2026-04-03)
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

    # Admin Auto Practice Creator (visa renewal at T-60)
    api.include_router(admin_practice_auto_create.router)

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

    # Bridge — Pro<->Fly bidirectional event bridge
    api.include_router(bridge.router)

    # Guardian V4 decision audit + risk scores
    # from backend.app.routers import guardian
    # api.include_router(guardian.router)

    # Visa Oracle — public product (no auth required)
    api.include_router(visa_oracle.router, prefix=settings.API_V1_STR)


def include_light_routers(api: FastAPI) -> None:
    """
    Include only LIGHT routers (DB + auth only, no RAG/ML dependencies).

    Used by the light process split — starts fast, no torch/sentence-transformers.
    All imports are lazy (inside function body) matching the existing pattern.

    Args:
        api: FastAPI application instance
    """
    from backend.app.routers import (
        admin_conversation_cleanup,
        admin_crm_kg,
        admin_drive_auth,
        admin_drive_health,
        admin_drive_refresh,
        admin_drive_setup,
        admin_logs,
        admin_practice_auto_create,
        admin_team_activity,
        admin_zoho_auth,
        analytics,
        article_composer,
        auth,
        bridge,  # [BRIDGE] Pro<->Fly bidirectional bridge (Phase 1 Sinapsi)
        cell_status,
        channel_health,  # [HEARTBEAT] Sprint 1.B 2026-05-02 — Cell-side bridge
        channels,  # Channel health, DLQ, unified conversations
        crm_analytics,
        crm_clients_documents,
        crm_company,
        crm_enhanced_alerts,
        crm_enhanced_documents,
        crm_intelligence,
        crm_interactions,
        crm_notifications,
        crm_portal_integration,
        crm_shared_memory,
        crm_tax_pilot,
        debug,
        documents_proxy,
        event_bus,
        experience,  # [EXP] Experience Library — trajectory recording/query (PR #54)
        federation,
        feedback,
        funnel,  # [FUNNEL] Cross-funnel lead tracking (v2-foundation)
        funnel_email,  # [4APPS] Drip email scheduler + unsubscribe (homepage apps)
        google_drive,
        handlers,
        health,
        hr,
        hr_late_reply,
        hr_owner_cashout,
        image_generation,
        instagram_chat,
        intel_lake,
        knowledge_activity,
        lead_capture,  # [4APPS] POST /api/lead/capture — homepage → WhatsApp handoff
        lkpm,
        media,
        messaging_identity,
        metabolic_health,  # [METABOLIC] SYMBIOSIS Pillar 7 read-only metrics (PR #60)
        newsletter,
        nusantara_health,
        observed_shell,  # [OBSERVED-SHELL] Sprint 1 PR-1.2 — cell-core observability bridge
        omnichannel,
        partners,  # [PARTNERS] CRM Partners module v1 (PR #141 + follow-ups)
        performance,
        portal,
        portal_admin,
        portal_billing,
        portal_drive,
        portal_invite,
        portal_matters,
        portal_notifications,
        portal_process_timeline,
        portal_taxes,
        portal_visa,
        prime,
        prime_v2,
        query_analytics,
        session,
        sheets,
        skill,  # [SKILL] Skill Registry — canonical procedures (PR #55)
        team,
        team_activity,
        team_analytics,
        team_drive,
        team_members,
        telegram,
        telegram_webhook,
        twitter,  # RE-ENABLED 2026-04-29 (P0-6 zero-crash audit) — CRC was actually working
        visa_check,  # [4APPS] Homepage Visa Check app (Clock + Match branches)
        visa_oracle,
        webhooks,
        websocket,
        whatsapp_conversations,
        workflow_analytics,
        workflow_queue,
        zoho_email,
    )

    # Core routers
    api.include_router(auth.router)
    api.include_router(health.router)
    api.include_router(nusantara_health.router)
    api.include_router(handlers.router)

    # Debug router (dev/staging always, production only if ADMIN_API_KEY is set)
    from backend.app.core.config import settings

    if settings.environment.lower() != "production" or settings.admin_api_key:
        api.include_router(debug.router)
        api.include_router(debug.v1_router)

    # Conversation & Memory (light subset)
    api.include_router(session.router)
    api.include_router(federation.router)
    api.include_router(feedback.router)
    api.include_router(funnel.router)  # [FUNNEL] Cross-funnel lead tracking (v2-foundation)

    # [4APPS] Homepage apps (Visa Check first; kbli/tax/zoning to follow) — PROD
    api.include_router(lead_capture.router)  # POST /api/lead/capture
    api.include_router(visa_check.router)  # /api/visa/check|clock|match (Clock + Match branches)
    api.include_router(funnel_email.router)  # /api/funnel_email (drip + unsubscribe)

    # Genome-backed registries (light: SQLite via cell-core, no ML deps)
    api.include_router(experience.router)  # [EXP] Experience Library (PR #54)
    api.include_router(skill.router)  # [SKILL] Skill Registry (PR #55)
    api.include_router(metabolic_health.router)  # [METABOLIC] SYMBIOSIS Pillar 7 (PR #60)

    # CRM routers (light — DB + auth only)
    api.include_router(crm_clients_documents.router)
    api.include_router(crm_company.router)
    api.include_router(crm_enhanced_documents.router)
    api.include_router(crm_enhanced_alerts.router)
    api.include_router(crm_intelligence.router)
    api.include_router(crm_interactions.router)
    api.include_router(crm_notifications.router)
    api.include_router(crm_shared_memory.router)
    api.include_router(crm_tax_pilot.router)
    api.include_router(crm_analytics.router)
    api.include_router(crm_portal_integration.router)
    api.include_router(partners.router)  # [PARTNERS] /api/partners/* — CRM Partners module

    # Channel system + Omnichannel router (unified inbox)
    api.include_router(channel_health.router)  # /api/channels/{name}/health Cell heartbeat bridge
    api.include_router(channels.router)  # /api/channels (health, DLQ, conversations)
    api.include_router(omnichannel.router)  # /api/omnichannel (threads, assignment)
    api.include_router(observed_shell.router)  # /api/observed-shell/emit (Sprint 1 PR-1.2)

    # HR/Payroll router
    api.include_router(hr.router)
    api.include_router(hr_late_reply.router)
    api.include_router(hr_owner_cashout.router)  # [NEW] Owner weekly cashout

    # Notifications module router
    from backend.app.modules.notifications.router import router as notifications_router

    api.include_router(notifications_router)

    # Cron notifiers (visa expiry, unpaid invoices, stale practices)
    from backend.app.routers.cron_notifiers import router as cron_notifiers_router

    api.include_router(cron_notifiers_router)

    # Portal routers (Client-facing)
    api.include_router(portal.router)
    api.include_router(portal_admin.router)  # superuser impersonation support
    api.include_router(portal_billing.router)
    api.include_router(portal_drive.router)
    api.include_router(portal_invite.router)
    api.include_router(portal_matters.router)
    api.include_router(portal_notifications.router)
    api.include_router(portal_process_timeline.router)
    api.include_router(portal_taxes.router)
    api.include_router(portal_visa.router)

    # Compliance routers
    api.include_router(lkpm.router)

    # Analytics routers
    api.include_router(analytics.router)

    # Preview router (for Telegram article previews)
    from backend.app.routers import preview

    api.include_router(preview.router)

    # Communication routers
    api.include_router(websocket.router)
    api.include_router(telegram.router)
    api.include_router(telegram_webhook.router)
    api.include_router(twitter.router)  # P0-6 re-enabled 2026-04-29
    api.include_router(twitter.webhook_router)  # P0-6 re-enabled 2026-04-29
    api.include_router(whatsapp_conversations.router)
    api.include_router(instagram_chat.router)
    api.include_router(instagram_chat.webhook_router)
    api.include_router(webhooks.router)
    api.include_router(messaging_identity.router)

    # Integrations routers
    api.include_router(zoho_email.router)
    api.include_router(google_drive.router)
    api.include_router(documents_proxy.router)
    api.include_router(team_drive.router)
    api.include_router(sheets.router)

    # Admin Drive Auth + CRM KG
    api.include_router(admin_crm_kg.router)
    api.include_router(admin_drive_auth.router)
    api.include_router(admin_drive_health.router)
    api.include_router(admin_drive_refresh.router)
    api.include_router(admin_drive_setup.router)
    api.include_router(admin_zoho_auth.router)

    # Blog routers (light)
    api.include_router(newsletter.router)
    api.include_router(article_composer.router)

    # Performance router
    api.include_router(performance.router)
    api.include_router(prime.router)
    api.include_router(prime_v2.router)

    # Team routers
    api.include_router(team.router)
    api.include_router(team_activity.router)
    api.include_router(team_analytics.router)
    api.include_router(team_members.router)

    # Media router
    api.include_router(media.router)

    # Image generation router
    api.include_router(image_generation.router)

    # Intel Lake — Wave 1 (mig 168) unified intel pipeline ingest endpoint
    api.include_router(intel_lake.router)

    # Query Analytics router
    api.include_router(query_analytics.router)

    # Workflow Analytics router
    api.include_router(workflow_analytics.router)

    # Workflow Queue router
    api.include_router(workflow_queue.router)

    # Admin Conversation Cleanup router
    api.include_router(admin_conversation_cleanup.router)

    # Admin Auto Practice Creator (visa renewal at T-60)
    api.include_router(admin_practice_auto_create.router)

    # Admin Logs router
    api.include_router(admin_logs.router)

    # Admin Team Activity router
    api.include_router(admin_team_activity.router)

    # dashboard_featured_articles moved to heavy routers (shares /api/dashboard prefix)

    # CELL organism dashboard
    api.include_router(cell_status.router)

    # EventBus monitoring
    api.include_router(event_bus.router)

    # Bridge — Pro<->Fly bidirectional event bridge (Phase 1 Sinapsi)
    # Light path: only DB + custom X-Bridge-Auth, no RAG dependencies
    api.include_router(bridge.router)

    # Knowledge Activity Tracking
    api.include_router(knowledge_activity.router)

    # Visa Oracle — public product (no auth required, light deps only)
    api.include_router(visa_oracle.router, prefix=settings.API_V1_STR)

    # intel/intel_scraper/intel_analytics serve on rag process (need /data volume for staging files)


def include_heavy_routers(api: FastAPI) -> None:
    """
    Include HEAVY routers (RAG/KG/AI — require SearchService + ZantaraAIClient).

    Also includes health + handlers so /health works on the RAG process for Fly.io checks.
    All imports are lazy (inside function body) matching the existing pattern.

    Args:
        api: FastAPI application instance
    """
    from backend.app.modules.identity.router import router as identity_router
    from backend.app.modules.knowledge.router import router as knowledge_router
    from backend.app.routers import (
        agent,
        agentic_rag,
        agents,
        autonomous_agents,
        autonomous_execution,
        blog_ask,
        collective_memory,
        conversations,
        crm_clients,
        crm_enhanced,
        crm_practices,
        dashboard,
        dashboard_featured_articles,
        dashboard_summary,
        dream,
        dynamic_pricing,
        episodic_memory,
        experience,  # [EXP] Experience Library
        handlers,
        health,
        ingest,
        intel,
        intel_analytics,
        intel_scraper,
        kbli_notebook,
        kbli_notebook_chat,
        kg_agentic,
        knowledge_visa,
        lam_memory,
        legal_ingest,
        metabolic_health,  # [METABOLIC] SYMBIOSIS Pillar 7
        monitoring_rag,
        naga,
        news,
        oracle_ingest,
        oracle_universal,
        skill,  # [SKILL] Skill Registry
        voice,
        whatsapp_chat,
    )

    # Health endpoints (required for Fly.io process health checks)
    api.include_router(health.router)
    api.include_router(handlers.router)

    # Agent routers
    api.include_router(agent.router)
    api.include_router(lam_memory.router)
    api.include_router(agents.router)
    api.include_router(autonomous_agents.router)
    api.include_router(autonomous_execution.router)  # Phase 7 POC: Autonomous task execution
    api.include_router(agentic_rag.router)
    api.include_router(kg_agentic.router)

    # Conversation & Memory routers
    api.include_router(conversations.router)
    api.include_router(collective_memory.router)
    api.include_router(episodic_memory.router)
    api.include_router(experience.router)  # [EXP] Experience Library
    api.include_router(skill.router)  # [SKILL] Skill Registry
    api.include_router(metabolic_health.router)  # [METABOLIC] SYMBIOSIS Pillar 7 — read-only metrics

    # CRM routers (RAG-heavy)
    api.include_router(crm_clients.router)
    api.include_router(crm_enhanced.router)
    api.include_router(crm_practices.router)

    # Ingestion routers
    api.include_router(ingest.router)
    api.include_router(legal_ingest.router)
    api.include_router(oracle_ingest.router)

    # Naga deep research engine
    api.include_router(naga.router)

    # Oracle router
    api.include_router(oracle_universal.router)

    # Intelligence & News Room routers (require /data volume — rag process only)
    api.include_router(intel.router)
    api.include_router(intel_scraper.router)
    api.include_router(intel_analytics.router)

    from backend.app.core.config import settings

    api.include_router(
        kbli_notebook.router, prefix=settings.API_V1_STR,
    )
    api.include_router(
        kbli_notebook_chat.router, prefix=settings.API_V1_STR,
    )

    # Blog routers (RAG-heavy)
    api.include_router(blog_ask.router)

    # News/Intel Feed routers
    api.include_router(news.router)

    # Dynamic scenario pricing
    api.include_router(dynamic_pricing.router)

    # Module routers (Prime Standard)
    api.include_router(dream.router)
    api.include_router(identity_router, prefix="/api/auth")
    api.include_router(knowledge_router)

    # Knowledge Base - Visa Types
    api.include_router(knowledge_visa.router)

    # Voice endpoint
    api.include_router(voice.router)

    # WhatsApp Chat (RAG-backed intelligent triage)
    api.include_router(whatsapp_chat.router)

    # Dashboard aggregation routers (all under /api/dashboard — proxied to rag)
    api.include_router(dashboard.router)
    api.include_router(dashboard_featured_articles.router)
    api.include_router(dashboard_summary.router)

    # RAG Monitoring router (Retrieval quality metrics and alerts)
    api.include_router(monitoring_rag.router)

    # Visa Oracle — already registered in include_light_routers(), skip duplicate
