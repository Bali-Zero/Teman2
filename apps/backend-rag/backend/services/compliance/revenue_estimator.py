"""
Revenue Estimator — Look up estimated renewal revenue from PricingService.

All prices come from PricingService (SSOT: bali_zero_official_prices_2025.json).
Never hardcoded. Returns None when price is not found or not a BZ service.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.compliance.renewal_rules import RenewalRule

logger = logging.getLogger(__name__)

_IDR_PATTERN = re.compile(r"[\d.,]+")


def _parse_idr(price_str: str) -> int | None:
    """
    Parse a price string like "18.000.000 IDR" or "18,000,000" → 18000000.
    Returns None for non-numeric prices like "Depend (Contact for quote)".
    """
    if not price_str or "depend" in price_str.lower() or "contact" in price_str.lower():
        return None
    match = _IDR_PATTERN.search(price_str)
    if not match:
        return None
    # Remove separators (. or ,) and parse
    cleaned = match.group(0).replace(".", "").replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None


def estimate_renewal_revenue(
    rule: "RenewalRule",
    all_prices: dict,
) -> int | None:
    """
    Look up the estimated revenue for a renewal rule from the full pricing dict.

    Args:
        rule:       RenewalRule with renewal_pricing_key.
        all_prices: Full dict from PricingService.get_pricing("all").
                    Expected shape: {"services": {"category": {"name": {"price": "X IDR"}}}}

    Returns:
        Estimated revenue in IDR (integer), or None if not found / not a BZ service.
    """
    if rule.renewal_pricing_key is None:
        return None  # Not a BZ service (e.g., passport renewal)

    services = all_prices.get("services", all_prices)

    for category_dict in services.values():
        if not isinstance(category_dict, dict):
            continue
        if rule.renewal_pricing_key in category_dict:
            price_str = category_dict[rule.renewal_pricing_key].get("price", "")
            result = _parse_idr(price_str)
            if result is not None:
                logger.debug(
                    "Revenue for rule '%s': %d IDR (key='%s')",
                    rule.rule_id,
                    result,
                    rule.renewal_pricing_key,
                )
            else:
                logger.debug(
                    "Revenue for rule '%s': non-numeric price '%s'",
                    rule.rule_id,
                    price_str,
                )
            return result

    logger.warning(
        "Pricing key '%s' not found in pricing data (rule=%s)",
        rule.renewal_pricing_key,
        rule.rule_id,
    )
    return None


def estimate_urgent_surcharge(processing_days: int, all_prices: dict) -> int | None:
    """
    Estimate the urgent surcharge if the action window is critically short.

    If days_until_action <= 0 (i.e., should have contacted client already),
    return the 1-day or 2-day urgent fee from pricing.

    Args:
        processing_days: Expected processing days for the renewal.
        all_prices:      Full pricing dict.

    Returns:
        Surcharge in IDR, or None if no urgency.
    """
    urgent_services = all_prices.get("services", {}).get("urgent_services", {})
    if not urgent_services:
        return None

    if processing_days <= 1:
        key = "Urgent 1 Hari"
    elif processing_days <= 2:
        key = "Urgent 2 Hari"
    else:
        key = "Urgent 3 Hari"

    entry = urgent_services.get(key, {})
    return _parse_idr(entry.get("price", ""))
