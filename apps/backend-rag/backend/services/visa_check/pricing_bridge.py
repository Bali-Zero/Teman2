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

# Known-None set: VisaTypes for which the pricing JSON has no entry.
# Bridge returns (None, None) for these and the UI shows
# "confirm on WhatsApp". These are intentional, not bugs.
KNOWN_NONE_VISAS: frozenset[VisaType] = frozenset({
    VisaType.C6,       # Social visit — no standalone C6 row in pricing JSON
    VisaType.E30A,     # Education — JSON lacks a student visa entry
})


# Map our VisaType codes to substrings likely to appear in the
# price JSON keys. Names reflect the JSON shape exactly (see
# backend/data/bali_zero_official_prices_2025.json). Offshore
# variants are preferred (standard fresh-applicant path).
_SEARCH_HINTS: dict[VisaType, tuple[str, ...]] = {
    VisaType.C1:             ("C1 Tourism",),
    VisaType.C2:             ("C2 Business",),
    VisaType.C6:             ("C6", "Social"),                              # known None
    VisaType.C7:             ("C7A&B Music/Art", "C7"),                     # best-effort
    VisaType.C7A:            ("C7A&B Music/Art", "C7A"),
    VisaType.C7B:            ("C7A&B Music/Art", "C7B"),
    VisaType.C18:            ("C18 Work Trial",),
    VisaType.C22A:           ("C22A&B Internship (60 Days)", "C22A&B Internship"),
    VisaType.D2:             ("D12 Business Investigation (1 Year)", "D2"),  # closest multi-entry row
    VisaType.D12:            (
        "D12 Business Investigation (1 Year)",
        "D12 Business Investigation (2 Years)",
    ),
    VisaType.E23:            ("Working KITAS (Offshore)", "Working KITAS"),
    VisaType.E23_FREELANCE:  ("Freelance E23 (Offshore)", "Freelance E23"),
    VisaType.E28A:           ("Investor KITAS 2 Years (Offshore)", "Investor KITAS"),
    VisaType.E30A:           ("Education", "Student"),                       # known None
    VisaType.E31:            (
        "Dependent 1 Year (Offshore)",
        "Spouse 1 Year (Offshore)",
        "Family",
    ),
    VisaType.E33E:           ("Retirement KITAP + MERP", "Retirement"),
    VisaType.E33F:           ("Retirement (Offshore)", "Retirement"),
    VisaType.E33G:           ("E33G Remote Worker (Offshore)", "E33G Remote Worker"),
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
        services = results.get("results") or results.get("services") or results
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


__all__ = [
    "KNOWN_NONE_VISAS",
    "_idr_string_to_int",
    "estimate_match_cost",
]
