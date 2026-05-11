"""Official Pricing Service
Loads official prices from JSON (NO AI GENERATION).

Source of truth: ``backend/data/bali_zero_official_prices_2026.json``.

The 2026 schema differs from the legacy 2025 one in three ways the
service has to handle internally:

* The ``urgent_services`` category was renamed ``urgent_processing``.
* The ``visa_extensions`` category was dropped — ``C1 Tourism Extension``
  now lives inside ``single_entry_visas``.
* New categories ``tax_accounting`` (which has one extra nesting level
  for the four tier sub-blocks ``monthly_tax_basic`` / ``monthly_tax_bundled``
  / ``annual_basic_packages`` / ``annual_standalone``) and
  ``consultant_services`` (flat, like the others).
* Each entry now exposes ``name`` / ``description_en`` / ``icon_id``
  / ``tier_range`` (a list ``[low, high]`` or ``None``) on top of the
  legacy ``price`` / ``duration`` / ``validity`` / ``notes`` fields.
"""

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Authoritative pricing JSON, 2026 edition.
_PRICING_FILENAME = "bali_zero_official_prices_2026.json"

# Categories whose value is a flat ``{service_name: entry}`` mapping.
_FLAT_CATEGORIES = (
    "single_entry_visas",
    "multiple_entry_visas",
    "kitas_permits",
    "kitap_permits",
    "company_services",
    "consultant_services",
    "other_process",
    "urgent_processing",
)

# Categories whose value is ``{sub_block: {service_name: entry}}``.
_NESTED_CATEGORIES = ("tax_accounting",)


def _format_tier_range(tier_range: list[str] | tuple[str, str] | None) -> str | None:
    """Render a ``tier_range`` (e.g. ``["1.800.000 IDR", "2.000.000 IDR"]``)
    as ``"Rp 1.800.000 – 2.000.000"`` for human-facing surfaces."""
    if not tier_range or len(tier_range) != 2:
        return None
    low_raw, high_raw = tier_range
    low = (low_raw or "").replace("IDR", "").strip()
    high = (high_raw or "").replace("IDR", "").strip()
    if not low or not high:
        return None
    return f"Rp {low} – {high}"


def _entry_display_price(entry: dict[str, Any]) -> str:
    """Return the best human price string for a 2026 entry.

    Falls back to ``tier_range`` when ``price`` is empty (typical for
    ``tax_accounting`` rows) and to ``"Contact"`` if both are missing.
    """
    price = (entry.get("price") or "").strip()
    if price:
        return price
    rendered = _format_tier_range(entry.get("tier_range"))
    if rendered:
        return rendered
    return "Contact"


