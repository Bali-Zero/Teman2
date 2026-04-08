"""
Nuzantara MCP Server — AGENT MESH (role-filtered).

Starts the full MCP server then removes tools NOT allowed for the given role.
Uses AGENT_ROLE env var to determine which tools to keep.

Usage:
    AGENT_ROLE=visa_specialist NUZANTARA_API_KEY=xxx python -m nuzantara_mcp.server_agent

Roles: visa_specialist, executive_consultant, admin (all tools)
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import mcp  # noqa: E402

logger = logging.getLogger("nuzantara-mcp.agent")

# ═══════════════════════════════════════════════════════════════════
# Role → Allowed Tools mapping
# Mirrors backend/services/agents/team_agent_config.py
# ═══════════════════════════════════════════════════════════════════

ROLE_TOOLS: dict[str, set[str]] = {
    "visa_specialist": {
        # READ — CRM & Visa
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types", "get_portal_visa_status",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health", "check_health_detailed",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        # READ — Content & Marketing
        "list_articles", "get_article",
        "list_subscribers",
        # READ — Intel & Research
        "list_staging_items",
        "get_intel_metrics", "get_critical_alerts", "get_intel_trends",
        "search_intel",
        # READ — Comms
        "list_emails", "search_emails",
        "list_whatsapp_conversations", "list_telegram_conversations",
        # WRITE — CRM
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "complete_journey_step",
        "federation_send", "federation_mark_read",
        "save_episode",
        # WRITE — Content & Marketing
        "compose_article", "publish_article",
        "subscribe_newsletter",
        # WRITE — Intel (scraper + curation)
        "submit_scraper_job",
        "approve_staging_item", "publish_intel",
        # WRITE — Comms / Outreach
        "send_email", "send_whatsapp",
    },
    "executive_consultant": {
        # Everything visa_specialist has, plus:
        "list_clients", "get_client", "get_client_stats", "get_client_timeline",
        "list_practices", "get_practice",
        "get_visa_details", "list_visa_types", "get_portal_visa_status",
        "get_compliance_alerts", "get_compliance_summary", "get_expiry_alerts",
        "calculate_pricing", "get_all_prices", "search_service_pricing",
        "search_kbli", "inspect_kbli", "chat_kbli", "ask_legal",
        "list_portal_documents", "list_portal_messages", "get_portal_dashboard",
        "check_health", "check_health_detailed",
        "get_journey", "get_journey_next_steps",
        "recall_similar", "list_recent_episodes",
        "federation_inbox", "federation_status",
        "list_drive_files", "search_drive",
        # WRITE
        "log_interaction",
        "update_practice_status",
        "send_portal_message",
        "create_journey", "complete_journey_step",
        "create_client",
        "create_practice",
        "create_drive_folder", "create_client_drive_folder",
        "federation_send", "federation_mark_read",
        "save_episode",
    },
}


def _get_all_tool_names() -> set[str]:
    """Get all registered tool names (compatible with FastMCP 3.0–3.2+)."""
    # FastMCP <= 3.1: sync access via _tool_manager
    if hasattr(mcp, "_tool_manager"):
        return {t.name for t in mcp._tool_manager._tools.values()}

    # FastMCP >= 3.2: list_tools() is async, but we can use the internal provider
    if hasattr(mcp, "local_provider") and hasattr(mcp.local_provider, "_tools"):
        return set(mcp.local_provider._tools.keys())

    # Fallback: run async list_tools()
    import asyncio
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    return {t.name for t in tools}


def _remove_tool(name: str) -> None:
    """Remove a tool (compatible with FastMCP 3.0–3.2+)."""
    # FastMCP >= 3.2: prefer local_provider.remove_tool()
    if hasattr(mcp, "local_provider") and hasattr(mcp.local_provider, "remove_tool"):
        mcp.local_provider.remove_tool(name)
    else:
        mcp.remove_tool(name)


def filter_tools_for_role(role: str) -> int:
    """
    Remove tools not allowed for the given role.

    Args:
        role: One of 'visa_specialist', 'executive_consultant', 'admin'

    Returns:
        Number of tools removed
    """
    if role == "admin":
        logger.info("Admin role: all tools available")
        return 0

    allowed = ROLE_TOOLS.get(role)
    if allowed is None:
        logger.error(f"Unknown role '{role}'. Available: {list(ROLE_TOOLS.keys()) + ['admin']}")
        sys.exit(1)

    all_tools = _get_all_tool_names()

    # Remove tools not in allowed set
    removed = 0
    for tool_name in all_tools:
        if tool_name not in allowed:
            try:
                _remove_tool(tool_name)
                removed += 1
            except Exception:
                pass

    remaining = len(all_tools) - removed
    logger.info(f"Role '{role}': {remaining} tools available ({removed} removed)")
    return removed


# ═══════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    role = os.getenv("AGENT_ROLE", "").strip().lower()
    agent_name = os.getenv("AGENT_NAME", "Team Member")

    if not role:
        logger.error("AGENT_ROLE env var required. Set to: visa_specialist, executive_consultant, or admin")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger.info(f"Nuzantara Agent MCP — role={role}, agent={agent_name}")

    filter_tools_for_role(role)
    mcp.run(transport="stdio")
