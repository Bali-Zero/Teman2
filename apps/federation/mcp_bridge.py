"""
Federation MCP Bridge — ADK McpToolset integration.

Provides ADK agents with direct access to Nuzantara MCP tools (109 tools)
and Advanced MCP tools (14 tools) without CLI dispatch overhead.

Usage:
  from apps.federation.mcp_bridge import get_nuzantara_toolset, get_advanced_toolset

  # In an LlmAgent:
  agent = LlmAgent(
      name="smart-agent",
      model="gemini-2.0-flash",
      tools=[get_nuzantara_toolset()],
  )

  # Or filter specific tools:
  agent = LlmAgent(
      name="crm-agent",
      model="gemini-2.0-flash",
      tools=[get_nuzantara_toolset(tool_filter=["create_client", "get_client", "list_clients"])],
  )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters as StdioConnectionParams  # noqa: N812

logger = logging.getLogger("federation.mcp_bridge")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ═══════════════════════════════════════════════════════
# MCP Server configurations
# ═══════════════════════════════════════════════════════

# Nuzantara MCP (109 tools): CRM, portal, intel, content, analytics, etc.
NUZANTARA_MCP_PARAMS = StdioConnectionParams(
    command=str(PROJECT_ROOT / "apps" / "nuzantara-mcp" / ".venv" / "bin" / "python"),
    args=[str(PROJECT_ROOT / "apps" / "nuzantara-mcp" / "nuzantara_mcp" / "server.py")],
    env={
        "PYTHONPATH": str(PROJECT_ROOT / "apps" / "nuzantara-mcp"),
    },
)

# Nuzantara Advanced MCP (14 tools): Fly.io ops, diagnostics, code search
ADVANCED_MCP_PARAMS = StdioConnectionParams(
    command=str(PROJECT_ROOT / "apps" / "nuzantara-mcp-advanced" / ".venv" / "bin" / "python"),
    args=[str(PROJECT_ROOT / "apps" / "nuzantara-mcp-advanced" / "nuzantara_mcp_advanced" / "server.py")],
    env={
        "PYTHONPATH": str(PROJECT_ROOT / "apps" / "nuzantara-mcp-advanced"),
    },
)


# ═══════════════════════════════════════════════════════
# Toolset factories
# ═══════════════════════════════════════════════════════

def get_nuzantara_toolset(
    tool_filter: Optional[list[str]] = None,
    prefix: Optional[str] = "nz",
) -> McpToolset:
    """Create an ADK McpToolset connected to the Nuzantara MCP server.

    Args:
        tool_filter: Optional list of tool names to include. None = all 109 tools.
        prefix: Tool name prefix to avoid collisions. Default "nz" → "nz_create_client".
    """
    return McpToolset(
        connection_params=NUZANTARA_MCP_PARAMS,
        tool_filter=tool_filter,
        tool_name_prefix=prefix,
    )


def get_advanced_toolset(
    tool_filter: Optional[list[str]] = None,
    prefix: Optional[str] = "ops",
) -> McpToolset:
    """Create an ADK McpToolset connected to the Advanced MCP server.

    Args:
        tool_filter: Optional list of tool names to include. None = all 14 tools.
        prefix: Tool name prefix. Default "ops" → "ops_check_fly_status".
    """
    return McpToolset(
        connection_params=ADVANCED_MCP_PARAMS,
        tool_filter=tool_filter,
        tool_name_prefix=prefix,
    )


# ═══════════════════════════════════════════════════════
# Domain-specific toolset bundles
# ═══════════════════════════════════════════════════════

def get_crm_toolset() -> McpToolset:
    """CRM tools only: client and practice management."""
    return get_nuzantara_toolset(
        tool_filter=[
            "create_client", "get_client", "update_client", "list_clients",
            "create_practice", "get_practice", "list_practices", "update_practice_status",
            "get_client_stats", "get_client_timeline", "get_client_compliance",
        ],
        prefix="crm",
    )


def get_intel_toolset() -> McpToolset:
    """Intelligence pipeline tools: scraping, research, articles."""
    return get_nuzantara_toolset(
        tool_filter=[
            "search_intel", "get_intel_metrics", "get_intel_trends",
            "compose_article", "get_article", "list_articles", "publish_article",
            "submit_scraper_job", "publish_intel",
        ],
        prefix="intel",
    )


def get_knowledge_toolset() -> McpToolset:
    """Knowledge base tools: KBLI, visa, legal, pricing."""
    return get_nuzantara_toolset(
        tool_filter=[
            "search_kbli", "chat_kbli", "inspect_kbli",
            "list_visa_types", "get_visa_details",
            "ask_legal", "calculate_pricing", "get_all_prices",
            "recall_similar",
        ],
        prefix="kb",
    )


def get_workspace_toolset() -> McpToolset:
    """Google Workspace tools: Drive, Sheets, Email."""
    return get_nuzantara_toolset(
        tool_filter=[
            "list_drive_files", "search_drive", "create_drive_folder",
            "create_client_drive_folder", "get_drive_storage_stats",
            "read_sheet", "write_sheet", "update_sheet_row", "find_sheet_row",
            "send_email", "list_emails", "search_emails",
        ],
        prefix="gws",
    )


def get_compliance_toolset() -> McpToolset:
    """Compliance and monitoring tools."""
    return get_nuzantara_toolset(
        tool_filter=[
            "get_expiry_alerts", "get_compliance_alerts", "get_compliance_summary",
            "track_compliance", "get_critical_alerts",
        ],
        prefix="compliance",
    )


# ═══════════════════════════════════════════════════════
# Verification
# ═══════════════════════════════════════════════════════

async def verify_toolsets() -> dict[str, int]:
    """Verify that MCP toolsets can connect and list tools."""
    results = {}

    for name, params in [("nuzantara", NUZANTARA_MCP_PARAMS), ("advanced", ADVANCED_MCP_PARAMS)]:
        try:
            toolset = McpToolset(connection_params=params)
            tools = await toolset.get_tools()
            results[name] = len(tools)
            logger.info("✅ %s MCP: %d tools available", name, len(tools))
        except Exception as e:
            results[name] = -1
            logger.error("❌ %s MCP: %s", name, e)

    return results


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    print("\nVerifying MCP toolsets...")
    result = asyncio.run(verify_toolsets())
    for name, count in result.items():
        status = f"{count} tools" if count >= 0 else "FAILED"
        print(f"  {name}: {status}")
