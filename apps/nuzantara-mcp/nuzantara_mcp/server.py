"""
Nuzantara Dynamic MCP Server

Exposes the Nuzantara RAG backend (Fly.io) as MCP tools for OpenClaw agents.
Covers: KBLI search, legal RAG, knowledge graph, health monitoring.

Transport: stdio (for OpenClaw local integration)
"""

import logging
import os
from typing import Optional

import httpx
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("nuzantara-mcp")

# --- Configuration ---
BACKEND_URL = os.getenv("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.getenv("NUZANTARA_API_KEY", "")
TIMEOUT = int(os.getenv("NUZANTARA_TIMEOUT", "30"))

mcp = FastMCP(
    name="Nuzantara RAG",
    instructions="AI-powered legal & business intelligence for Indonesia (Bali Zero)",
)


# --- HTTP helper ---
async def _call(
    endpoint: str,
    method: str = "GET",
    json: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict:
    """Authenticated call to Nuzantara backend."""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=TIMEOUT) as client:
        resp = await client.request(
            method=method, url=endpoint, json=json, params=params, headers=headers
        )
        resp.raise_for_status()
        return resp.json()


# =========================================================================
# TOOLS - KBLI (Indonesian Business Classification)
# =========================================================================


@mcp.tool()
async def search_kbli(query: str, limit: int = 10) -> dict:
    """
    Search Indonesian business activity codes (KBLI 2025).

    Use when users ask about:
    - Which KBLI code fits their business
    - Business license requirements
    - Foreign investment (PMA) eligibility
    - Risk categories for business activities

    Args:
        query: Business activity description (any language - auto-translated to Indonesian)
        limit: Max results (default 10, max 20)

    Returns:
        List of matching KBLI codes with title, score, PMA status, risk category.
    """
    return await _call(
        "/api/v1/kbli-notebook/search",
        params={"query": query, "limit": min(limit, 20)},
    )


@mcp.tool()
async def inspect_kbli(code: str) -> dict:
    """
    Get deep details for a specific KBLI code.

    Returns licensing requirements, PMA status, risk profile,
    required permits, and related KBLI codes from the Knowledge Graph.

    Args:
        code: 5-digit KBLI code (e.g. "56101", "62010")

    Returns:
        Full KBLI detail: title, description, PMA status, licenses, related codes.
    """
    return await _call(f"/api/v1/kbli-notebook/inspect/{code}")


@mcp.tool()
async def chat_kbli(query: str) -> dict:
    """
    AI-powered KBLI consultation chat.

    Translates the query to Indonesian, searches KBLI semantically,
    and generates a grounded explanation with suggested follow-ups.

    Args:
        query: Question about business classification (any language)

    Returns:
        AI answer, detected KBLI codes, search results, suggested queries.
    """
    return await _call(
        "/api/v1/kbli-notebook/chat",
        method="POST",
        json={"query": query},
    )


# =========================================================================
# TOOLS - Agentic RAG (Legal Intelligence)
# =========================================================================


@mcp.tool()
async def ask_legal(
    question: str,
    user_id: str = "mcp-agent",
    session_id: Optional[str] = None,
) -> dict:
    """
    Ask a legal question to Nuzantara's Agentic RAG system.

    Covers Indonesian law: immigration, company formation, tax,
    property, permits, visas, and general legal matters.

    IMPORTANT: Requires authentication (JWT). If no API key is set,
    this tool will return a 401 error.

    Args:
        question: Legal question (any language)
        user_id: User identifier for context tracking
        session_id: Optional session ID for conversation continuity

    Returns:
        AI-generated answer with sources, execution time, route used.
    """
    payload = {"query": question, "user_id": user_id}
    if session_id:
        payload["session_id"] = session_id

    return await _call("/api/agentic-rag/query", method="POST", json=payload)


# =========================================================================
# TOOLS - Health & Monitoring
# =========================================================================


@mcp.tool()
async def check_health() -> dict:
    """
    Check Nuzantara backend health status.

    Returns service status, Qdrant collections count,
    embedding model info, and database connectivity.

    Returns:
        Health status with database and embeddings details.
    """
    return await _call("/health")


@mcp.tool()
async def check_health_detailed() -> dict:
    """
    Get detailed health of all Nuzantara backend services.

    Shows individual service status for: search, AI client,
    database pool, memory service, intelligent router, health monitor.

    Returns:
        Per-service health breakdown with critical service indicators.
    """
    return await _call("/health/detailed")


@mcp.tool()
async def get_qdrant_metrics() -> dict:
    """
    Get Qdrant vector database performance metrics.

    Returns search/upsert operation counts, average latency,
    document counts, retry counts, and error counts.

    Returns:
        Qdrant operation metrics with timestamps.
    """
    return await _call("/health/metrics/qdrant")


# =========================================================================
# RESOURCES
# =========================================================================


@mcp.resource("config://nuzantara")
def get_config() -> dict:
    """Current MCP server configuration."""
    return {
        "backend_url": BACKEND_URL,
        "authenticated": bool(API_KEY),
        "timeout": TIMEOUT,
    }


# =========================================================================
# PROMPTS
# =========================================================================


@mcp.prompt()
def immigration_check(visa_type: str, nationality: str) -> str:
    """Template for immigration eligibility questions."""
    return (
        f"I need information about {visa_type} visa for {nationality} nationals in Indonesia. "
        "Please provide: eligibility requirements, application process, "
        "required documents, processing time and costs, common issues."
    )


@mcp.prompt()
def business_setup(business_type: str, investor_type: str = "foreign") -> str:
    """Template for business setup guidance in Indonesia."""
    return (
        f"I want to establish a {business_type} business in Indonesia as a {investor_type} investor. "
        "Guide me through: recommended company structure (PT, PT PMA), "
        "required KBLI codes, licenses and permits, capital requirements, step-by-step process."
    )


@mcp.prompt()
def kbli_comparison(code1: str, code2: str) -> str:
    """Template to compare two KBLI codes."""
    return (
        f"Compare KBLI {code1} and KBLI {code2}: "
        "What does each cover? What are the differences in PMA status, "
        "risk category, and licensing requirements? "
        "When should I choose one over the other?"
    )


# =========================================================================
# ENTRY POINT
# =========================================================================


def main():
    """Run MCP server with stdio transport."""
    logger.info(f"Starting Nuzantara MCP Server → {BACKEND_URL}")
    logger.info(f"Auth: {'enabled' if API_KEY else 'disabled (public endpoints only)'}")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
