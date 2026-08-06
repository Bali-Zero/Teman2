"""Deterministic, exact-key adapter to the Bali Zero pricing SSOT.

The current catalogue declares a last-updated date but no approved max-age or
valid-until policy. Therefore this adapter can prove key/row identity and
content hashes, but it cannot emit an AVAILABLE amount. Every non-AVAILABLE
resolution deliberately omits price data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, cast

from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.models import VisaProductVersion


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
    status: str
    reason_code: str
    evaluated_at: datetime
    catalog_last_updated: date | None = None
    catalog_sha256: str | None = None
    row_sha256: str | None = None

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


def resolve_candidate_pricing(
    product: VisaProductVersion,
    *,
    pricing_catalog: ExactPricingCatalog,
    evaluated_at: datetime,
) -> PricingResolution:
    """Resolve one product without guessing, fuzzy matching, or exposing amount."""

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
        row = pricing_catalog.get_service_by_key(pricing_key.item_key)
        if row is None or row.get("category") != pricing_key.category:
            return PricingResolution(
                status="CONTACT_REQUIRED",
                reason_code="PRICING_ROW_MISSING",
                evaluated_at=evaluated_at,
                catalog_last_updated=last_updated,
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

    return PricingResolution(
        status="CONTACT_REQUIRED",
        reason_code="PRICING_FRESHNESS_UNKNOWN",
        evaluated_at=evaluated_at,
        catalog_last_updated=last_updated,
        catalog_sha256=catalog_sha256,
        row_sha256=row_sha256,
    )


__all__ = [
    "ExactPricingCatalog",
    "PricingResolution",
    "UnavailablePricingCatalog",
    "resolve_candidate_pricing",
]
