"""
Team Agent Configuration — Role-based permissions for Agent Mesh.

Maps team members to their roles, allowed tools, and client scope.
Used by the Telegram webhook to inject context into conversations.

Architecture:
    chat_id → messaging_users → user_profiles.email → TEAM_AGENTS config
    → role, language, allowed_actions, client_scope injected into ChannelMessage.metadata
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentRole:
    """Defines what a team member's agent can do."""

    role_id: str
    display_name: str
    language: str  # Default response language
    system_context: str  # Injected into system prompt
    allowed_read_tools: list[str] = field(default_factory=list)
    allowed_write_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    client_scope: str = "assigned"  # "assigned" = only their clients, "all" = admin
    # VASSAL Phase 3: tools that require interactive user confirmation before
    # they may execute. The ToolAuthorizer reads this list and returns
    # AuthResult.confirm() with a non-empty preview reason; tool_executor
    # then awaits ConfirmationService.request_and_wait. Empty list = no
    # confirmation needed for any tool (admin default).
    requires_confirmation: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Role Definitions
# ═══════════════════════════════════════════════════════════════════

ROLE_VISA_SPECIALIST = AgentRole(
    role_id="visa_specialist",
    display_name="Junior Consultant",  # Damar: visa + marketing
    language="id",  # Indonesian
    system_context=(
        "You are Zantara, personal AI assistant for a Junior Consultant at Bali Zero. "
        "Focus on visa applications, client follow-up, content creation, and marketing. "
        "Answer in Bahasa Indonesia unless the user switches language. "
        "Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
        # CRM & Visa
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types", "get_portal_visa_status",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        # Content & Marketing
        "list_articles", "get_article",
        "list_subscribers",
        # Intel & Research
        "list_staging_items",
        "get_intel_metrics", "get_critical_alerts", "get_intel_trends",
        "search_intel",
        # Comms
        "list_emails", "search_emails",
        "list_whatsapp_conversations", "list_telegram_conversations",
        # Phase 2 v8: path Z runtime tools
        "vector_search",
        "pricing",
        "team_knowledge",
        "knowledge_graph",
        "calculator",
        "vision",
        "web_search",
        "crm_query",
    ],
    allowed_write_tools=[
        # CRM
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "complete_journey_step",
        "federation_send", "federation_mark_read",
        "save_episode",
        "image_generation",
        "timesheet",
        # Content & Marketing
        "compose_article", "publish_article",
        "subscribe_newsletter",
        # Intel (scraper + curation)
        "submit_scraper_job",
        "approve_staging_item", "publish_intel",
        # Comms / Outreach
        "send_email", "send_whatsapp",
    ],
    blocked_tools=[
        "execute_plan", "create_execution_plan",
        "delete_episode",
        "ingest_regulation",
        "get_admin_logs",
    ],
    client_scope="assigned",
    requires_confirmation=["image_generation"],
)

ROLE_EXECUTIVE_CONSULTANT = AgentRole(
    role_id="executive_consultant",
    display_name="Executive Consultant",
    language="id",
    system_context=(
        "You are Zantara, personal AI assistant for an Executive Consultant at Bali Zero. "
        "Focus on company setup (PT PMA, CV), client onboarding, practice management, "
        "and business advisory. Answer in Bahasa Indonesia unless the user switches language. "
        "Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        "list_drive_files", "search_drive",
        # Phase 2 v8: path Z runtime tools (agentic ReAct loop registry).
        # Same gap analysis as ROLE_VISA_SPECIALIST — see
        # VASSAL_PHASE2_HANDOFF.md (a)1-2.
        "vector_search",
        "pricing",
        "team_knowledge",
        "knowledge_graph",
        "calculator",
        "vision",
        "web_search",
        "crm_query",
    ],
    allowed_write_tools=[
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "create_journey", "complete_journey_step",
        "create_client",
        "create_practice",
        "create_drive_folder", "create_client_drive_folder",
        "federation_send", "federation_mark_read",
        "save_episode",
        "image_generation",
        "timesheet",  # Own HR timesheet
    ],
    blocked_tools=[
        "execute_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
    ],
    client_scope="assigned",
    requires_confirmation=["image_generation"],
)

ROLE_ADMIN = AgentRole(
    role_id="admin",
    display_name="Administrator",
    language="it",  # Italian for Zero
    system_context=(
        "You are Zantara, AI assistant for the administrator of Bali Zero. "
        "Full access to all tools and all clients. Respond in Italian."
    ),
    allowed_read_tools=[],  # Empty = all allowed
    allowed_write_tools=[],  # Empty = all allowed
    blocked_tools=[],  # Nothing blocked
    client_scope="all",
)

ROLE_HR_MANAGER = AgentRole(
    role_id="hr_manager",
    display_name="HR Manager",
    language="id",
    system_context=(
        "You are Zantara, personal AI assistant for the HR Manager at Bali Zero. "
        "Focus on CRM clients/practices overview, team HR, payroll, and timesheets. "
        "Answer in Bahasa Indonesia unless the user switches language. "
        "Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
        # CRM: clients + practices (read)
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        # HR: full read (payroll, timesheets, team)
        "get_team_activity", "get_team_timesheets", "get_payroll_summary",
        "get_hr_dashboard", "list_team_members",
        # Runtime tools
        "vector_search", "pricing", "team_knowledge", "knowledge_graph",
        "calculator", "vision", "web_search",
    ],
    allowed_write_tools=[
        "log_interaction",
        "update_practice_status",
        "timesheet",
        "image_generation",
        "save_episode",
    ],
    blocked_tools=[
        # Owner cashout: nobody except admin
        "get_owner_cashout", "create_owner_cashout", "process_owner_cashout",
        "list_owner_cashouts", "owner_cashout_report",
        # Admin-only
        "execute_plan", "create_execution_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
        "approve_staging_item",
    ],
    client_scope="all",
)

