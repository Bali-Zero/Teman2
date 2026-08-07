"""Deterministic, exact-key adapter to the Bali Zero pricing SSOT.

The approved catalogue remains valid until it is superseded or withdrawn;
``metadata.last_updated`` is provenance, not an invented expiry clock. An
amount is usable only when the signed product names one exact PricingTool row
and that row contains one unambiguous IDR amount. Ranges, fuzzy matches and
free-form contact prices fail closed without an amount.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol, cast

from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.models import PriceQuote, VisaProductVersion


class ExactPricingCatalog(Protocol):
    """Narrow PricingTool surface; fuzzy search is intentionally absent."""

    loaded: bool

    def get_service_by_key(self, key: str) -> dict[str, Any] | None: ...

    def get_all_prices(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UnavailablePricingCatalog:
    """Fail-closed catalog used when PricingTool cannot be acquired."""

    loaded: bool = False

    def get_service_by_key(self, key: str) -> None:
        return None

    def get_all_prices(self) -> dict[str, Any]:
        return {}


@dataclass(frozen=True, slots=True)
class PricingResolution:
    status: Literal["AVAILABLE", "CONTACT_REQUIRED", "UNAVAILABLE", "UNKNOWN"]
    reason_code: str
    evaluated_at: datetime
    catalog_last_updated: date | None = None
    catalog_version: str | None = None
    catalog_sha256: str | None = None
    row_sha256: str | None = None
    amount: int | None = None

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "status": self.status,
            "reason_code": self.reason_code,
            "evaluated_at": self.evaluated_at.isoformat(),
            "catalog_last_updated": (
                None if self.catalog_last_updated is None else self.catalog_last_updated.isoformat()
            ),
            "catalog_sha256": self.catalog_sha256,
            "row_sha256": self.row_sha256,
        }


def _sha256_jcs(value: dict[str, Any]) -> str:
    canonical = canonicalize_json(cast(dict[str, JsonValue], value))
    return hashlib.sha256(canonical).hexdigest()


def _catalog_last_updated(catalog: dict[str, Any]) -> date | None:
    metadata = catalog.get("metadata")
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("last_updated")
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _catalog_version(catalog: dict[str, Any]) -> str | None:
    raw = catalog.get("version")
    return raw if isinstance(raw, str) and raw.strip() else None


_IDR_AMOUNT_RE = re.compile(r"^(?:(?P<suffix>\d[\d.,]*)\s+IDR|IDR\s+(?P<prefix>\d[\d.,]*))$")
_GROUPED_IDR_AMOUNT_RE = re.compile(r"^(?:\d+|\d{1,3}(?:\.\d{3})+|\d{1,3}(?:,\d{3})+)$")


def _parse_exact_idr_amount(raw: object) -> int | None:
    """Parse one integral IDR amount; reject ranges and ambiguous text."""

    if not isinstance(raw, str):
        return None
    match = _IDR_AMOUNT_RE.fullmatch(raw.strip().upper())
    if match is None:
        return None
    grouped_amount = match.group("suffix") or match.group("prefix")
    if _GROUPED_IDR_AMOUNT_RE.fullmatch(grouped_amount) is None:
        return None
    amount = int(grouped_amount.replace(".", "").replace(",", ""))
    if amount > 9_007_199_254_740_991:
        return None
    return amount


def resolve_candidate_pricing(
    product: VisaProductVersion,
    *,
    pricing_catalog: ExactPricingCatalog,
    evaluated_at: datetime,
) -> PricingResolution:
    """Resolve one product without guessing or fuzzy matching."""

    pricing_key = product.pricing_key
    if pricing_key is None:
        return PricingResolution(
            status="CONTACT_REQUIRED",
            reason_code="PRICING_KEY_NOT_CONFIGURED",
            evaluated_at=evaluated_at,
        )
    try:
        if pricing_catalog.loaded is not True:
            raise RuntimeError("pricing catalog is not loaded")
        catalog = pricing_catalog.get_all_prices()
        if not isinstance(catalog, dict) or "error" in catalog:
            raise RuntimeError("pricing catalog payload is unavailable")
        catalog_sha256 = _sha256_jcs(catalog)
        last_updated = _catalog_last_updated(catalog)
        catalog_version = _catalog_version(catalog)
        row = pricing_catalog.get_service_by_key(pricing_key.item_key)
        if row is None or row.get("category") != pricing_key.category:
            return PricingResolution(
                status="CONTACT_REQUIRED",
                reason_code="PRICING_ROW_MISSING",
                evaluated_at=evaluated_at,
                catalog_last_updated=last_updated,
                catalog_version=catalog_version,
                catalog_sha256=catalog_sha256,
            )
        row_sha256 = _sha256_jcs(row)
    except Exception:
        # Pricing is not a legal-authority input. Any adapter/runtime failure
        # therefore degrades only the pricing assessment and can never erase
        # or reorder an already approved deterministic visa decision.
        return PricingResolution(
            status="UNKNOWN",
            reason_code="PRICING_CATALOG_UNAVAILABLE",
            evaluated_at=evaluated_at,
        )

    amount = _parse_exact_idr_amount(row.get("price"))
    if catalog_version is None or last_updated is None or amount is None:
        return PricingResolution(
            status="CONTACT_REQUIRED",
            reason_code="PRICING_ROW_NOT_EXACT_AMOUNT",
            evaluated_at=evaluated_at,
            catalog_last_updated=last_updated,
            catalog_version=catalog_version,
            catalog_sha256=catalog_sha256,
            row_sha256=row_sha256,
        )

    return PricingResolution(
        status="AVAILABLE",
        reason_code="PRICE_AVAILABLE",
        evaluated_at=evaluated_at,
        catalog_last_updated=last_updated,
        catalog_version=catalog_version,
        catalog_sha256=catalog_sha256,
        row_sha256=row_sha256,
        amount=amount,
    )


def build_price_quote(
    product: VisaProductVersion,
    resolution: PricingResolution,
    *,
    decision_id: uuid.UUID,
) -> PriceQuote | None:
    """Convert one exact-key resolution into the signed decision contract."""

    pricing_key = product.pricing_key
    if pricing_key is None or resolution.status != "AVAILABLE":
        return None
    quote_seed = ":".join(
        (
            str(product.product_version_id),
            resolution.status,
            resolution.catalog_sha256 or "no-catalog",
            resolution.row_sha256 or "no-row",
        )
    )
    return PriceQuote(
        quote_id=uuid.uuid5(decision_id, quote_seed),
        product_version_id=product.product_version_id,
        product_code=product.product_code,
        status=resolution.status,
        currency="IDR",
        amount=resolution.amount,
        pricing_key=pricing_key,
        catalog_version=resolution.catalog_version,
        catalog_sha256=resolution.catalog_sha256,
        row_sha256=resolution.row_sha256,
        quoted_at=resolution.evaluated_at,
        valid_until=None,
        reason_code=resolution.reason_code,
    )


__all__ = [
    "ExactPricingCatalog",
    "PricingResolution",
    "UnavailablePricingCatalog",
    "build_price_quote",
    "resolve_candidate_pricing",
]
