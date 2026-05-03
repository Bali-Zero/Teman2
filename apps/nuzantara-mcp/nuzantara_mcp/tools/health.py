"""Health & Monitoring Tools - 3 tools for system health checks."""


def register(mcp, _call, _call_safe):
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
