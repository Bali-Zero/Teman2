"""
Bali Zero Official Pricing Service
Loads official prices from JSON (NO AI GENERATION)
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PricingService:
    """Official Bali Zero pricing - NO AI GENERATION ALLOWED"""

    def __init__(self):
        self.prices: dict[str, Any] = {}
        self.loaded = False
        self._load_prices()

    def _load_prices(self):
        """Load official prices from JSON file"""
        try:
            # Path to official prices JSON
            json_path = (
                Path(__file__).parent.parent / "data" / "bali_zero_official_prices_2025.json"
            )

            if not json_path.exists():
                logger.warning(f"Official prices file not found at {json_path}")
                self.prices = {}
                self.loaded = False
                return

            with open(json_path, encoding="utf-8") as f:
                self.prices = json.load(f)

            self.loaded = True
            logger.info(f"Loaded official Bali Zero prices from {json_path}")

            # Count services
            service_count = 0
            for category in [
                "single_entry_visas",
                "multiple_entry_visas",
                "kitas_permits",
                "kitap_permits",
                "business_legal_services",
                "taxation_services",
            ]:
                if category in self.prices.get("services", {}):
                    service_count += len(self.prices["services"][category])

            logger.info(f"{service_count} services loaded across 6 categories")

        except Exception as e:
            logger.error(f"Error loading official prices: {e}")
            self.prices = {}
            self.loaded = False

    def get_pricing(self, service_type: str = "all") -> dict[str, Any]:
        """
        Get pricing for specific service type (FIXED: Added missing method)

        Args:
            service_type: Type of service (visa, kitas, business_setup, tax_consulting, legal, all)

        Returns:
            Pricing data for the requested service type
        """
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {"email": "info@balizero.com", "whatsapp": "+62 813 3805 1876"},
            }

        # Map service types to specific methods
        if service_type == "visa":
            return self.get_visa_prices()
        elif service_type == "kitas" or service_type == "long_stay_permit":
            return self.get_kitas_prices()  # Generic long-stay permit prices
        elif service_type == "business_setup":
            return self.get_business_prices()
        elif service_type == "tax_consulting":
            return self.get_tax_prices()
        elif service_type == "legal":
            return self.get_business_prices()  # Legal services are in business
        elif service_type == "all":
            return self.get_all_prices()
        else:
            # Try to search for the service
            return self.search_service(service_type)

    def get_all_prices(self) -> dict[str, Any]:
        """Get all official prices"""
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {"email": "info@balizero.com", "whatsapp": "+62 813 3805 1876"},
            }
        return self.prices

    def search_service(self, query: str) -> dict[str, Any]:
        """Search for a specific service by name or keyword (IMPROVED SEARCH with legacy alias support)"""
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "contact": self.prices.get("contact_info", {}),
            }

        query_lower = query.lower()
        results = {}

        # Extract keywords from query (remove common words)
        noise_words = [
            "berapa",
            "harga",
            "biaya",
            "price",
            "cost",
            "how",
            "much",
            "is",
            "the",
            "quanto",
            "costa",
            "what",
            "untuk",
            "for",
            "?",
            "di",
            "in",
            "bali",
        ]

        # Split query and remove noise words
        query_keywords = query_lower.split()
        clean_keywords = [
            w.strip("?.,!") for w in query_keywords if w.strip("?.,!") not in noise_words
        ]

        # Also search full query for partial matches
        search_terms = clean_keywords + [query_lower]

        # Search across all service categories
        services = self.prices.get("services", {})
        for category_name, category_services in services.items():
            if isinstance(category_services, dict):
                for service_name, service_data in category_services.items():
                    # Match by any keyword in service name or service data
                    service_text = service_name.lower() + " " + str(service_data).lower()

                    # Also check legacy_names if present (e.g., B211A -> C1 Tourism)
                    legacy_names = (
                        service_data.get("legacy_names", [])
                        if isinstance(service_data, dict)
                        else []
                    )
                    legacy_text = " ".join([n.lower() for n in legacy_names])
                    full_search_text = service_text + " " + legacy_text

                    if any(term in full_search_text for term in search_terms):
                        if category_name not in results:
                            results[category_name] = {}
                        results[category_name][service_name] = service_data

        if results:
            return {
                "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025",
                "search_query": query,
                "results": results,
                "contact_info": self.prices.get("contact_info", {}),
                "disclaimer": self.prices.get("disclaimer", {}),
            }
        else:
            return {
                "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025",
                "search_query": query,
                "message": f"No service found for '{query}'",
                "suggestion": "Contact info@balizero.com for custom quotes",
                "contact_info": self.prices.get("contact_info", {}),
            }

    def get_visa_prices(self) -> dict[str, Any]:
        """Get all visa prices (single entry + multiple entry)"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025 - VISA",
            "single_entry_visas": services.get("single_entry_visas", {}),
            "multiple_entry_visas": services.get("multiple_entry_visas", {}),
            "contact_info": self.prices.get("contact_info", {}),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_kitas_prices(self) -> dict[str, Any]:
        """Get all KITAS prices"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025 - KITAS",
            "kitas_permits": services.get("kitas_permits", {}),
            "contact_info": self.prices.get("contact_info", {}),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_business_prices(self) -> dict[str, Any]:
        """Get business & legal service prices"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025 - BUSINESS",
            "business_legal_services": services.get("business_legal_services", {}),
            "contact_info": self.prices.get("contact_info", {}),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_tax_prices(self) -> dict[str, Any]:
        """Get taxation service prices"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025 - TAX",
            "taxation_services": services.get("taxation_services", {}),
            "contact_info": self.prices.get("contact_info", {}),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_quick_quotes(self) -> dict[str, Any]:
        """Get pre-calculated package quotes"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025 - PACKAGES",
            "quick_quotes": services.get("quick_quotes", {}),
            "contact_info": self.prices.get("contact_info", {}),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_warnings(self) -> dict[str, Any]:
        """Get important warnings for clients"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        return {
            "important_warnings": self.prices.get("important_warnings", {}),
            "cost_optimization_tips": self.prices.get("cost_optimization_tips", {}),
            "contact_urgency_levels": self.prices.get("contact_urgency_levels", {}),
        }

    def format_for_llm_context(self, service_type: str | None = None) -> str:
        """
        Format pricing data as context for LLM
        Returns a concise string suitable for injection into LLM context
        """
        if not self.loaded:
            return "⚠️ Official prices not available. Contact info@balizero.com"

        context_parts = [
            "🔒 BALI ZERO OFFICIAL PRICES 2025 (DO NOT GENERATE - USE THESE EXACT VALUES)",
            "",
        ]

        services = self.prices.get("services", {})

        if service_type == "visa" or service_type is None:
            context_parts.append("## VISA PRICES")
            # Single entry
            for name, data in services.get("single_entry_visas", {}).items():
                price = data.get("price", "Contact")
                context_parts.append(f"- {name}: {price}")
            # Multiple entry
            for name, data in services.get("multiple_entry_visas", {}).items():
                price_1y = data.get("price_1y", "")
                price_2y = data.get("price_2y", "")
                context_parts.append(f"- {name}: {price_1y} (1y) / {price_2y} (2y)")
            context_parts.append("")

        if service_type == "kitas" or service_type is None:
            context_parts.append("## Long-stay Permit Prices")  # Generic - no specific codes
            for name, data in services.get("kitas_permits", {}).items():
                offshore = data.get("offshore", data.get("price_1y_off", "Contact"))
                onshore = data.get("onshore", data.get("price_1y_on", "Contact"))
                context_parts.append(f"- {name}: {offshore} (offshore) / {onshore} (onshore)")
            context_parts.append("")

        if service_type == "business" or service_type is None:
            context_parts.append("## BUSINESS SERVICES")
            for name, data in services.get("business_legal_services", {}).items():
                price = data.get("price", "Contact")
                context_parts.append(f"- {name}: {price}")
            context_parts.append("")

        if service_type == "tax" or service_type is None:
            context_parts.append("## TAX SERVICES")
            for name, data in services.get("taxation_services", {}).items():
                price = data.get("price", "Contact")
                context_parts.append(f"- {name}: {price}")
            context_parts.append("")

        # Always include warnings
        warnings = self.prices.get("important_warnings", {})
        if warnings:
            context_parts.append("## IMPORTANT WARNINGS")
            for _key, warning in list(warnings.items())[:3]:  # Top 3 warnings
                context_parts.append(f"⚠️ {warning}")
            context_parts.append("")

        # Contact info
        contact = self.prices.get("contact_info", {})
        context_parts.append(
            f"Contact: {contact.get('email', '')} | WhatsApp: {contact.get('whatsapp', '')}"
        )

        return "\n".join(context_parts)


# Global singleton instance
_pricing_service: PricingService | None = None


def get_pricing_service() -> PricingService:
    """Get or create global pricing service instance"""
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService()
    return _pricing_service


# Convenience functions for easy import
def get_all_prices() -> dict[str, Any]:
    """Get all official prices"""
    return get_pricing_service().get_all_prices()


def search_service(query: str) -> dict[str, Any]:
    """Search for a service by name/keyword"""
    return get_pricing_service().search_service(query)


def get_visa_prices() -> dict[str, Any]:
    """Get visa prices"""
    return get_pricing_service().get_visa_prices()


def get_kitas_prices() -> dict[str, Any]:
    """Get KITAS prices"""
    return get_pricing_service().get_kitas_prices()


def get_business_prices() -> dict[str, Any]:
    """Get business service prices"""
    return get_pricing_service().get_business_prices()


def get_tax_prices() -> dict[str, Any]:
    """Get tax service prices"""
    return get_pricing_service().get_tax_prices()


def get_pricing_context_for_llm(service_type: str | None = None) -> str:
    """Get pricing data formatted for LLM context injection"""
    return get_pricing_service().format_for_llm_context(service_type)
