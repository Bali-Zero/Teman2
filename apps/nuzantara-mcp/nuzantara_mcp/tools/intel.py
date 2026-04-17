"""Intelligence Tools - 8 tools for regulatory intelligence pipeline."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("visa_specialist")
    async def submit_scraper_job(
        sources: list[str],
        topic: Optional[str] = None,
    ) -> dict:
        """
        Submit a new intelligence scraping job.

        Scrapes regulatory sources for updates on Indonesian business law.

        Args:
            sources: List of source identifiers (e.g. ["kemenkumham", "pajak.go.id", "oss.go.id"])
            topic: Optional topic filter

        Returns:
            Job ID and status for tracking.
        """
        payload: dict = {"sources": sources}
        if topic:
            payload["topic"] = topic
        return await _call(
            "/api/intel/scraper/submit", method="POST", json=payload
        )

    @mcp.tool()
    async def list_staging_items(
        status: Optional[str] = None, limit: int = 20
    ) -> dict:
        """
        List intelligence items in staging (pending review).

        Args:
            status: Filter by type: "visa", "news", or "all" (default)
            limit: Max items to return

        Returns:
            List of intel items with title, source, date, status, preview.
        """
        intel_type = status if status in ("visa", "news") else "all"
        return await _call("/api/intel/staging/pending", params={"type": intel_type})

    @mcp.tool()
    async def approve_staging_item(item_id: str) -> dict:
        """
        Approve a staging item for publication.

        Args:
            item_id: UUID of the staging item

        Returns:
            Updated item with approved status.
        """
        # item_id format: "{type}/{id}" or just "{id}" for news
        if "/" not in item_id:
            item_id = f"news/{item_id}"
        return await _call(
            f"/api/intel/staging/approve/{item_id}", method="POST"
        )

    @mcp.tool()
    async def publish_intel(content_type: str, item_id: str) -> dict:
        """
        Publish an approved intelligence item to production.

        Args:
            content_type: Type of content (regulation, alert, analysis, news)
            item_id: UUID of the approved item

        Returns:
            Published item record with public URL.
        """
        return await _call(
            f"/api/intel/staging/publish/{content_type}/{item_id}",
            method="POST",
        )

    @mcp.tool()
    async def get_intel_metrics() -> dict:
        """
        Get intelligence pipeline metrics.

        Returns:
            Total items scraped, approved, published, rejected. Source breakdown.
            Processing times. Collection statistics.
        """
        return await _call("/api/intel/metrics")

    @mcp.tool()
    async def get_critical_alerts() -> dict:
        """
        Get critical regulatory alerts requiring immediate attention.

        Returns alerts about law changes, deadline modifications,
        or new requirements that affect active clients.

        Returns:
            List of critical alerts with severity, impact area, affected clients.
        """
        return await _call("/api/intel/critical")

    @mcp.tool()
    async def get_intel_trends(period: str = "30d") -> dict:
        """
        Get intelligence trends over a time period.

        Args:
            period: Time period (7d, 30d, 90d, 1y)

        Returns:
            Trend data: topic frequency, regulatory activity by area, emerging themes.
        """
        return await _call("/api/intel/trends", params={"period": period})

    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant")
    async def search_intel(query: str, limit: int = 10) -> dict:
        """
        Search the intelligence database.

        Args:
            query: Search query (supports natural language)
            limit: Max results

        Returns:
            Matching intelligence items ranked by relevance.
        """
        return await _call(
            "/api/intel/search", method="POST", json={"query": query, "limit": limit}
        )
