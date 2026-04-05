"""Pricing Tools - 3 tools for dynamic pricing and service catalog."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def calculate_pricing(
        service_type: str,
        complexity: str = "standard",
        urgency: str = "normal",
    ) -> dict:
        """
        Calculate pricing for a service based on type, complexity, and urgency.

        Uses the dynamic pricing engine that factors in current workload,
        service complexity, and urgency surcharges.

        Args:
            service_type: Type of service (e.g., "kitas", "pt_pma", "kitap",
                "property_due_diligence", "tax_filing")
            complexity: Complexity level: "standard", "complex", "premium"
            urgency: Urgency level: "normal", "urgent", "express"

        Returns:
            Pricing breakdown: base_price, surcharges, total, currency, validity.
        """
        return await _call_safe(
            "/api/agents/pricing/calculate",
            method="POST",
            json={
                "service_type": service_type,
                "complexity": complexity,
                "urgency": urgency,
            },
        )

    @mcp.tool()
    async def get_all_prices() -> dict:
        """
        Get the complete pricing catalog for all services.

        Returns the full official pricing list. This is the ONLY source of truth
        for prices — never hardcode or guess prices.

        Returns:
            Complete pricing catalog with all service types and tiers.
        """
        return await _call_safe("/api/pricing/all")

    @mcp.tool()
    async def search_service_pricing(query: str) -> dict:
        """
        Search for a specific service in the pricing catalog.

        Uses semantic search to find the right service even with
        approximate descriptions.

        Args:
            query: Natural language description of the service
                (e.g., "work permit for investor", "company setup bali")

        Returns:
            Matching services with pricing details.
        """
        return await _call_safe("/api/pricing/search", params={"q": query})
