"""
Revenue Estimator — Look up estimated renewal revenue from PricingService.

All prices come from PricingService (SSOT: bali_zero_official_prices_2026.json).
Never hardcoded. Returns None when price is not found or not a BZ service.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING

import asyncpg

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
    rule: RenewalRule,
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

    def _scan(container: dict) -> tuple[bool, str]:
        """Search a flat ``{name: entry}`` mapping. Returns (found, price_str).

        Falls back to ``tier_range[0]`` (low end) when the entry uses a
        range instead of a single price (2026 ``tax_accounting`` rows).
        """
        if rule.renewal_pricing_key in container:
            entry = container[rule.renewal_pricing_key]
            if not isinstance(entry, dict):
                return True, ""
            price_str = entry.get("price", "") or ""
            if not price_str:
                tier_range = entry.get("tier_range")
                if isinstance(tier_range, (list, tuple)) and tier_range:
                    price_str = tier_range[0] or ""
            return True, price_str
        return False, ""

    for category_dict in services.values():
        if not isinstance(category_dict, dict):
            continue
        # 2026 ``tax_accounting`` is one level deeper.
        nested_subblocks = [
            v for v in category_dict.values()
            if isinstance(v, dict)
            and v
            and all(
                isinstance(item, dict) and ("price" in item or "tier_range" in item)
                for item in v.values()
            )
        ]
        if nested_subblocks:
            for sub_block in nested_subblocks:
                found, price_str = _scan(sub_block)
                if found:
                    result = _parse_idr(price_str)
                    if result is not None:
                        logger.debug(
                            "Revenue for rule '%s': %d IDR (key='%s', nested)",
                            rule.rule_id, result, rule.renewal_pricing_key,
                        )
                    return result
            continue

        found, price_str = _scan(category_dict)
        if found:
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
    services = all_prices.get("services", {})
    # 2026 renamed ``urgent_services`` → ``urgent_processing``; accept either
    # for transitional fixtures that still use the legacy key.
    urgent = services.get("urgent_processing") or services.get("urgent_services") or {}
    if not urgent:
        return None

    if processing_days <= 1:
        key = "Urgent 1 Hari"
    elif processing_days <= 2:
        key = "Urgent 2 Hari"
    else:
        key = "Urgent 3 Hari"

    entry = urgent.get(key, {})
    return _parse_idr(entry.get("price", ""))


# ---------------------------------------------------------------------------
# Revenue ↔ Compliance correlation — risk bands (decision #5)
# ---------------------------------------------------------------------------


class RiskBand(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


_BAND_WEIGHT: dict[RiskBand, float] = {
    RiskBand.GREEN: 1.0,
    RiskBand.YELLOW: 0.8,
    RiskBand.ORANGE: 0.5,
    RiskBand.RED: 0.2,
}

_SEVERITY_TO_BAND: dict[str, RiskBand] = {
    "warning": RiskBand.YELLOW,
    "urgent": RiskBand.ORANGE,
    "critical": RiskBand.RED,
}


def _band_rank(b: RiskBand) -> int:
    return {RiskBand.GREEN: 0, RiskBand.YELLOW: 1, RiskBand.ORANGE: 2, RiskBand.RED: 3}[b]


async def classify_client_risk(
    conn: asyncpg.Connection,
    client_id: int,
) -> RiskBand:
    """
    Return the worst risk band across a client's active alerts + overdue practices.

    Active = status in (pending, sent, acknowledged). 'info' alerts do not shift band.
    Worst-band-wins: having both warning and critical → RED.
    """
    highest: RiskBand = RiskBand.GREEN

    # Derive worst band from compliance_alerts
    rows = await conn.fetch(
        "SELECT severity FROM compliance_alerts "
        "WHERE client_id = $1 AND status IN ('pending','sent','acknowledged')",
        client_id,
    )
    for r in rows:
        band = _SEVERITY_TO_BAND.get(r["severity"])
        if band is None:
            continue
        if _band_rank(band) > _band_rank(highest):
            highest = band

    # Derive worst band from overdue practices (table may be absent locally)
    try:
        overdue_days: int = await conn.fetchval(
            """
            SELECT COALESCE(MAX(EXTRACT(DAY FROM (NOW() - due_at))), 0)::int
            FROM practices
            WHERE client_id = $1 AND status != 'completed' AND due_at < NOW()
            """,
            client_id,
        ) or 0
    except asyncpg.PostgresError:
        overdue_days = 0

    if overdue_days >= 30:
        if _band_rank(RiskBand.RED) > _band_rank(highest):
            highest = RiskBand.RED
    elif overdue_days > 0:
        if _band_rank(RiskBand.ORANGE) > _band_rank(highest):
            highest = RiskBand.ORANGE

    return highest


async def get_weighted_revenue(
    conn: asyncpg.Connection,
    client_id: int,
    *,
    expected_idr: int,
) -> int:
    """
    Return expected_idr multiplied by the risk-band weight for client_id.

    Example: urgent alert → ORANGE → 0.5 × expected_idr.
    """
    band = await classify_client_risk(conn, client_id)
    return int(expected_idr * _BAND_WEIGHT[band])


async def clients_at_revenue_risk(
    conn: asyncpg.Connection,
    *,
    min_band: RiskBand = RiskBand.ORANGE,
    limit: int = 20,
) -> list[dict]:
    """
    Return top-N clients at or above `min_band` ordered by alert count descending.

    Designed for the admin dashboard top-N at-risk query.
    """
    min_rank = _band_rank(min_band)
    severities = [
        s for s, b in _SEVERITY_TO_BAND.items() if _band_rank(b) >= min_rank
    ]
    if not severities:
        return []
    rows = await conn.fetch(
        """
        SELECT c.id, c.full_name, MAX(a.severity) AS worst_severity, COUNT(*) AS alerts
        FROM compliance_alerts a
        JOIN clients c ON c.id = a.client_id
        WHERE a.status IN ('pending','sent','acknowledged')
          AND a.severity = ANY($1::text[])
        GROUP BY c.id, c.full_name
        ORDER BY alerts DESC
        LIMIT $2
        """,
        severities,
        limit,
    )
    return [dict(r) for r in rows]


__all__ = [
    "estimate_renewal_revenue",
    "estimate_urgent_surcharge",
    "RiskBand",
    "classify_client_risk",
    "get_weighted_revenue",
    "clients_at_revenue_risk",
]
