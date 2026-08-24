"""Exact-key PricingTool bridge for the stateless GARUDA internal preview.

Prices are never literals here. Each case type maps to one official catalogue
key, and any missing, malformed, or mismatched row fails closed.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from backend.services.garuda_flow import freshness
from backend.services.garuda_flow.intake import CaseType
from backend.services.pricing.pricing_service import PricingService

logger = logging.getLogger(__name__)

_ISSUANCE_PRICE_KEY = "B1 Visa on Arrival (VOA)"
_EXTENSION_PRICE_KEY = "B1 Visa on Arrival Extension"
_pricing = PricingService()


def catalogue_last_updated_stamp(service: PricingService | object) -> object:
    """Raw ``metadata.last_updated`` from the loaded catalogue, unvalidated.

    Deliberately does no validation of its own — ``freshness.check_freshness``
    owns "is this a good stamp"; this only reaches into whatever object it is
    handed (the real `PricingService`, or a test double that may not even
    carry a ``prices`` attribute — ``getattr`` with a dict default keeps that
    case a clean "no stamp" rather than an `AttributeError`).
    """
    prices = getattr(service, "prices", None)
    if not isinstance(prices, dict):
        return None
    metadata = prices.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return metadata.get("last_updated")


def price_catalogue_freshness(
    *, today: date, service: PricingService | None = None
) -> freshness.FreshnessReport:
    """Freshness of the ``service`` catalogue's ``metadata.last_updated``.

    A named function (rather than an inline `freshness.check_freshness` call
    inside `price_for_case`) so it can be monkeypatched independently, the
    same way `freshness.nationality_eligibility_freshness` /
    `rule_constants_freshness` are — see
    `tests/services/garuda_flow/conftest.py`.
    """
    resolved = service or _pricing
    return freshness.check_freshness(
        source="price_catalogue",
        stamp_accessor=lambda: catalogue_last_updated_stamp(resolved),
        max_age_days=freshness.MAX_AGE_DAYS["price_catalogue"],
        today=today,
    )


def _positive_idr_amount(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([1-9]\d{0,2}(?:\.\d{3})*) IDR", value)
    if match is None:
        return None
    amount = int(match.group(1).replace(".", ""))
    return amount if amount > 0 else None


def price_for_case(
    case_type: CaseType,
    *,
    pricing: PricingService | None = None,
    today: date,
) -> tuple[int | None, str | None]:
    """Return the official ``(amount_idr, catalogue_key)`` for a B1 case.

    ``None`` values are deliberate fail-safe output: callers must ask staff to
    confirm rather than invent a price when the official catalogue is absent,
    cannot be matched, OR has not been re-verified within its freshness
    window (G-FRESHNESS-FAIL-CLOSED, DECISIONS.md Q9, `freshness.py`) —
    exactly the existing "no price" shape, never a new one. ``today`` is
    caller-supplied (never a clock read here), matching every other
    date-taking function in this engine.
    """

    service = pricing or _pricing

    freshness_report = price_catalogue_freshness(today=today, service=service)
    if freshness_report.stale:
        logger.warning(
            "garuda_flow: price catalogue stale for case_type=%s (%s) — declining to quote",
            case_type.value,
            freshness_report.detail,
        )
        return None, None

    key = _EXTENSION_PRICE_KEY if case_type is CaseType.EXTENSION else _ISSUANCE_PRICE_KEY
    try:
        row = service.get_service_by_key(key)
    except Exception:
        logger.warning("garuda_flow: exact official price lookup failed for %s", case_type.value)
        return None, None
    if not isinstance(row, dict) or row.get("key") != key:
        logger.warning("garuda_flow: official price key mismatch for case_type=%s", case_type.value)
        return None, None
    amount = _positive_idr_amount(row.get("price"))
    if amount is None:
        logger.warning("garuda_flow: malformed official price for case_type=%s", case_type.value)
        return None, None
    return amount, key


__all__ = ["catalogue_last_updated_stamp", "price_catalogue_freshness", "price_for_case"]
