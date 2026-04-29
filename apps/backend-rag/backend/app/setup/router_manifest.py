"""
Router Manifest — Single source of truth for all router declarations.

SCAR CONTEXT: PRs #54, #55, #60 shipped routers only in include_routers()
but missed include_light_routers() (used by main_api in production).
Result: /api/experience, /api/skill, /api/metabolic silently 404'd in prod.

This manifest makes it structurally impossible to repeat that mistake.
Each router is declared ONCE with its process_groups. The include_*
functions read this manifest instead of maintaining separate import lists.

HOW TO ADD A NEW ROUTER:
  1. Create your router file in backend/app/routers/
  2. Add a RouterEntry below (alphabetical order)
  3. Set process_groups: {"api"} for light, {"rag"} for heavy, {"api","rag"} for both
  4. Run: PYTHONPATH=. pytest backend/tests/setup/ -q
  5. Done. No other file needs editing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterEntry:
    """Single router declaration in the manifest.

    Attributes:
        name: Module name under backend.app.routers (e.g. "auth").
              For module routers, use dotted path (e.g. "modules.identity").
        process_groups: Which Fly.io processes include this router.
                       "api" = main_api (light, public HTTP)
                       "rag" = main_rag (heavy, internal RAG)
        attr: Attribute name on the imported module (default "router").
              Use for multi-router modules (e.g. "v1_router", "webhook_router").
        prefix: Optional prefix override for include_router().
        condition: Optional callable returning bool — if False, router is skipped.
                  Must be cheap (reads settings, no I/O).
        tags: Descriptive tags for documentation/filtering.
        import_path: Full import path override (for module routers not in
                    backend.app.routers). If None, uses f"backend.app.routers.{name}".
    """

    name: str
    process_groups: frozenset[str]
    attr: str = "router"
    prefix: str | None = None
    condition: Callable[[], bool] | None = None
    tags: tuple[str, ...] = ()
    import_path: str | None = None


# Valid process groups — enforce typo prevention
PROCESS_GROUPS = frozenset({"api", "rag"})

# Shorthand constants for readability
_API = frozenset({"api"})
_RAG = frozenset({"rag"})
_BOTH = frozenset({"api", "rag"})


def _is_debug_enabled() -> bool:
    """Condition for debug router: enabled in dev/staging or when ADMIN_API_KEY is set."""
    from backend.app.core.config import settings
    return settings.environment.lower() != "production" or bool(settings.admin_api_key)


def _get_api_v1_prefix() -> str:
    from backend.app.core.config import settings
    return settings.API_V1_STR


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CANONICAL ROUTER MANIFEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Alphabetical order. One entry per router attribute.
# process_groups: _API (light/public), _RAG (heavy/internal), _BOTH
#
# To add a new router: insert one RouterEntry, run tests. Done.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROUTER_MANIFEST: tuple[RouterEntry, ...] = (
    # ── Admin ──
    RouterEntry(name="admin_conversation_cleanup", process_groups=_API, tags=("admin",)),
    RouterEntry(name="admin_drive_auth",           process_groups=_API, tags=("admin", "drive")),
    RouterEntry(name="admin_drive_health",         process_groups=_API, tags=("admin", "drive")),
    RouterEntry(name="admin_drive_refresh",        process_groups=_API, tags=("admin", "drive")),
    RouterEntry(name="admin_drive_setup",          process_groups=_API, tags=("admin", "drive")),
    RouterEntry(name="admin_email_health",         process_groups=_API, tags=("admin", "email")),
    RouterEntry(name="admin_logs",                 process_groups=_API, tags=("admin",)),
    RouterEntry(name="admin_pii",                  process_groups=_API, tags=("admin", "pii", "compliance")),
    RouterEntry(name="admin_practice_auto_create", process_groups=_API, tags=("admin",)),
    RouterEntry(name="admin_rate_limit",           process_groups=_BOTH, tags=("admin", "rate-limit")),
    RouterEntry(name="admin_self_healing",         process_groups=_BOTH, tags=("admin", "self-healing")),
    RouterEntry(name="admin_team_activity",        process_groups=_API, tags=("admin",)),
    RouterEntry(name="admin_zoho_auth",            process_groups=_API, tags=("admin", "integrations")),

    # ── Agent / AI ──
    RouterEntry(name="agent",                process_groups=_RAG, tags=("agent",)),
    RouterEntry(name="agents",               process_groups=_RAG, tags=("agent",)),
    RouterEntry(name="agentic_rag",          process_groups=_RAG, tags=("agent", "rag")),
    RouterEntry(name="autonomous_agents",    process_groups=_RAG, tags=("agent",)),
    RouterEntry(name="autonomous_execution", process_groups=_RAG, tags=("agent",)),

    # ── Analytics ──
    RouterEntry(name="analytics",          process_groups=_API, tags=("analytics",)),
    RouterEntry(name="article_composer",   process_groups=_API, tags=("blog",)),

    # ── Auth / Core ──
    RouterEntry(name="auth",     process_groups=_API, tags=("core",)),
    RouterEntry(name="blog_ask", process_groups=_RAG, tags=("blog", "rag")),

    # ── Bridge ──
    RouterEntry(name="bridge", process_groups=_API, tags=("infra",)),

    # ── CELL ──
    RouterEntry(name="cell_status", process_groups=_API, tags=("cell",)),

    # ── Channels ──
    RouterEntry(name="channels",    process_groups=_API, tags=("channels",)),

    # ── CRM ──
    RouterEntry(name="crm_analytics",          process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_clients",            process_groups=_RAG, tags=("crm", "rag")),
    RouterEntry(name="crm_clients_documents",  process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_company",            process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_enhanced",           process_groups=_RAG, tags=("crm", "rag")),
    RouterEntry(name="crm_enhanced_alerts",    process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_enhanced_documents", process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_interactions",       process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_notifications",      process_groups=_API, tags=("crm",)),
    RouterEntry(name="crm_portal_integration", process_groups=_API, tags=("crm", "portal")),
    RouterEntry(name="crm_practices",          process_groups=_RAG, tags=("crm", "rag")),
    RouterEntry(name="crm_shared_memory",      process_groups=_API, tags=("crm",)),

    # ── Conversations / Memory ──
    RouterEntry(name="collective_memory", process_groups=_RAG, tags=("memory",)),
    RouterEntry(name="conversations",     process_groups=_RAG, tags=("memory",)),
    RouterEntry(name="episodic_memory",   process_groups=_RAG, tags=("memory",)),

    # ── Dashboard ──
    RouterEntry(name="dashboard",                   process_groups=_RAG, tags=("dashboard",)),
    RouterEntry(name="dashboard_featured_articles", process_groups=_RAG, tags=("dashboard",)),
    RouterEntry(name="dashboard_summary",           process_groups=_RAG, tags=("dashboard",)),

    # ── Debug (conditional) ──
    RouterEntry(name="debug", attr="router",     process_groups=_API, condition=_is_debug_enabled, tags=("debug",)),
    RouterEntry(name="debug", attr="v1_router",  process_groups=_API, condition=_is_debug_enabled, tags=("debug",)),

    # ── Documents ──
    RouterEntry(name="documents_proxy", process_groups=_API, tags=("integrations",)),

    # ── Dream ──
    RouterEntry(name="dream", process_groups=_RAG, tags=("module",)),

    # ── Dynamic Pricing ──
    RouterEntry(name="dynamic_pricing", process_groups=_RAG, tags=("pricing",)),

    # ── EventBus ──
    RouterEntry(name="event_bus", process_groups=_API, tags=("infra",)),

    # ── Experience / Skill / Metabolic (SCAR: PR #54/#55/#60) ──
    # These are LIGHT routers (SQLite local, no RAG deps) — must be in api group.
    # Originally misclassified as rag-only, causing 404 in production.
    RouterEntry(name="experience",       process_groups=_API, tags=("cell", "scar-pr54")),
    RouterEntry(name="skill",            process_groups=_API, tags=("cell", "scar-pr55")),
    RouterEntry(name="metabolic_health", process_groups=_API, tags=("cell", "scar-pr60")),

    # ── Federation / Feedback ──
    RouterEntry(name="federation", process_groups=_API, tags=("agent",)),
    RouterEntry(name="feedback",   process_groups=_API, tags=("core",)),

    # ── Funnel (cross-funnel lead tracking, pre-auth) ──
    RouterEntry(name="funnel", process_groups=_API, tags=("funnel",)),

    # ── Google Drive / Integrations ──
    RouterEntry(name="google_drive", process_groups=_API, tags=("integrations",)),

    # ── Core infra ──
    RouterEntry(name="handlers", process_groups=_BOTH, tags=("core",)),
    RouterEntry(name="health",   process_groups=_BOTH, tags=("core",)),

    # ── HR ──
    RouterEntry(name="hr",               process_groups=_API, tags=("hr",)),
    RouterEntry(name="hr_late_reply",     process_groups=_API, tags=("hr",)),
    RouterEntry(name="hr_owner_cashout",  process_groups=_API, tags=("hr",)),

    # ── Image Generation ──
    RouterEntry(name="image_generation", process_groups=_API, tags=("media",)),

    # ── Ingestion ──
    RouterEntry(name="ingest",       process_groups=_RAG, tags=("ingest",)),
    RouterEntry(name="legal_ingest", process_groups=_RAG, tags=("ingest",)),
    RouterEntry(name="oracle_ingest", process_groups=_RAG, tags=("ingest",)),

    # ── Instagram ──
    RouterEntry(name="instagram_chat", attr="router",         process_groups=_API, tags=("channels",)),
    RouterEntry(name="instagram_chat", attr="webhook_router", process_groups=_API, tags=("channels",)),

    # ── Intel (RAG process only — needs /data volume) ──
    RouterEntry(name="intel",           process_groups=_RAG, tags=("intel",)),
    RouterEntry(name="intel_analytics", process_groups=_RAG, tags=("intel",)),
    RouterEntry(name="intel_scraper",   process_groups=_RAG, tags=("intel",)),

    # ── KBLI ──
    RouterEntry(name="kbli_notebook",      process_groups=_RAG, prefix="__API_V1__", tags=("kbli",)),
    RouterEntry(name="kbli_notebook_chat", process_groups=_RAG, prefix="__API_V1__", tags=("kbli",)),

    # ── KG ──
    RouterEntry(name="kg_agentic", process_groups=_RAG, tags=("kg", "agent")),

    # ── Knowledge ──
    RouterEntry(name="knowledge_activity", process_groups=_API, tags=("knowledge",)),
    RouterEntry(name="knowledge_visa",     process_groups=_RAG, tags=("knowledge",)),

    # ── LAM Memory ──
    RouterEntry(name="lam_memory", process_groups=_RAG, tags=("memory",)),

    # ── Lead Capture (4-app homepage → WhatsApp handoff, shared infra) ──
    RouterEntry(name="lead_capture", process_groups=_API, tags=("funnel", "lead")),

    # ── Funnel Email (drip scheduler + unsubscribe for 4-app homepage) ──
    RouterEntry(name="funnel_email", process_groups=_API, tags=("funnel", "email")),

    # ── Compliance Alerts (outcome recording + autotune metrics) ──
    RouterEntry(name="compliance_alerts", process_groups=_API, tags=("compliance",)),

    # ── LKPM Compliance ──
    RouterEntry(name="lkpm", process_groups=_API, tags=("compliance",)),

    # ── LLM Cost Tracking (remote ingestion for Pro/Air cron agents) ──
    RouterEntry(name="llm_costs", process_groups=_API, tags=("observability", "admin")),

    # ── Media ──
    RouterEntry(name="media", process_groups=_API, tags=("media",)),

    # ── Messaging ──
    RouterEntry(name="messaging_identity", process_groups=_API, tags=("channels",)),

    # ── Monitoring ──
    RouterEntry(name="monitoring_rag", process_groups=_RAG, tags=("monitoring",)),

    # ── Naga (Deep Research) ──
    RouterEntry(name="naga", process_groups=_RAG, tags=("research",)),

    # ── Newsletter ──
    RouterEntry(name="newsletter", process_groups=_API, tags=("blog",)),

    # ── News ──
    RouterEntry(name="news", process_groups=_RAG, tags=("intel",)),

    # ── Nusantara Health ──
    RouterEntry(name="nusantara_health", process_groups=_API, tags=("core",)),

    # ── Olympus (full-only: internal admin) ──
    RouterEntry(name="olympus", attr="internal_router", process_groups=_API, tags=("admin",)),

    # ── Omnichannel ──
    RouterEntry(name="omnichannel", process_groups=_API, tags=("channels",)),

    # ── Oracle ──
    RouterEntry(name="oracle_universal", process_groups=_RAG, tags=("oracle",)),

    # ── Performance ──
    RouterEntry(name="performance", process_groups=_API, tags=("analytics",)),

    # ── Partners (CRM) ──
    RouterEntry(name="partners", process_groups=_API, tags=("crm", "partners")),

    # ── Portal ──
    RouterEntry(name="portal",                  process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_admin",            process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_billing",          process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_dashboard",        process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_drive",            process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_family",           process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_matters",          process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_invite",           process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_notifications",    process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_notification_prefs", process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_process_timeline", process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_taxes",            process_groups=_API, tags=("portal",)),
    RouterEntry(name="portal_visa",             process_groups=_API, tags=("portal",)),

    # ── Preview ──
    RouterEntry(name="preview", process_groups=_API, tags=("blog",)),

    # ── Prime ──
    RouterEntry(name="prime",    process_groups=_API, tags=("prime",)),
    RouterEntry(name="prime_v2", process_groups=_API, tags=("prime",)),

    # ── Query Analytics ──
    RouterEntry(name="query_analytics", process_groups=_API, tags=("analytics",)),

    # ── Research Control (SOTA kill-switches) ──
    RouterEntry(name="research_control", process_groups=_API, tags=("sota", "kill-switch")),

    # ── Session ──
    RouterEntry(name="session", process_groups=_API, tags=("core",)),

    # ── Sheets ──
    RouterEntry(name="sheets", process_groups=_API, tags=("integrations",)),

    # ── Team ──
    RouterEntry(name="team",           process_groups=_API, tags=("team",)),
    RouterEntry(name="team_activity",  process_groups=_API, tags=("team",)),
    RouterEntry(name="team_analytics", process_groups=_API, tags=("team",)),
    RouterEntry(name="team_drive",     process_groups=_API, tags=("team", "integrations")),

    # ── Telegram ──
    RouterEntry(name="telegram",         process_groups=_API, tags=("channels",)),
    RouterEntry(name="telegram_webhook", process_groups=_API, tags=("channels",)),

    # ── Twitter / X ──
    # Re-enabled 2026-04-29 (P0-6 zero-crash audit). Was previously DISABLED
    # 2026-04-03 ("CRC broken, OAuth incomplete"); the CRC handshake was
    # actually correct, the disable was conservative. Now lives behind the
    # ack-first persistence layer so any handler exception lands in
    # ``inbound_webhooks`` for the WebhookProcessor to retry.
    RouterEntry(name="twitter", attr="router",         process_groups=_API, tags=("channels",)),
    RouterEntry(name="twitter", attr="webhook_router", process_groups=_API, tags=("channels",)),

    # ── Visa Check (homepage 4-app — Clock + Match branches) ──
    RouterEntry(name="visa_check", process_groups=_API, tags=("visa", "funnel")),

    # ── Visa Oracle (public — prefix override) ──
    RouterEntry(name="visa_oracle", process_groups=_API, prefix="__API_V1__", tags=("visa",)),

    # ── Voice ──
    RouterEntry(name="voice", process_groups=_RAG, tags=("media",)),

    # ── War Room Dashboard (Sprint 11 — metrics aggregate queries) ──
    RouterEntry(
        name="war_room_dashboard",
        process_groups=_API,
        tags=("war-room", "admin"),
    ),

    # ── Webhooks ──
    RouterEntry(name="webhooks", process_groups=_API, tags=("channels",)),

    # ── WebSocket ──
    RouterEntry(name="websocket", process_groups=_API, tags=("channels",)),

    # ── WhatsApp ──
    RouterEntry(name="whatsapp_chat",          process_groups=_RAG, tags=("channels", "rag")),
    RouterEntry(name="whatsapp_conversations", process_groups=_API, tags=("channels",)),

    # ── Workflow ──
    RouterEntry(name="workflow_analytics", process_groups=_API, tags=("analytics",)),
    RouterEntry(name="workflow_queue",     process_groups=_API, tags=("infra",)),

    # ── Workspace (kita team ops) ──
    RouterEntry(name="workspace_inbox",     process_groups=_API, tags=("workspace",)),
    RouterEntry(name="workspace_analytics", process_groups=_API, tags=("workspace", "analytics")),

    # ── Zoho ──
    RouterEntry(name="zoho_email", process_groups=_API, tags=("integrations",)),

    # ── Module routers (not in backend.app.routers) ──
    RouterEntry(
        name="identity",
        process_groups=_RAG,
        prefix="/api/auth",
        import_path="backend.app.modules.identity.router",
        tags=("module", "auth"),
    ),
    RouterEntry(
        name="knowledge",
        process_groups=_RAG,
        import_path="backend.app.modules.knowledge.router",
        tags=("module", "rag"),
    ),
    RouterEntry(
        name="notifications",
        process_groups=_API,
        import_path="backend.app.modules.notifications.router",
        tags=("module",),
    ),
    RouterEntry(
        name="cron_notifiers",
        process_groups=_API,
        import_path="backend.app.routers.cron_notifiers",
        tags=("cron",),
    ),
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Disabled routers — documented here for audit trail
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# twitter / twitter.webhook_router — RE-ENABLED 2026-04-29 (P0-6 zero-crash audit).
#   Original disable: 2026-04-03 ("CRC broken, OAuth incomplete"). The CRC
#   handshake at backend/app/routers/twitter.py was actually correct; the
#   register-time block was conservative. Re-registered above in the
#   "Twitter / X" section with ack-first persistence (P0-6 audit).
# team_members — duplicates team.py /members endpoint (audit 2026-04-03)
# whatsapp_chat.alias_router — legacy alias causes duplicate responses
# guardian — not live yet
# audio — included separately in app_factory.py


def routers_for_group(group: str) -> tuple[RouterEntry, ...]:
    """Return all routers declared for a given process group.

    Args:
        group: Process group name ("api" or "rag")

    Returns:
        Tuple of RouterEntry instances for the group
    """
    if group not in PROCESS_GROUPS:
        raise ValueError(
            f"Unknown process group '{group}'. Valid: {sorted(PROCESS_GROUPS)}"
        )
    return tuple(r for r in ROUTER_MANIFEST if group in r.process_groups)


def all_router_names() -> frozenset[str]:
    """Return all unique router module names in the manifest."""
    return frozenset(r.name for r in ROUTER_MANIFEST)


def validate_manifest() -> list[str]:
    """Validate manifest integrity. Returns list of error messages (empty = OK)."""
    errors: list[str] = []

    # Check process groups are valid
    for entry in ROUTER_MANIFEST:
        invalid = entry.process_groups - PROCESS_GROUPS
        if invalid:
            errors.append(
                f"Router '{entry.name}' has invalid process_groups: {invalid}"
            )
        if not entry.process_groups:
            errors.append(f"Router '{entry.name}' has empty process_groups")

    # Check for duplicate (name, attr) pairs
    seen: set[tuple[str, str]] = set()
    for entry in ROUTER_MANIFEST:
        key = (entry.name, entry.attr)
        if key in seen:
            errors.append(f"Duplicate router entry: name={entry.name}, attr={entry.attr}")
        seen.add(key)

    return errors
