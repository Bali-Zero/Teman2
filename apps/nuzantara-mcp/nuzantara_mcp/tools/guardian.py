"""Guardian monitoring tools.

These tools expose read-only Guardian decision and risk-score state through the
backend. They do not mutate Guardian records or runtime configuration.
"""

from typing import Any, Optional


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:
    @mcp.tool()
    async def guardian_recent_decisions(
        last: int = 24,
        component: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """Get recent Guardian decisions with optional filters."""
        params: dict[str, Any] = {"last": last, "limit": limit}
        if component:
            params["component"] = component
        if severity:
            params["severity"] = severity
        return await _call("/api/guardian/decisions", params=params, admin=True)

    @mcp.tool()
    async def guardian_risk_score() -> dict:
        """Get latest Guardian risk score plus 7-day trend."""
        return await _call("/api/guardian/risk-score", admin=True)

    @mcp.tool()
    async def guardian_risk_score_history(days: int = 30) -> dict:
        """Get Guardian risk score history."""
        return await _call(
            "/api/guardian/risk-score/history",
            params={"days": days},
            admin=True,
        )
