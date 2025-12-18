"""
Pricing Plugin - Official Bali Zero Pricing

Migrated from: backend/services/zantara_tools.py -> _get_pricing
"""

import logging

from core.plugins import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from pydantic import Field

from services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)


class PricingQueryInput(PluginInput):
    """Input schema for pricing queries"""

    service_type: str = Field(
        default="all",
        description="Type of service: visa, kitas, business_setup, tax_consulting, legal, or all",
    )
    query: str | None = Field(
        None,
        description="Optional: specific search query (e.g. 'long-stay permit', 'company setup')",
    )


class PricingQueryOutput(PluginOutput):
    """Output schema for pricing queries"""

    prices: list[dict] | None = Field(
        None, description="List of pricing items (None if result is dict format - check data field)"
    )
    fallback_contact: dict | None = Field(None, description="Contact info if prices not available")


class PricingPlugin(Plugin):
    """
    Official Bali Zero pricing plugin.

    ⚠️ CRITICAL: ALWAYS use this plugin for ANY pricing question. NEVER generate prices from memory.

    This returns OFFICIAL 2025 prices including:
    - Visa prices (C1 Tourism, C2 Business, D1/D2 Multiple Entry, etc.)
    - KITAS prices (E23 Freelance, E23 Working, E28A Investor, E33F Retirement, E33G Remote Worker)
    - Business services (PT PMA setup, company revision, alcohol license, legal real estate)
    - Tax services (NPWP, monthly/annual reports, BPJS)
    - Quick quote packages
    - Bali Zero service margins and government fee breakdowns
    """

    def __init__(self, config: dict | None = None, pricing_service=None):
        """
        Initialize pricing plugin

        Args:
            config: Optional plugin configuration
            pricing_service: Optional pricing service instance (for dependency injection/testing)
        """
        super().__init__(config)
        self.pricing_service = pricing_service or get_pricing_service()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="bali_zero.pricing",
            version="1.0.0",
            description="Get OFFICIAL Bali Zero pricing for all services (visa, KITAS, business, tax)",
            category=PluginCategory.BALI_ZERO,
            tags=["pricing", "bali-zero", "official", "visa", "kitas", "business", "tax"],
            requires_auth=False,
            estimated_time=0.5,
            rate_limit=30,  # 30 calls per minute
            allowed_models=["haiku", "sonnet", "opus"],
            legacy_handler_key="get_pricing",
        )

    @property
    def input_schema(self):
        return PricingQueryInput

    @property
    def output_schema(self):
        return PricingQueryOutput

    async def execute(self, input_data: PricingQueryInput) -> PricingQueryOutput:
        """Execute pricing query"""
        try:
            service_type = input_data.service_type
            query = input_data.query

            logger.debug(f"Pricing query: service_type={service_type}, query={query}")

            # If query provided, search specifically
            if query:
                result = self.pricing_service.search_service(query)
            else:
                result = self.pricing_service.get_pricing(service_type)

            # Check if pricing loaded successfully
            if not self.pricing_service.loaded:
                return PricingQueryOutput(
                    success=False,
                    error="Official prices not loaded",
                    fallback_contact={
                        "email": "info@balizero.com",
                        "whatsapp": "+62 813 3805 1876",
                    },
                )

            # Convert result to list format if needed
            # Result can be dict (from get_pricing) or dict with results (from search_service) or list
            prices_list = None
            if isinstance(result, list):
                prices_list = result
            elif isinstance(result, dict):
                # If result has 'results' key (from search_service), extract services
                if "results" in result:
                    # Flatten results into list
                    prices_list = []
                    for category, services in result.get("results", {}).items():
                        if isinstance(services, dict):
                            for service_name, service_data in services.items():
                                prices_list.append(
                                    {"category": category, "name": service_name, **service_data}
                                )
                # Otherwise, result is already in the right format
                # Keep as dict in data field, set prices to None (will be extracted by client)
                else:
                    prices_list = None  # Let client extract from data field

            return PricingQueryOutput(
                success=True,
                data=result,
                prices=prices_list,  # None if result is dict format
            )

        except Exception as e:
            logger.error(f"Pricing plugin error: {e}", exc_info=True)
            return PricingQueryOutput(success=False, error=f"Pricing lookup failed: {str(e)}")
