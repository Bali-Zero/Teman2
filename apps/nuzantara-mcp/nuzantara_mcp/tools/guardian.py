"""Guardian risk and decision audit tools."""

from typing import Any, Optional


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:
    @mcp.tool()
    async def guardian_risk_score() -> dict:
        """
        Return the latest Guardian risk score and seven-day trend.

        Returns:
            Current score snapshot plus daily trend rows.
        """
        return await _call("/api/guardian/risk-score")

    @mcp.tool()
    async def guardian_recent_decisions(
        last: int = 24,
        limit: int = 100,
        component: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> dict:
        """
        Return recent Guardian decisions with optional filters.

        Args:
            last: Hours to look back, capped by backend at 720.
            limit: Max rows to return, capped by backend at 500.
            component: Optional component filter.
            severity: Optional severity filter.

        Returns:
            Recent Guardian decision records.
        """
        params: dict[str, Any] = {"last": last, "limit": limit}
        if component:
            params["component"] = component
        if severity:
            params["severity"] = severity
        return await _call("/api/guardian/decisions", params=params)

    @mcp.tool()
    async def guardian_risk_score_history(days: int = 7) -> dict:
        """
        Return Guardian risk score history.

        Args:
            days: Days to look back, capped by backend at 90.

        Returns:
            Historical Guardian score snapshots.
        """
        return await _call("/api/guardian/risk-score/history", params={"days": days})