ROLE_CRM_FULL = AgentRole(
    role_id="crm_full",
    display_name="CRM Full Access",
    language="uk",  # Ukrainian for Ruslana
    system_context=(
        "You are Zantara, personal AI assistant for a Board Member at Bali Zero. "
        "Full access to all CRM data: clients, practices, compliance, analytics. "
        "Respond in Ukrainian unless the user switches language. "
        "Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
        # CRM: full read
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types", "get_portal_visa_status",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        "list_drive_files", "search_drive",
        # Runtime tools
        "vector_search", "pricing", "team_knowledge", "knowledge_graph",
        "calculator", "vision", "web_search",
    ],
    allowed_write_tools=[
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "create_journey", "complete_journey_step",
        "create_client",
        "create_practice",
        "create_drive_folder", "create_client_drive_folder",
        "federation_send", "federation_mark_read",
        "save_episode",
        "image_generation",
    ],
    blocked_tools=[
        "execute_plan", "create_execution_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
        "approve_staging_item",
    ],
    client_scope="all",
)

ROLE_TAX_SPECIALIST = AgentRole(
    role_id="tax_specialist",
    display_name="Tax Specialist",
    language="id",
    system_context=(
        "You are Zantara, personal AI assistant for a Tax Specialist at Bali Zero. "
        "Focus on tax compliance, LKPM reporting, CRM client/practice data, "
        "and your own HR/timesheet. Answer in Bahasa Indonesia unless the user "
        "switches language. Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
        # CRM: full read
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        "list_drive_files", "search_drive",
        # LKPM
        "get_lkpm_status", "list_lkpm_reports", "get_lkpm_deadlines",
        # Runtime tools
        "vector_search", "pricing", "team_knowledge", "knowledge_graph",
        "calculator", "vision", "web_search",
    ],
    allowed_write_tools=[
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "create_journey", "complete_journey_step",
        "create_client",
        "create_practice",
        "federation_send", "federation_mark_read",
        "save_episode",
        "image_generation",
        # Own timesheet
        "timesheet",
        # LKPM
        "create_lkpm_report", "update_lkpm_report",
    ],
    blocked_tools=[
        "execute_plan", "create_execution_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
        "approve_staging_item",
    ],
    client_scope="all",
)


# ═══════════════════════════════════════════════════════════════════
# Team Member → Role Mapping
# ═══════════════════════════════════════════════════════════════════

TEAM_AGENTS: dict[str, AgentRole] = {
    # Admin
    "zero@balizero.com": ROLE_ADMIN,
    # HR Manager
    "asya@balizero.com": ROLE_HR_MANAGER,
    # CRM Full (Board)
    "ruslana@balizero.com": ROLE_CRM_FULL,
    # Visa Specialist
    "damar@balizero.com": ROLE_VISA_SPECIALIST,
    # Executive Consultants (setup team)
    "krisna@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "dea@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "adit@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "ari.firda@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "surya@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "sahira@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "vino@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    # Tax team
    "tax@balizero.com": ROLE_TAX_SPECIALIST,  # Veronika
    "angel.tax@balizero.com": ROLE_TAX_SPECIALIST,
    "kadek.tax@balizero.com": ROLE_TAX_SPECIALIST,
    "dewaayu.tax@balizero.com": ROLE_TAX_SPECIALIST,
    "faysha.tax@balizero.com": ROLE_TAX_SPECIALIST,
}


def get_agent_role(email: str) -> AgentRole | None:
    """
    Get the agent role for a team member by email.

    Args:
        email: Team member email

    Returns:
        AgentRole or None if not a registered team agent
    """
    return TEAM_AGENTS.get(email)


def is_tool_allowed(role: AgentRole, tool_name: str) -> bool:
    """
    Check if a tool is allowed for a given role.

    Logic:
        - If blocked_tools is non-empty and tool is in it → DENIED
        - If allowed_read/write_tools are non-empty → tool must be in one of them
        - If both allowed lists are empty (admin) → ALLOWED

    Args:
        role: AgentRole to check
        tool_name: MCP tool name

    Returns:
        True if tool is allowed
    """
    # Explicitly blocked
    if role.blocked_tools and tool_name in role.blocked_tools:
        return False

    # Admin: empty allowed lists = everything allowed
    if not role.allowed_read_tools and not role.allowed_write_tools:
        return True

    # Must be in one of the allowed lists
    return tool_name in role.allowed_read_tools or tool_name in role.allowed_write_tools


def build_agent_context(email: str, full_name: str) -> dict[str, Any] | None:
    """
    Build the full agent context dict to inject into ChannelMessage.metadata.

    Args:
        email: Team member email
        full_name: Team member display name

    Returns:
        Dict with agent context or None if not a team agent
    """
    role = get_agent_role(email)
    if not role:
        return None

    return {
        "agent_mesh": True,
        "agent_email": email,
        "agent_name": full_name,
        "agent_role": role.role_id,
        "agent_role_display": role.display_name,
        "agent_language": role.language,
        "agent_system_context": role.system_context,
        "agent_client_scope": role.client_scope,
    }
