"""Expanded Resources - 5 live data resources."""

from typing import Any, Callable


def register(
    mcp,
    _call_safe: Callable,
    backend_url: str,
    api_key: str,
    timeout: int,
):
    @mcp.resource("config://nuzantara")
    def get_config() -> dict:
        """Current MCP server configuration."""
        return {
            "backend_url": backend_url,
            "authenticated": bool(api_key),
            "timeout": timeout,
            "version": "2.1.0",
            "tools_count": 115,
            "chains_count": 8,
        }

    @mcp.resource("data://crm/stats")
    async def get_crm_stats() -> dict[str, Any]:
        """Live CRM statistics: client counts, practice status breakdown, nationality distribution."""
        return await _call_safe("/api/crm/clients/stats")

    @mcp.resource("data://analytics/daily")
    async def get_daily_analytics() -> dict[str, Any]:
        """Live daily metrics: completion rates, response times, SLA compliance."""
        return await _call_safe("/api/analytics/completion-rates", params={"period": "1d"})

    @mcp.resource("data://intel/alerts")
    async def get_active_alerts() -> dict[str, Any]:
        """Active intelligence and regulatory alerts requiring attention."""
        return await _call_safe("/api/intel/critical")

    @mcp.resource("data://workflows/active")
    async def get_active_workflows() -> dict[str, Any]:
        """Currently active execution plans and their progress."""
        return await _call_safe("/api/v1/autonomous-execution/plans", params={"status": "in_progress", "limit": 20})
