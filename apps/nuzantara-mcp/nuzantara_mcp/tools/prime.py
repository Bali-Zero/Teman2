"""Prime Nexus Tools — Geospatial zone intelligence for Zantara AI."""


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def prime_zone_lookup(
        lat: float,
        lng: float,
        include_analysis: bool = False,
        kbli_code: str | None = None,
    ) -> dict:
        """
        Look up RDTR zoning for a geographic point in Bali.

        Returns zone code, allowed activities, building codes, overlays,
        and optionally a full investment analysis with KBLI compliance.

        Use this when a client asks: "Can I open a business in Canggu?",
        "What zone is this property in?", "Is this KBLI allowed here?"

        Args:
            lat: Latitude (-90 to 90), e.g. -8.648 for Canggu
            lng: Longitude (-180 to 180), e.g. 115.132 for Canggu
            include_analysis: If True, includes KBLI compliance + investment score
            kbli_code: KBLI 5-digit code for compliance check (requires include_analysis=True)

        Returns:
            Zone resolution data with zone code, name, allowed activities,
            building codes, overlays. If include_analysis: also verdict
            (GREEN/YELLOW/RED), score breakdown, and opportunities.
        """
        if not include_analysis:
            return await _call(
                "/api/prime/v2/resolve",
                method="POST",
                json={"lat": lat, "lng": lng},
            )

        return await _call(
            "/api/prime/v2/analyze",
            method="POST",
            json={
                "lat": lat,
                "lng": lng,
                "kbli_code": kbli_code,
                "is_pma": True,
            },
        )

    @mcp.tool()
    async def prime_competitor_density(
        zone_code: str,
    ) -> dict:
        """
        Check business density and competitor saturation in a Bali zoning area.

        Returns number of companies, KBLI sector breakdown, and saturation index.
        Use this when a client asks: "How crowded is this area?",
        "How many restaurants are in Canggu?", "Is this market saturated?"

        Args:
            zone_code: RDTR zone code (e.g. "K-3", "W-1", "R-2")

        Returns:
            Total companies, sector breakdown with counts, saturation index (0-1),
            saturation label (LOW/MEDIUM/HIGH).
        """
        return await _call(
            "/api/prime/v2/density",
            method="GET",
            params={"zone_code": zone_code},
        )

    @mcp.tool()
    async def prime_predict_zone(
        zone_code: str,
    ) -> dict:
        """
        Predict investment trend for a Bali zoning area.

        Returns 3-signal analysis: rejection trend, expiry density, activity momentum.
        Use when asked: "Is this zone getting better or worse?",
        "Should I invest here now or wait?", "Zone K-3 trend?"

        Args:
            zone_code: RDTR zone code (e.g. "K-3", "W-1")

        Returns:
            Trend (improving/stable/declining), trend_score, predicted_label,
            and factor breakdown.
        """
        return await _call(
            "/api/prime/v2/predict",
            method="GET",
            params={"zone_code": zone_code},
        )

    @mcp.tool()
    async def prime_temporal_analysis(
        zone_code: str,
        period: str = "6m",
    ) -> dict:
        """
        Analyze activity trends over time for a Bali zoning area.

        Returns time-bucketed practice and company counts with trend direction.
        Use when asked: "What's happening in zone K-3?",
        "How active is Canggu this quarter?", "Zone activity history?"

        Args:
            zone_code: RDTR zone code (e.g. "K-3", "W-1")
            period: Time window — "1m", "3m", "6m", or "12m"

        Returns:
            Buckets with date, practices, companies, activity_score.
            Trend: increasing/stable/decreasing. Total activity count.
        """
        return await _call(
            "/api/prime/v2/temporal",
            method="GET",
            params={"zone_code": zone_code, "period": period, "granularity": "weekly"},
        )

    @mcp.tool()
    async def prime_regulation_feed(
        zone_code: str,
        limit: int = 10,
    ) -> dict:
        """
        Get recent regulations and news affecting a Bali zoning area.

        Combines database news_items with Qdrant semantic search.
        Use when asked: "Any new regulations for Canggu?",
        "Recent legal changes for zone W-1?", "Property news in Seminyak?"

        Args:
            zone_code: RDTR zone code (e.g. "K-3", "W-1")
            limit: Maximum articles to return (1-50)

        Returns:
            List of regulation articles with title, category, sentiment,
            published date, and source URL.
        """
        return await _call(
            "/api/prime/v2/regulations",
            method="GET",
            params={"zone_code": zone_code, "limit": str(limit)},
        )

    @mcp.tool()
    async def prime_create_proposal(
        lat: float,
        lng: float,
        zone_code: str,
        kbli_code: str | None = None,
        verdict_label: str = "GREEN",
        verdict_score: int = 70,
        investor_name: str | None = None,
        investor_email: str | None = None,
    ) -> dict:
        """
        Create a shareable investment proposal from Prime analysis results.

        Returns a token for public sharing (valid 7 days).
        Use when: "Create a proposal for this location",
        "Share analysis with investor", "Generate investment report"

        Args:
            lat: Latitude of the investment location
            lng: Longitude of the investment location
            zone_code: RDTR zone code
            kbli_code: Optional KBLI code for the business type
            verdict_label: GREEN, YELLOW, or RED
            verdict_score: Investment score (0-100)
            investor_name: Optional investor name
            investor_email: Optional investor email

        Returns:
            Proposal token and shareable URL.
        """
        return await _call(
            "/api/prime/v2/proposal",
            method="POST",
            json={
                "lat": lat, "lng": lng, "zone_code": zone_code,
                "kbli_code": kbli_code, "verdict_label": verdict_label,
                "verdict_score": verdict_score, "investor_name": investor_name,
                "investor_email": investor_email,
            },
        )

    @mcp.tool()
    async def prime_portfolio_advisor(
        client_id: int,
    ) -> dict:
        """
        Get investment portfolio health and risk analysis for a client.

        Returns all geocoded entities, health scores, risk concentration,
        and actionable suggestions.
        Use when asked: "How's my investment portfolio?",
        "Risk analysis for client 123", "Portfolio health check"

        Args:
            client_id: CRM client ID

        Returns:
            Entities with health scores, risk concentration by zone/KBLI,
            warnings, suggestions, and overall health percentage.
        """
        return await _call(
            "/api/prime/v2/portfolio",
            method="GET",
            params={"client_id": str(client_id)},
        )