def _iter_service_entries(
    services: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Yield ``(category, service_name, entry)`` triples across the whole
    ``services`` mapping, descending one extra level for nested categories
    such as ``tax_accounting`` so callers see a flat stream."""
    triples: list[tuple[str, str, dict[str, Any]]] = []
    for category_name, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category_name in _NESTED_CATEGORIES:
            for sub_block in category_payload.values():
                if not isinstance(sub_block, dict):
                    continue
                for service_name, entry in sub_block.items():
                    if isinstance(entry, dict):
                        triples.append((category_name, service_name, entry))
        else:
            for service_name, entry in category_payload.items():
                if isinstance(entry, dict):
                    triples.append((category_name, service_name, entry))
    return triples


class PricingService:
    """Official Service Pricing - NO AI GENERATION ALLOWED"""

    def __init__(self) -> None:
        self.prices: dict[str, Any] = {}
        self.loaded = False
        self._load_prices()

    def _load_prices(self) -> None:
        """Load official prices from the 2026 JSON file."""
        try:
            json_path = (
                Path(__file__).parent.parent.parent / "data" / _PRICING_FILENAME
            )

            if not json_path.exists():
                logger.warning(f"Official prices file not found at {json_path}")
                self.prices = {}
                self.loaded = False
                return

            with open(json_path, encoding="utf-8") as f:
                self.prices = json.load(f)

            self.loaded = True
            logger.info(f"Loaded official prices from {json_path}")

            # Count services across the full 9-category 2026 schema, descending
            # into ``tax_accounting`` sub-blocks so the log line reflects the
            # real number of priced rows.
            service_count = len(_iter_service_entries(self.prices.get("services", {})))
            categories_present = [
                cat for cat in (*_FLAT_CATEGORIES, *_NESTED_CATEGORIES)
                if cat in self.prices.get("services", {})
            ]
            logger.info(
                f"{service_count} services loaded across {len(categories_present)} categories"
            )

        except Exception as e:
            logger.error(f"Error loading official prices: {e}")
            self.prices = {}
            self.loaded = False

    def get_pricing(self, service_type: str = "all") -> dict[str, Any]:
        """
        Get pricing for specific service type

        Args:
            service_type: Type of service (visa, kitas, business_setup, tax_consulting, legal, all)

        Returns:
            Pricing data for the requested service type
        """
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {
                    "email": settings.SUPPORT_EMAIL,
                    "whatsapp": settings.SUPPORT_WHATSAPP,
                },
            }

        # Map service types to specific methods
        if service_type == "visa":
            return self.get_visa_prices()
        if service_type == "kitas" or service_type == "long_stay_permit":
            return self.get_kitas_prices()  # Generic long-stay permit prices
        if service_type == "business_setup":
            return self.get_business_prices()
        if service_type == "tax_consulting":
            return self.get_tax_prices()
        if service_type == "legal":
            return self.get_business_prices()  # Legal services are in business
        if service_type == "all":
            return self.get_all_prices()
        # Try to search for the service
        return self.search_service(service_type)

    def get_all_prices(self) -> dict[str, Any]:
        """Get all official prices"""
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {
                    "email": settings.SUPPORT_EMAIL,
                    "whatsapp": settings.SUPPORT_WHATSAPP,
                },
            }
        return self.prices

    def search_service(self, query: str) -> dict[str, Any]:
        """Search for a specific service by name or keyword.

        Supports both the legacy LIST shape (some unit tests still mount
        ``[{code, name, ...}]`` fixtures) and the 2026 DICT shape, plus
        the 2026-only nested ``tax_accounting`` sub-block layout.
        """
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "contact": self.prices.get("contact_info", self.prices.get("metadata", {}).get("contact", {})),
            }

        query_lower = query.lower().strip()
        results: dict[str, Any] = {}

        # Extract keywords from query (remove common words)
        noise_words = {
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
            "di",
            "in",
            "bali",
            "un",
            "una",
            "il",
            "la",
            "anno",
            "anni",
            "year",
            "years",
            "prezzo",
            "a",
            "of",
            "per",
            "del",
            "della",
            "dei",
            "delle",
            "con",
            "and",
            "e",
            "or",
            "o",
        }

        # Split query and remove noise words; also remove short numeric tokens
        query_keywords = query_lower.split()
        clean_keywords = []
        for w in query_keywords:
            w_clean = w.strip("?.,!\"'")
            if w_clean and w_clean not in noise_words and len(w_clean) > 1:
                clean_keywords.append(w_clean)

        if not clean_keywords:
            # If all words were noise, use the raw query
            clean_keywords = [query_lower]

        services = self.prices.get("services", {})

        def _score_dict_entry(
            category_name: str,
            service_name: str,
            service_data: dict[str, Any],
            container: dict[str, Any] | None = None,
        ) -> None:
            service_text = service_name.lower()
            service_text += " " + str(service_data.get("name", "")).lower()
            service_text += " " + str(service_data.get("notes", "")).lower()
            service_text += " " + str(service_data.get("description_en", "")).lower()
            legacy_names = service_data.get("legacy_names", [])
            if isinstance(legacy_names, list):
                service_text += " " + " ".join(n.lower() for n in legacy_names)
            match_count = sum(1 for term in clean_keywords if term in service_text)
            if match_count > 0:
                target = container if container is not None else results
                target.setdefault(category_name, {})[service_name] = service_data

        for category_name, category_services in services.items():
            # Handle LIST format (legacy fixtures only — no 2026 category uses this)
            if isinstance(category_services, list):
                for service_item in category_services:
                    if not isinstance(service_item, dict):
                        continue
                    code = str(service_item.get("code", "")).lower()
                    name = str(service_item.get("name", "")).lower()
                    notes = str(service_item.get("notes", "")).lower()
                    description = str(service_item.get("description_en", "")).lower()
                    service_text = f"{code} {name} {notes} {description}"

                    legacy_names = service_item.get("legacy_names", [])
                    if isinstance(legacy_names, list):
                        service_text += " " + " ".join(n.lower() for n in legacy_names)

                    match_count = sum(1 for term in clean_keywords if term in service_text)
                    if match_count > 0:
                        results.setdefault(category_name, []).append(
                            (match_count, service_item),
                        )
                continue

            if not isinstance(category_services, dict):
                continue

            # 2026: ``tax_accounting`` is one level deeper.
            if category_name in _NESTED_CATEGORIES:
                for sub_block_name, sub_block in category_services.items():
                    if not isinstance(sub_block, dict):
                        continue
                    for service_name, service_data in sub_block.items():
                        if not isinstance(service_data, dict):
                            continue
                        # Annotate the entry with its sub-block so callers
                        # (UI, MCP, prompt builder) can preserve the
                        # tier hierarchy without us flattening it.
                        annotated = {**service_data, "_sub_block": sub_block_name}
                        _score_dict_entry(category_name, service_name, annotated)
                continue

            # Flat dict (single_entry_visas, kitas_permits, …, urgent_processing).
            for service_name, service_data in category_services.items():
                if not isinstance(service_data, dict):
                    continue
                _score_dict_entry(category_name, service_name, service_data)

        # For list results, sort by match_count descending, keep top results
        filtered_results: dict[str, Any] = {}
        for category_name, items in results.items():
            if isinstance(items, list):
                items.sort(key=lambda x: x[0], reverse=True)
                max_score = items[0][0] if items else 0
                if max_score <= 1:
                    best_items = [item for _score, item in items[:5]]
                else:
                    best_items = [item for score, item in items if score >= max_score]
                filtered_results[category_name] = best_items
            else:
                filtered_results[category_name] = items

        contact_info = self.prices.get(
            "contact_info",
            self.prices.get("metadata", {}).get("contact", {}),
        )

        if filtered_results:
            return {
                "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
                "search_query": query,
                "results": filtered_results,
                "contact_info": contact_info,
                "disclaimer": self.prices.get("disclaimer", {}),
            }
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
            "search_query": query,
            "message": f"No service found for '{query}'",
            "suggestion": f"Contact {settings.SUPPORT_EMAIL} for custom quotes",
            "contact_info": contact_info,
        }

    def _contact_info(self) -> dict[str, Any]:
        """Single source for contact info — prefer 2026 ``metadata.contact``."""
        explicit = self.prices.get("contact_info")
        if explicit:
            return explicit
        return self.prices.get("metadata", {}).get("contact", {})

    def get_visa_prices(self) -> dict[str, Any]:
        """Get all visa prices.

        2026 dropped the ``visa_extensions`` category — ``C1 Tourism Extension``
        is now a row inside ``single_entry_visas``. We still publish the
        ``visa_extensions`` key in the response for backwards compatibility
        with the Mouth ``PricingTable.tsx`` renderer, but it is empty.
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - VISA",
            "single_entry_visas": services.get("single_entry_visas", {}),
            "multiple_entry_visas": services.get("multiple_entry_visas", {}),
            # Legacy key preserved for the Mouth chat renderer; 2026 has no
            # standalone extensions category, so this is intentionally empty.
            "visa_extensions": services.get("visa_extensions", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_kitas_prices(self) -> dict[str, Any]:
        """Get all KITAS / KITAP prices."""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - KITAS",
            "kitas_permits": services.get("kitas_permits", {}),
            "kitap_permits": services.get("kitap_permits", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_business_prices(self) -> dict[str, Any]:
        """Get business / company / consultant service prices.

        2026 added ``consultant_services`` (Close PMA, NPWPD, BPJS, NPWP
        Personal, Update Data, EFIN). Surfaced alongside the existing
        ``company_services`` and ``other_process`` so the prompt builder
        and the Mouth UI can render them together.
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - BUSINESS",
            "company_services": services.get("company_services", {}),
            "consultant_services": services.get("consultant_services", {}),
            "other_process": services.get("other_process", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_tax_prices(self) -> dict[str, Any]:
        """Get tax & accounting prices.

        2026 introduced the dedicated ``tax_accounting`` category with four
        nested sub-blocks (``monthly_tax_basic`` / ``monthly_tax_bundled``
        / ``annual_basic_packages`` / ``annual_standalone``). The nested
        structure is preserved in the response so callers can render the
        tier hierarchy. Urgent processing kept under its 2026 name
        (``urgent_processing``).
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - TAX & URGENT",
            "tax_accounting": services.get("tax_accounting", {}),
            "urgent_processing": services.get("urgent_processing", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_quick_quotes(self) -> dict[str, Any]:
        """Get pre-calculated package quotes (deprecated — not in 2026 schema)."""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - PACKAGES",
            "quick_quotes": services.get("quick_quotes", {}),
            "contact_info": self._contact_info(),
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

    def _format_service_list(self, category_data: list | dict) -> list[str]:
        """Helper to format service data regardless of list/dict format.

        2026 dict entries can carry ``tier_range`` instead of ``price``;
        :func:`_entry_display_price` resolves both cases.
        """
        lines: list[str] = []
        if isinstance(category_data, list):
            for item in category_data:
                if isinstance(item, dict):
                    name = item.get("name", item.get("code", "Unknown"))
                    price_idr = item.get("price_idr", item.get("price", "Contact"))
                    price_usd = item.get("price_usd_approx", "")
                    duration = item.get("duration", "")
                    suffix = f" ({duration})" if duration else ""
                    usd_str = f" (~${price_usd})" if price_usd else ""
                    lines.append(
                        f"- {name}: IDR {price_idr:,}{usd_str}{suffix}"
                        if isinstance(price_idr, (int, float))
                        else f"- {name}: {price_idr}{usd_str}{suffix}",
                    )
        elif isinstance(category_data, dict):
            for name, data in category_data.items():
                if isinstance(data, dict):
                    # Detect tax_accounting-style sub-block: a dict whose
                    # values look like service entries themselves (have
                    # ``name`` and either ``price`` or ``tier_range``).
                    is_subblock = bool(data) and all(
                        isinstance(v, dict) and ("price" in v or "tier_range" in v)
                        for v in data.values()
                    )
                    # Distinguish a SINGLE entry (which also has those keys)
                    # from a sub-block by checking that ``data`` itself is
                    # NOT a service entry — service entries have ``name``.
                    if is_subblock and "name" not in data:
                        lines.append(f"### {name}")
                        lines.extend(self._format_service_list(data))
                        continue
                    display = _entry_display_price(data)
                    duration = data.get("duration", "")
                    duration_str = f" — {duration}" if duration else ""
                    lines.append(f"- {name}: {display}{duration_str}")
                else:
                    lines.append(f"- {name}: {data}")
        return lines

    def format_for_llm_context(self, service_type: str | None = None) -> str:
        """
        Format pricing data as context for LLM.

        Returns a concise string suitable for injection into LLM context.
        Sections track the 2026 schema: visa, KITAS/KITAP, company &
        consultant, tax & accounting, urgent processing.
        """
        if not self.loaded:
            return f"⚠️ Official prices not available. Contact {settings.SUPPORT_EMAIL}"

        context_parts = [
            "🔒 BALI ZERO OFFICIAL PRICES 2026 (DO NOT GENERATE - USE THESE EXACT VALUES)",
            "",
        ]

        services = self.prices.get("services", {})

        if service_type == "visa" or service_type is None:
            context_parts.append("## VISA PRICES")
            context_parts.extend(self._format_service_list(services.get("single_entry_visas", {})))
            context_parts.extend(
                self._format_service_list(services.get("multiple_entry_visas", {})),
            )
            context_parts.append("")

        if service_type == "kitas" or service_type is None:
            context_parts.append("## KITAS/KITAP PERMITS")
            context_parts.extend(self._format_service_list(services.get("kitas_permits", {})))
            context_parts.extend(self._format_service_list(services.get("kitap_permits", {})))
            context_parts.append("")

        if service_type == "business" or service_type is None:
            context_parts.append("## COMPANY & CONSULTANT SERVICES")
            context_parts.extend(self._format_service_list(services.get("company_services", {})))
            context_parts.extend(self._format_service_list(services.get("consultant_services", {})))
            context_parts.append("")

        if service_type == "tax" or service_type is None:
            context_parts.append("## TAX & ACCOUNTING")
            context_parts.extend(self._format_service_list(services.get("tax_accounting", {})))
            context_parts.append("")

        if service_type == "other" or service_type is None:
            context_parts.append("## OTHER SERVICES")
            context_parts.extend(self._format_service_list(services.get("other_process", {})))
            context_parts.append("")

        if service_type == "urgent" or service_type is None:
            context_parts.append("## URGENT PROCESSING")
            context_parts.extend(self._format_service_list(services.get("urgent_processing", {})))
            context_parts.append("")

        # Always include warnings
        warnings = self.prices.get("important_warnings", {})
        if warnings and isinstance(warnings, dict):
            context_parts.append("## IMPORTANT WARNINGS")
            for _key, warning in list(warnings.items())[:3]:
                context_parts.append(f"⚠️ {warning}")
            context_parts.append("")

        # Contact info
        contact = self._contact_info()
        context_parts.append(
            f"Contact: {contact.get('email', settings.SUPPORT_EMAIL)} | WhatsApp: {contact.get('whatsapp', settings.SUPPORT_WHATSAPP)}",
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
