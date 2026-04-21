"""Read-only bridge between Visa Check and `PricingService`.

Rule (CLAUDE.md Golden Rule #12): never hardcode prices. This module
asks `PricingService` for the quote matching a VisaType and returns
it to the router as a plain int (IDR), plus the source string for
the UI disclaimer.

If PricingService cannot find a quote we return `None` — the UI then
says "Let's confirm the exact fee on WhatsApp" instead of inventing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.catalogue import VisaType

logger = logging.getLogger(__name__)

# Map our VisaType codes to substrings likely to appear in the
# price JSON keys (e.g. "C2 Business", "Investor KITAS 2 Years").
_SEARCH_HINTS: dict[VisaType, tuple[str, ...]] = {
    VisaType.C1: ("C1", "Tourism"),
    VisaType.C2: ("C2 Business",),
    VisaType.C7: ("C7", "Internship"),
    VisaType.C7A: ("C7A", "Music"),
    VisaType.C7B: ("C7B", "Sport"),
    VisaType.E33G: ("Digital Nomad", "Remote Worker", "E33G"),
    VisaType.E28A: ("Investor KITAS", "E28A"),
    VisaType.E23: ("Work KITAS", "E23"),
    VisaType.E33F: ("Retirement", "E33F"),
    VisaType.E31: ("Family", "Spouse", "Dependent", "E31"),
    VisaType.E30A: ("Student", "E30A"),
}


def _idr_string_to_int(raw: str) -> int | None:
    """Parse '5.800.000 IDR' → 5_800_000. Returns None if unparseable."""
    if not raw:
        return None
    match = re.search(r"([\d.,]+)\s*IDR", raw)
    if not match:
        return None
    digits = re.sub(r"[.,]", "", match.group(1))
    try:
        return int(digits)
    except ValueError:
        return None


def estimate_match_cost(
    *,
    visa_type: VisaType,
    pricing: PricingService,
) -> tuple[int | None, str | None]:
    """Return (cost_idr, human_source).

    `human_source` is the price-JSON key that matched (e.g.
    "C2 Business"), used for the UI disclaimer "priced as C2 Business".
    """
    hints = _SEARCH_HINTS.get(visa_type, (visa_type.value,))
    for hint in hints:
        results = pricing.search_service(hint)
        if not isinstance(results, dict):
            continue
        services = results.get("services") or results
        # Walk each category, take the first match.
        for category, items in services.items():
            if category == "contact_info":
                continue
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    cost = _extract_cost(item)
                    if cost is not None:
                        name = str(item.get("name") or item.get("code") or hint)
                        return cost, name
            elif isinstance(items, dict):
                for key, item in items.items():
                    if not isinstance(item, dict):
                        continue
                    cost = _extract_cost(item)
                    if cost is not None:
                        return cost, str(key)

    logger.warning(
        "pricing_bridge: no quote found for %s (hints=%s)",
        visa_type.value,
        hints,
    )
    return None, None


def _extract_cost(item: dict[str, Any]) -> int | None:
    """Try several shape possibilities in the price JSON."""
    raw = item.get("price") or item.get("price_idr")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        return _idr_string_to_int(raw)
    return None
