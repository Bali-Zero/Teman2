"""Naga Tools - 3 tools for agentic research via the Naga engine."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def naga_research(
        query: str,
        tier: str = "auto",
        domain: str = "auto",
        mode: str = "auto",
        trusted_mode: bool = False,
    ) -> dict:
        """
        Execute agentic research using Naga engine.

        Naga performs multi-step research with claim verification, source
        triangulation, and confidence scoring. Supports tiered execution
        from quick lookups to deep multi-source investigations.

        Args:
            query: Research question or topic
            tier: Execution tier - "auto", "t1" (quick), "t2" (standard), "t3" (deep)
            domain: Domain hint - "auto", "visa", "tax", "company", "property", "general"
            mode: Research mode - "auto", "verify", "explore", "compare"
            trusted_mode: Skip human-in-the-loop confirmations (for automated pipelines)

        Returns:
            Research result with findings, sources, confidence scores, and claim list.
        """
        payload: dict = {
            "query": query,
            "tier": tier,
            "domain": domain,
            "mode": mode,
            "trusted_mode": trusted_mode,
        }
        return await _call(
            "/api/naga/research", method="POST", json=payload, timeout=1800
        )

    @mcp.tool()
    async def naga_claims_search(
        query: str,
        domain: Optional[str] = None,
        verification: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        """
        Search Naga's verified claims knowledge base.

        Query the accumulated knowledge base of verified claims produced
        by previous Naga research sessions.

        Args:
            query: Search query for claims
            domain: Filter by domain (visa, tax, company, property, general)
            verification: Filter by verification status (verified, disputed, unverified)
            limit: Max results to return

        Returns:
            List of matching claims with verification status, sources, and confidence.
        """
        params: dict = {"query": query, "limit": limit}
        if domain:
            params["domain"] = domain
        if verification:
            params["verification"] = verification
        return await _call("/api/naga/claims/search", params=params)

    @mcp.tool()
    async def naga_session_status(session_id: str) -> dict:
        """
        Check status of an ongoing Naga research session.

        Use this to poll progress of long-running Naga research tasks,
        especially tier-3 deep investigations that may take several minutes.

        Args:
            session_id: UUID of the Naga research session

        Returns:
            Session status with progress percentage, current step, partial results.
        """
        return await _call(f"/api/naga/session/{session_id}")
