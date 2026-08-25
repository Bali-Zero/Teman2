"""Exact-key PricingTool bridge for the stateless GARUDA internal preview.

Prices are never literals here. Each case type maps to one official catalogue
key, and any missing, malformed, or mismatched row fails closed.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from backend.app.utils.logging_utils import sanitize_for_log
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
    *,
    today: date,
    service: PricingService | None = None,
    key: str | None = None,
    row: object = None,
) -> freshness.FreshnessReport:
    """THE single freshness seam for "is the price truth fresh enough to
    sell right now" — every caller and every test that forces a freshness
    state patches this exact name (`tests/services/garuda_flow/conftest.py`,
    `tests/app/routers/conftest.py`, `tests/app/routers/test_garuda_voa_public.py`,
    `freshness_report.collect_real_reports`). Deliberately kept as ONE
    function rather than a second one in front of it: a `price_for_case`
    freshness decision that could be reached WITHOUT going through this name
    would silently stop being controllable by any of the above — see
    `test_price_for_case_freshness_decision_always_passes_through_the_patchable_seam`
    in `test_pricing.py`, the tripwire that guards exactly this.

    Two modes, selected by whether ``row`` carries its own attestation:

    - **Catalogue-wide** (default — ``key``/``row`` omitted, or ``row`` has no
      ``verified_on`` / it is ``None``): checks ``service``'s
      ``metadata.last_updated``. Unattested rows (the ~98 that are not the two
      VOA rows) always take this path — byte-for-byte the original behaviour.
    - **Row-scoped** (``row`` carries a non-``None`` ``verified_on``): checks
      THAT stamp instead, via the same `freshness.check_freshness`, reported
      under a distinct ``price_catalogue.row[<key>]`` source so a caller (or
      the operator-facing report) can tell "this one row is stale" apart from
      "the whole catalogue is old". This is a NARROWING, never a widening —
      see `products/garuda-voa/product.yaml` owner decision 7: an owner who
      re-verifies one row is never read as covering the other ~98 under the
      same catalogue-wide stamp. A malformed attestation (present but not a
      parseable ISO date) fails CLOSED through `check_freshness`'s own
      fail-closed handling rather than falling back to the — possibly
      fresher — catalogue-wide stamp: a typo in an attestation must never
      become MORE permissive than having made no attestation at all.
    """
    raw_row_stamp = row.get("verified_on") if isinstance(row, dict) else None
    if raw_row_stamp is not None:
        source = f"price_catalogue.row[{key}]" if key else "price_catalogue.row"
        return freshness.check_freshness(
            source=source,
            stamp_accessor=lambda: raw_row_stamp,
            max_age_days=freshness.MAX_AGE_DAYS["price_catalogue"],
            today=today,
        )

    resolved = service or _pricing
    return freshness.check_freshness(
        source="price_catalogue",
        stamp_accessor=lambda: catalogue_last_updated_stamp(resolved),
        max_age_days=freshness.MAX_AGE_DAYS["price_catalogue"],
        today=today,
    )


def price_freshness_for_case(
    case_type: CaseType, *, today: date, service: PricingService | None = None
) -> freshness.FreshnessReport:
    """Freshness for the ONE sellable row `price_for_case` would use for
    ``case_type`` — the exact key-lookup + row/catalogue precedence
    `price_for_case` applies, exposed read-only so a reporting surface
    (`freshness_report.collect_real_reports`) can show "the row we actually
    sell" without duplicating that lookup logic itself. Never used by
    `price_for_case` itself (it does its own lookup, once, alongside the
    amount extraction) — this exists purely for diagnostics.
    """
    resolved = service or _pricing
    key = _EXTENSION_PRICE_KEY if case_type is CaseType.EXTENSION else _ISSUANCE_PRICE_KEY
    try:
        row = resolved.get_service_by_key(key)
    except Exception:
        row = None
    return price_catalogue_freshness(today=today, service=resolved, key=key, row=row)


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

    Freshness is checked PER ROW, through the single seam
    `price_catalogue_freshness(key=..., row=...)` — not once for the whole
    catalogue up front: the row has to be fetched first so its own
    ``verified_on`` attestation (if any) can override the catalogue-wide
    ``metadata.last_updated`` stamp for that ONE row only. ``key`` itself is
    computed before the row fetch — it is a pure expression of ``case_type``,
    no I/O — so the fail-closed ordering (never invent a price on any
    failure) is unchanged; only what "freshness" means for this row moved.
    """

    service = pricing or _pricing

    key = _EXTENSION_PRICE_KEY if case_type is CaseType.EXTENSION else _ISSUANCE_PRICE_KEY
    try:
        row = service.get_service_by_key(key)
    except Exception:
        logger.warning(
            "garuda_flow: exact official price lookup failed for %s",
            sanitize_for_log(case_type.value),
        )
        return None, None

    freshness_report = price_catalogue_freshness(today=today, service=service, key=key, row=row)
    if freshness_report.stale:
        logger.warning(
            "garuda_flow: price stale for case_type=%s (%s) — declining to quote",
            sanitize_for_log(case_type.value),
            sanitize_for_log(freshness_report.detail),
        )
        return None, None

    if not isinstance(row, dict) or row.get("key") != key:
        logger.warning(
            "garuda_flow: official price key mismatch for case_type=%s",
            sanitize_for_log(case_type.value),
        )
        return None, None
    amount = _positive_idr_amount(row.get("price"))
    if amount is None:
        logger.warning(
            "garuda_flow: malformed official price for case_type=%s",
            sanitize_for_log(case_type.value),
        )
        return None, None
    return amount, key


__all__ = [
    "catalogue_last_updated_stamp",
    "price_catalogue_freshness",
    "price_for_case",
    "price_freshness_for_case",
]
