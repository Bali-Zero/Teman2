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


# ═══════════════════════════════════════════════════════════════════
# Role Definitions
# ═══════════════════════════════════════════════════════════════════

ROLE_VISA_SPECIALIST = AgentRole(
    role_id="visa_specialist",
    display_name="Visa Specialist",
    language="id",  # Indonesian
    system_context=(
        "You are Zantara, personal AI assistant for a Visa Specialist at Bali Zero. "
        "Focus on visa applications, KITAS/KITAP processes, immigration requirements, "
        "and client document tracking. Answer in Bahasa Indonesia unless the user "
        "switches language. Always use real data from tools — never guess."
    ),
    allowed_read_tools=[
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
    ],
    allowed_write_tools=[
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "complete_journey_step",
        "federation_send", "federation_mark_read",
        "save_episode",
    ],
    blocked_tools=[
        "execute_plan", "create_execution_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
        "approve_staging_item",
    ],
    client_scope="assigned",
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
    ],
    blocked_tools=[
        "execute_plan",
        "delete_episode",
        "publish_article", "publish_intel",
        "ingest_regulation",
        "get_admin_logs",
    ],
    client_scope="assigned",
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


# ═══════════════════════════════════════════════════════════════════
# Team Member → Role Mapping
# ═══════════════════════════════════════════════════════════════════

TEAM_AGENTS: dict[str, AgentRole] = {
    "damar@balizero.com": ROLE_VISA_SPECIALIST,
    "krisna@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "zero@balizero.com": ROLE_ADMIN,
    "antonellosiano@gmail.com": ROLE_ADMIN,
    "dea@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
    "adit@balizero.com": ROLE_EXECUTIVE_CONSULTANT,
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
