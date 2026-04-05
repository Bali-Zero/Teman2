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
