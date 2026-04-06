"""
Nuzantara MCP Server — LITE for Antigravity (max 63 tools).
Removes tools to stay under AG's 100-tool global limit
(100 - 36 NLM - 1 sequential-thinking = 63 available).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import mcp  # noqa: E402

EXCLUDED = [
    # Chains (8) — deterministic workflows, run from Claude Code
    "chain_client_health_monitor",
    "chain_compliance_autopilot",
    "chain_daily_ops_autopilot",
    "chain_intel_pipeline",
    "chain_journey_accelerator",
    "chain_new_client_onboarding",
    "chain_practice_lifecycle_check",
    "chain_weekly_report",
    # Federation (4) — Air/Pro orchestration, not for AG
    "federation_send",
    "federation_inbox",
    "federation_mark_read",
    "federation_status",
    # ML/Analytics (7) — rarely needed in AG context
    "run_client_predictor",
    "run_conversation_trainer",
    "visualize_langgraph",
    "lam_grounding_snapshot",
    "langsmith_project_stats",
    "langsmith_recent_runs",
    "langsmith_run_detail",
    # Team metrics (5) — internal HR, not for AG
    "get_burnout_indicators",
    "get_team_productivity",
    "get_team_hours",
    "get_response_times",
    "get_sla_compliance",
    "get_completion_rates",
    # Low-priority ops (6)
    "clock_in",
    "clock_out",
    "get_agents_status",
    "get_admin_logs",
    "get_failed_queries",
    "get_qdrant_metrics",
    # Content (4) — AG doesn't write articles
    "compose_article",
    "publish_article",
    "list_articles",
    "get_article",
    # Portal (4) — client portal, managed from Claude Code
    "get_portal_dashboard",
    "get_portal_timeline",
    "get_portal_visa_status",
    "list_portal_documents",
    # Misc (5)
    "subscribe_newsletter",
    "list_subscribers",
    "approve_staging_item",
    "list_staging_items",
    "delete_episode",
    # Naga (3) — deep research, run from Claude Code
    "naga_research",
    "naga_claims_search",
    "naga_session_status",
    # Sheets (4) — Google Sheets, rarely needed
    "find_sheet_row",
    "read_sheet",
    "update_sheet_row",
    "write_sheet",
    # Extra cuts to reach 58 (for 95 total: 58 + 36 NLM + 1 seq = 95)
    "list_portal_messages",
    "send_portal_message",
    "log_interaction",
    "list_recent_episodes",
    "save_episode",
    "recall_similar",
]

for name in EXCLUDED:
    try:
        mcp.remove_tool(name)
    except Exception:
        pass

if __name__ == "__main__":
    mcp.run()
