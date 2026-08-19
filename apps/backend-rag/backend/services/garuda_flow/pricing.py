"""GARUDA VOA pricing bridge.

The owner archive and stateless internal preview share this bridge so both
resolve the same official catalogue row. Prices are
never literals here: :class:`PricingService` loads the PricingTool source of
truth and the existing Visa Check candidate ranker disambiguates the two B1
rows.
"""

from __future__ import annotations

import logging
import re

from backend.services.garuda_flow.intake import CaseType
from backend.services.pricing.pricing_service import PricingService

logger = logging.getLogger(__name__)

_ISSUANCE_PRICE_KEY = "B1 Visa on Arrival (VOA)"
_EXTENSION_PRICE_KEY = "B1 Visa on Arrival Extension"
_pricing = PricingService()


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
) -> tuple[int | None, str | None]:
    """Return the official ``(amount_idr, catalogue_key)`` for a B1 case.

    ``None`` values are deliberate fail-safe output: callers must ask staff to
    confirm rather than invent a price when the official catalogue is absent
    or cannot be matched.
    """

    service = pricing or _pricing
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


__all__ = ["price_for_case"]
