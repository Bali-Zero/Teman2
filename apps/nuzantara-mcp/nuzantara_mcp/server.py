"""
Nuzantara MCP Server v2.1
Full-spectrum business automation for Bali Zero.

96 tools | 10 prompts | 5 resources | 8 deterministic workflow chains

Transport: stdio (for Claude Code / Cowork / OpenClaw local integration)
"""

import logging
import os
from typing import Any, Optional

import httpx
from fastmcp import FastMCP

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("nuzantara-mcp")

# --- Configuration ---
BACKEND_URL = os.getenv("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.getenv("NUZANTARA_API_KEY", "")
TIMEOUT = int(os.getenv("NUZANTARA_TIMEOUT", "30"))
LONG_TIMEOUT = int(os.getenv("NUZANTARA_LONG_TIMEOUT", "120"))

# --- MCP Server Instance ---
mcp = FastMCP(
    name="Nuzantara",
    instructions=(
        "Full-spectrum AI business intelligence and automation platform for Bali Zero. "
        "Covers: CRM, client portal, intelligence, content, analytics, KBLI/visa knowledge, "
        "communications, Google Drive, autonomous workflows, and admin operations. "
        "Use workflow chains for deterministic multi-step automation with near-zero human intervention."
    ),
)


# --- HTTP Helpers ---
async def _call(
    endpoint: str,
    method: str = "GET",
    json: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: Optional[int] = None,
) -> dict:
    """Authenticated call to Nuzantara backend."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["X-API-Key"] = API_KEY

    async with httpx.AsyncClient(
        base_url=BACKEND_URL, timeout=timeout or TIMEOUT
    ) as client:
        resp = await client.request(
            method=method, url=endpoint, json=json, params=params, headers=headers
        )
        resp.raise_for_status()
        return resp.json()


async def _call_safe(
    endpoint: str,
    method: str = "GET",
    json: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: Optional[int] = None,
) -> dict[str, Any]:
    """Like _call but returns error dict instead of raising."""
    try:
        return await _call(endpoint, method, json, params, timeout)
    except httpx.HTTPStatusError as e:
        return {"error": True, "status": e.response.status_code, "detail": str(e)}
    except httpx.RequestError as e:
        return {"error": True, "status": 0, "detail": f"Connection error: {e}"}


# --- Register all tool modules ---
# --- Core domain tools ---
from nuzantara_mcp.tools.crm import register as register_crm
from nuzantara_mcp.tools.portal import register as register_portal
from nuzantara_mcp.tools.intel import register as register_intel
from nuzantara_mcp.tools.content import register as register_content
from nuzantara_mcp.tools.analytics import register as register_analytics
from nuzantara_mcp.tools.knowledge import register as register_knowledge
from nuzantara_mcp.tools.comms import register as register_comms
from nuzantara_mcp.tools.drive import register as register_drive
from nuzantara_mcp.tools.sheets import register as register_sheets
from nuzantara_mcp.tools.workflows import register as register_workflows
from nuzantara_mcp.tools.admin import register as register_admin
from nuzantara_mcp.tools.health import register as register_health
from nuzantara_mcp.tools.google_bridge import register as register_google_bridge

# --- Tier 1 expansion: Journey, Pricing, Invoicing, Compliance ---
from nuzantara_mcp.tools.journey import register as register_journey
from nuzantara_mcp.tools.pricing import register as register_pricing
from nuzantara_mcp.tools.invoicing import register as register_invoicing
from nuzantara_mcp.tools.compliance import register as register_compliance

# --- LAM: Memory + Heartbeat ---
from nuzantara_mcp.tools.memory import register as register_memory
from nuzantara_mcp.workflows.heartbeat import register as register_heartbeat

# --- Observability ---
from nuzantara_mcp.tools.langsmith import register as register_langsmith

# --- Legal Ingestion ---
from nuzantara_mcp.tools.legal import register as register_legal

# --- Federation ---
from nuzantara_mcp.tools.federation import register as register_federation

# --- Prompts, Resources, Chains ---
from nuzantara_mcp.prompts.templates import register as register_prompts
from nuzantara_mcp.resources.config import register as register_resources
from nuzantara_mcp.workflows.chains import register as register_chains

# Core domain
register_crm(mcp, _call, _call_safe)
register_portal(mcp, _call, _call_safe)
register_intel(mcp, _call, _call_safe)
register_content(mcp, _call, _call_safe)
register_analytics(mcp, _call, _call_safe)
register_knowledge(mcp, _call, _call_safe)
register_comms(mcp, _call, _call_safe)
register_drive(mcp, _call, _call_safe)
register_sheets(mcp, _call, _call_safe)
register_workflows(mcp, _call, _call_safe)
register_admin(mcp, _call, _call_safe)
register_health(mcp, _call, _call_safe)
register_google_bridge(mcp, _call, _call_safe)

# Tier 1 expansion
register_journey(mcp, _call, _call_safe)
register_pricing(mcp, _call, _call_safe)
register_invoicing(mcp, _call, _call_safe)
register_compliance(mcp, _call, _call_safe)

# LAM: memory + grounding
register_memory(mcp, _call, _call_safe)
register_heartbeat(mcp, _call, _call_safe)

# Observability
register_langsmith(mcp, _call, _call_safe)

# Legal ingestion pipeline
register_legal(mcp, _call, _call_safe)

# Federation inter-node bus
register_federation(mcp, _call, _call_safe)

# Prompts, resources, chains
register_prompts(mcp)
register_resources(mcp, _call_safe, BACKEND_URL, API_KEY, TIMEOUT)
register_chains(mcp, _call, _call_safe, LONG_TIMEOUT)


# --- Entry Point ---
def main():
    """Run MCP server with stdio transport."""
    logger.info(f"Nuzantara MCP v2.1 → {BACKEND_URL}")
    logger.info(f"Auth: {'enabled' if API_KEY else 'disabled (public endpoints only)'}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
