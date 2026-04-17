"""Analytics Tools - 8 tools for business intelligence and team monitoring."""

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def get_completion_rates(period: str = "30d") -> dict:
        """
        Get practice completion rates.

        Args:
            period: Time period (7d, 30d, 90d, 1y)

        Returns:
            Completion rates by practice type, average time to completion,
            bottleneck analysis, comparison to previous period.
        """
        return await _call(
            "/api/analytics/completion-rates", params={"period": period}
        )

    @mcp.tool()
    async def get_response_times(period: str = "30d") -> dict:
        """
        Get response time analytics.

        Args:
            period: Time period (7d, 30d, 90d, 1y)

        Returns:
            Average response times by channel, peak hours, SLA compliance rates.
        """
        return await _call(
            "/api/analytics/response-times", params={"period": period}
        )

    @mcp.tool()
    async def get_sla_compliance(period: str = "30d") -> dict:
        """
        Get SLA compliance metrics.

        Args:
            period: Time period (7d, 30d, 90d, 1y)

        Returns:
            SLA compliance percentage, breaches by category, trend over time.
        """
        return await _call(
            "/api/analytics/sla-compliance", params={"period": period}
        )

    @mcp.tool()
    @require_role("tax_consultant")
    async def get_revenue_analytics(period: str = "30d") -> dict:
        """
        Get revenue analytics.

        Args:
            period: Time period (7d, 30d, 90d, 1y)

        Returns:
            Total revenue, revenue by practice type, client LTV distribution,
            month-over-month growth, forecast.
        """
        return await _call(
            "/api/analytics/revenue", params={"period": period}
        )

    @mcp.tool()
    async def get_query_analytics(period: str = "7d") -> dict:
        """
        Get RAG query analytics (how the AI system is performing).

        Args:
            period: Time period (1d, 7d, 30d)

        Returns:
            Query volume, success rate, average confidence, top topics,
            collection hit rates, cache utilization.
        """
        return await _call(
            "/api/query-analytics/volume", params={"period": period}
        )

    @mcp.tool()
    async def get_failed_queries(limit: int = 20) -> dict:
        """
        Get recent failed/low-confidence queries for analysis.

        Returns:
            List of queries that returned ABSTAIN or CAUTIOUS responses,
            with context about why they failed.
        """
        return await _call(
            "/api/query-analytics/failed", params={"limit": limit}
        )

    @mcp.tool()
    async def get_team_productivity(period: str = "7d") -> dict:
        """
        Get team productivity metrics.

        Args:
            period: Time period (1d, 7d, 30d)

        Returns:
            Practices handled per member, response times, client satisfaction,
            workload distribution.
        """
        return await _call(
            "/api/team-analytics/productivity", params={"period": period}
        )

    @mcp.tool()
    async def get_burnout_indicators() -> dict:
        """
        Get team burnout risk indicators.

        Analyzes work patterns to identify potential burnout risks.

        Returns:
            Per-member risk scores, overtime hours, weekend work frequency,
            response time degradation, recommendations.
        """
        return await _call("/api/team-analytics/burnout")
